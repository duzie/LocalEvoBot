from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import os
import importlib
import pkgutil
import inspect
import shutil
import io
import re
import zipfile
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Tuple
from langchain_core.tools import BaseTool
from ..shared import shared

router = APIRouter()

def _get_project_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def _parse_tool_item(item: str) -> Dict[str, str]:
    name = ""
    desc = ""
    if item.startswith("**"):
        end = item.find("**", 2)
        if end != -1:
            name = item[2:end].strip()
            rest = item[end + 2 :].strip()
            if rest.startswith(":"):
                desc = rest[1:].strip()
        else:
            name = item.strip("*").strip()
    else:
        if ":" in item:
            parts = item.split(":", 1)
            name = parts[0].strip()
            desc = parts[1].strip()
        else:
            name = item.strip()
    return {"name": name, "description": desc}

def _parse_skill_md(path: str) -> Dict[str, Any]:
    info = {
        "name": "",
        "version": "",
        "description": "",
        "entry": "",
        "tools": [],
        "platforms": [],
        "dependencies": [],
        "references": []
    }
    if not os.path.exists(path):
        return info
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return info
    section = ""
    for line in lines:
        s = line.strip()
        if s.startswith("## "):
            section = s[3:].strip().lower()
            continue
        if not s:
            continue
        if section in {"name", "version", "description", "entry"}:
            if not info.get(section):
                info[section] = s
            continue
        if section in {"tools", "platforms", "dependencies", "references"}:
            if not s.startswith("-"):
                continue
            item = s.lstrip("-").strip()
            if section == "tools":
                parsed = _parse_tool_item(item)
                if parsed.get("name"):
                    info["tools"].append(parsed)
            else:
                info[section].append(item)
    return info

def _list_skill_dirs(root: str) -> List[str]:
    if not os.path.isdir(root):
        return []
    items = []
    for name in os.listdir(root):
        skill_dir = os.path.join(root, name)
        if not os.path.isdir(skill_dir):
            continue
        if os.path.exists(os.path.join(skill_dir, "skill.md")):
            items.append(name)
    return sorted(items)

def _build_entry(scope: str, skill_id: str) -> str:
    prefix = "app.skills" if scope == "skills" else "app.auto_skills"
    return f"{prefix}.{skill_id}.scripts"

def _discover_tools(entry: str) -> Tuple[List[str], List[str]]:
    errors = []
    tools = []
    try:
        scripts_module = importlib.import_module(entry)
    except Exception as e:
        return [], [f"导入入口失败: {e}"]
    def _collect(mod):
        for _, obj in inspect.getmembers(mod):
            if isinstance(obj, BaseTool):
                tools.append(obj)
            elif inspect.isclass(obj) and issubclass(obj, BaseTool) and obj is not BaseTool:
                try:
                    tools.append(obj())
                except Exception:
                    pass
    if hasattr(scripts_module, "__path__"):
        for _, module_name, _ in pkgutil.iter_modules(scripts_module.__path__):
            full_module_name = f"{entry}.{module_name}"
            try:
                module = importlib.import_module(full_module_name)
                _collect(module)
            except Exception as e:
                errors.append(f"模块加载失败: {full_module_name} ({e})")
    else:
        _collect(scripts_module)
    names = []
    for t in tools:
        n = getattr(t, "name", "") or ""
        if n:
            names.append(n)
    return sorted(set(names)), errors

def _normalize_scope(scope: str) -> str:
    s = (scope or "").strip().lower()
    if s in {"skills", "skill"}:
        return "skills"
    if s in {"auto_skills", "autos", "auto"}:
        return "auto_skills"
    return s

def _is_abs_path(path: str) -> bool:
    try:
        return bool(path) and os.path.isabs(path)
    except Exception:
        return False

def _safe_rmtree(path: str):
    if os.path.exists(path):
        shutil.rmtree(path)

def _build_skills_allowlist(requested: List[Dict[str, Any]]) -> Tuple[List[str], List[str], List[str]]:
    necessary_core = ["system_skill"]
    core: List[str] = []
    auto: List[str] = []
    for item in (requested or []):
        if not isinstance(item, dict):
            continue
        scope = _normalize_scope(item.get("scope"))
        skill_id = str(item.get("id") or "").strip()
        if not skill_id:
            continue
        if scope == "skills":
            core.append(skill_id)
        elif scope == "auto_skills":
            auto.append(skill_id)
    for sid in necessary_core:
        if sid not in core:
            core.append(sid)
    core = sorted(set(core))
    auto = sorted(set(auto))
    added = [sid for sid in necessary_core if sid in core]
    return core, auto, added

def _prune_exported_system_skill(dst_root: str):
    skill_dir = os.path.join(dst_root, "app", "skills", "system_skill")
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return

    keep_scripts = {"__init__.py", "experience_tools.py"}
    for name in os.listdir(scripts_dir):
        p = os.path.join(scripts_dir, name)
        if os.path.isdir(p):
            continue
        if name.endswith(".py") and name not in keep_scripts:
            try:
                os.remove(p)
            except Exception:
                pass

def _write_exported_agent_prompt(dst_root: str, agent_prompt: str):
    prompts_path = os.path.join(dst_root, "app", "prompts.py")
    if not os.path.exists(prompts_path):
        return
    try:
        with open(prompts_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return
    marker = 'base = """'
    start = content.find(marker)
    if start == -1:
        return
    start_text = start + len(marker)
    end = content.find('"""', start_text)
    if end == -1:
        return
    safe = str(agent_prompt or "").replace("\r\n", "\n").replace("\r", "\n")
    safe = safe.replace('"""', '\\"""')
    if safe and not safe.endswith("\n"):
        safe += "\n"
    content2 = content[:start_text] + safe + content[end:]
    try:
        with open(prompts_path, "w", encoding="utf-8") as f:
            f.write(content2)
    except Exception:
        return

def _sanitize_filename(name: str) -> str:
    n = (name or "").strip()
    if not n:
        n = "agent_export"
    n = re.sub(r'[^a-zA-Z0-9._-]+', "_", n)
    n = n.strip("._-")
    return n or "agent_export"

def _zip_directory(dir_path: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fn in files:
                if fn.endswith(".pyc"):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, dir_path).replace("\\", "/")
                zf.write(full, rel)
    return buf.getvalue()

    init_path = os.path.join(scripts_dir, "__init__.py")
    init_content = "from .experience_tools import add_operation_experience, get_operation_experience, compress_operation_experience, search_short_term_memory\n"
    try:
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(init_content)
    except Exception:
        pass

    md_path = os.path.join(skill_dir, "skill.md")
    if os.path.exists(md_path):
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
        except Exception:
            lines = []
        if lines:
            out = []
            in_tools = False
            for line in lines:
                if line.strip().lower() == "## tools":
                    in_tools = True
                    out.append(line)
                    out.append("- add_operation_experience: 记录操作经验")
                    out.append("- get_operation_experience: 查询操作经验")
                    out.append("- search_short_term_memory: 搜索短期记忆（本地对话消息）")
                    out.append("- compress_operation_experience: 压缩操作经验")
                    continue
                if in_tools:
                    if line.strip().startswith("## "):
                        in_tools = False
                        out.append(line)
                    continue
                out.append(line)
            try:
                with open(md_path, "w", encoding="utf-8") as f:
                    f.write("\n".join(out) + "\n")
            except Exception:
                pass

def _copy_project_filtered(src_root: str, dst_root: str, allowed_core: List[str], allowed_auto: List[str]):
    allowed_core_set = set(allowed_core or [])
    allowed_auto_set = set(allowed_auto or [])

    def ignore(dirpath: str, names: List[str]):
        ignored = set()
        rel_norm = os.path.relpath(dirpath, src_root).replace("\\", "/")

        if rel_norm == ".":
            for n in ["__pycache__", ".git", ".venv", ".idea", ".trae", "_exports", "exports"]:
                if n in names:
                    ignored.add(n)

        if rel_norm == "app":
            if "data" in names:
                ignored.add("data")

        if rel_norm == "gateway":
            if "node_modules" in names:
                ignored.add("node_modules")

        if rel_norm == "web/frontend":
            if "node_modules" in names:
                ignored.add("node_modules")

        if rel_norm == "app/skills":
            for name in names:
                full = os.path.join(dirpath, name)
                if os.path.isdir(full) and name not in allowed_core_set:
                    ignored.add(name)

        if rel_norm == "app/auto_skills":
            for name in names:
                full = os.path.join(dirpath, name)
                if os.path.isdir(full) and name not in allowed_auto_set:
                    ignored.add(name)

        if "__pycache__" in names:
            ignored.add("__pycache__")

        return list(ignored)

    shutil.copytree(src_root, dst_root, ignore=ignore)

@router.post("/export")
async def export_agent(payload: Dict[str, Any]):
    target_dir = str((payload or {}).get("target_dir") or "").strip()
    overwrite = bool((payload or {}).get("overwrite")) if isinstance(payload, dict) else False
    requested = (payload or {}).get("skills") if isinstance(payload, dict) else None
    if not isinstance(requested, list):
        requested = []
    for item in requested:
        if not isinstance(item, dict):
            continue
        scope = _normalize_scope(item.get("scope"))
        skill_id = str(item.get("id") or "").strip()
        if scope == "skills" and skill_id == "skillgen_skill":
            raise HTTPException(status_code=400, detail="skillgen_skill is not allowed to export")
    if not target_dir:
        raise HTTPException(status_code=400, detail="target_dir required")
    if not _is_abs_path(target_dir):
        raise HTTPException(status_code=400, detail="target_dir must be an absolute path")

    src_root = _get_project_root()
    src_abs = os.path.abspath(src_root)
    dst_abs = os.path.abspath(target_dir)
    if dst_abs == src_abs:
        raise HTTPException(status_code=400, detail="target_dir cannot be the current project directory")
    try:
        if os.path.commonpath([dst_abs, src_abs]) == src_abs:
            exports_root = os.path.join(src_abs, "_exports")
            if os.path.commonpath([dst_abs, exports_root]) != exports_root:
                raise HTTPException(status_code=400, detail="target_dir cannot be inside the current project directory (except _exports)")
    except ValueError:
        pass

    if os.path.exists(dst_abs):
        if not overwrite:
            raise HTTPException(status_code=400, detail="target_dir already exists; set overwrite=true to replace")
        _safe_rmtree(dst_abs)

    allowed_core, allowed_auto, added_necessary = _build_skills_allowlist(requested)
    try:
        _copy_project_filtered(src_abs, dst_abs, allowed_core, allowed_auto)
        _prune_exported_system_skill(dst_abs)
    except Exception as e:
        try:
            _safe_rmtree(dst_abs)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"export failed: {e}")

    return {
        "ok": True,
        "target_dir": dst_abs,
        "kept_skills": allowed_core,
        "kept_auto_skills": allowed_auto,
        "added_necessary_skills": added_necessary,
    }

@router.post("/export_zip")
async def export_agent_zip(payload: Dict[str, Any]):
    requested = (payload or {}).get("skills") if isinstance(payload, dict) else None
    if not isinstance(requested, list):
        requested = []
    for item in requested:
        if not isinstance(item, dict):
            continue
        scope = _normalize_scope(item.get("scope"))
        skill_id = str(item.get("id") or "").strip()
        if scope == "skills" and skill_id == "skillgen_skill":
            raise HTTPException(status_code=400, detail="skillgen_skill is not allowed to export")

    agent_prompt = str((payload or {}).get("agent_prompt") or "")
    filename = _sanitize_filename(str((payload or {}).get("filename") or ""))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"{filename}_{ts}.zip"

    src_abs = os.path.abspath(_get_project_root())
    allowed_core, allowed_auto, added_necessary = _build_skills_allowlist(requested)
    tmp_parent = tempfile.mkdtemp(prefix="agent_export_")
    tmp_root = os.path.join(tmp_parent, "project")
    try:
        _copy_project_filtered(src_abs, tmp_root, allowed_core, allowed_auto)
        _prune_exported_system_skill(tmp_root)
        if agent_prompt.strip():
            _write_exported_agent_prompt(tmp_root, agent_prompt)
        data = _zip_directory(tmp_root)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"export failed: {e}")
    finally:
        try:
            shutil.rmtree(tmp_parent, ignore_errors=True)
        except Exception:
            pass

    headers = {
        "Content-Disposition": f'attachment; filename="{zip_name}"',
        "X-Export-Kept-Skills": ",".join(allowed_core),
        "X-Export-Kept-Auto-Skills": ",".join(allowed_auto),
        "X-Export-Added-Necessary": ",".join(added_necessary),
    }
    return StreamingResponse(io.BytesIO(data), media_type="application/zip", headers=headers)

@router.get("")
async def list_skills():
    root = _get_project_root()
    skills_root = os.path.join(root, "app", "skills")
    auto_root = os.path.join(root, "app", "auto_skills")
    items = []
    for scope, base in [("skills", skills_root), ("auto_skills", auto_root)]:
        for skill_id in _list_skill_dirs(base):
            md_path = os.path.join(base, skill_id, "skill.md")
            info = _parse_skill_md(md_path)
            name = info.get("name") or skill_id
            entry = info.get("entry") or _build_entry(scope, skill_id)
            items.append({
                "id": skill_id,
                "name": name,
                "scope": scope,
                "version": info.get("version") or "",
                "description": info.get("description") or "",
                "entry": entry,
                "tools": info.get("tools") or [],
                "platforms": info.get("platforms") or [],
                "dependencies": info.get("dependencies") or [],
                "references": info.get("references") or [],
                "tool_count": len(info.get("tools") or []),
                "md_path": md_path
            })
    items.sort(key=lambda x: (x.get("scope") or "", x.get("name") or ""))
    return {"skills": items}

@router.post("/reload")
async def reload_skills():
    shared.put_input("__RELOAD_SKILLS__")
    return {"ok": True}

@router.get("/{scope}/{skill_id}/loadability")
async def test_loadability(scope: str, skill_id: str):
    scope = (scope or "").strip().lower()
    if scope not in {"skills", "auto_skills"}:
        raise HTTPException(status_code=400, detail="invalid scope")
    entry = _build_entry(scope, skill_id)
    tools, errors = _discover_tools(entry)
    return {
        "ok": not errors,
        "entry": entry,
        "tools_found": tools,
        "errors": errors
    }
