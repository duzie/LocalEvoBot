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
import json
import time
import hashlib
import traceback
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from ..shared import shared
from app.agent import create_llm
from app.skills.skillgen_skill.scripts.skill_tools import scaffold_skill, write_tool_code

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

def _safe_json_loads(text: str) -> Optional[Any]:
    s = str(text or "").strip()
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        frag = s[start : end + 1]
        try:
            return json.loads(frag)
        except Exception:
            return None
    return None

def _normalize_skill_name(name: str, fallback_text: str = "") -> str:
    raw = str(name or "").strip()
    if raw and re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", raw):
        return raw
    base = "gen"
    m = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", str(fallback_text or ""))
    if m:
        base = m[0][:24]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    h = hashlib.sha256((fallback_text or ts).encode("utf-8", errors="ignore")).hexdigest()[:6]
    out = f"{base}_{ts}_{h}"
    out = re.sub(r"[^a-zA-Z0-9_]+", "_", out)
    if not re.match(r"^[a-zA-Z]", out):
        out = "gen_" + out
    return out[:60]

def _coerce_arg_default(arg_type: str):
    t = (arg_type or "str").strip().lower()
    if t == "int":
        return 0
    if t == "float":
        return 0.0
    if t == "bool":
        return False
    if t in {"list", "dict"}:
        return None
    return ""

def _python_literal(v: Any) -> str:
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, (list, dict)):
        return "None"
    return json.dumps(str(v), ensure_ascii=False)

def _build_tool_module(tool: Dict[str, Any]) -> str:
    tool_name = str(tool.get("name") or "").strip()
    tool_desc = str(tool.get("description") or "工具").strip()
    args = tool.get("args") or []
    type_map = {"str": "str", "int": "int", "float": "float", "bool": "bool", "list": "list", "dict": "dict"}

    sig_parts = []
    doc_parts = []
    in_payload_parts = []
    for a in args:
        if not isinstance(a, dict):
            continue
        an = str(a.get("name") or "").strip()
        if not an or not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", an):
            continue
        at = type_map.get(str(a.get("type") or "str").lower(), "str")
        if "default" in a:
            dv = a.get("default")
        else:
            dv = _coerce_arg_default(at)
        sig_parts.append(f"{an}: {at} = {_python_literal(dv)}")
        ad = str(a.get("description") or "").strip()
        if ad:
            doc_parts.append(f"    {an}: {ad}")
        in_payload_parts.append(f"        \"{an}\": {an},")

    sig = ", ".join(sig_parts)
    if sig:
        sig = " " + sig
    doc = ""
    if doc_parts:
        doc = "\n\n    Args:\n" + "\n".join(doc_parts)

    return "\n".join([
        "from langchain_core.tools import tool",
        "from typing import Dict, Any",
        "",
        "@tool",
        f"def {tool_name}({sig.strip()}):",
        '    """',
        f"    {tool_desc}{doc}",
        '    """',
        "    payload: Dict[str, Any] = {\"ok\": True, \"message\": \"ok\"}",
        "    payload[\"input\"] = {",
        *in_payload_parts,
        "    }",
        "    return payload",
        "",
    ])

def _validate_spec(spec: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    errors: List[str] = []
    if not isinstance(spec, dict):
        return {}, ["spec 必须为对象"]
    skill_name = str(spec.get("skill_name") or spec.get("name") or "").strip()
    description = str(spec.get("description") or "").strip()
    tools = spec.get("tools") or []
    tests = spec.get("tests") or []
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", skill_name):
        errors.append("skill_name 非法（仅字母/数字/下划线，且以字母开头）")
    if not isinstance(tools, list) or not tools:
        errors.append("tools 必须为非空数组")
    clean_tools: List[Dict[str, Any]] = []
    for t in tools if isinstance(tools, list) else []:
        if not isinstance(t, dict):
            continue
        tn = str(t.get("name") or "").strip()
        td = str(t.get("description") or "工具").strip()
        if not tn or not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", tn):
            continue
        args = t.get("args") or []
        clean_args = []
        if isinstance(args, list):
            for a in args:
                if not isinstance(a, dict):
                    continue
                an = str(a.get("name") or "").strip()
                if not an or not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", an):
                    continue
                clean_args.append({
                    "name": an,
                    "type": str(a.get("type") or "str"),
                    "default": a.get("default") if "default" in a else None,
                    "description": str(a.get("description") or "")
                })
        clean_tools.append({"name": tn, "description": td, "args": clean_args})
    if tools and not clean_tools:
        errors.append("tools 中没有可用的工具定义")

    clean_tests = []
    if isinstance(tests, list):
        for it in tests:
            if not isinstance(it, dict):
                continue
            tool = str(it.get("tool") or "").strip()
            args = it.get("args") if isinstance(it.get("args"), dict) else {}
            expect_ok = True if it.get("expect_ok") is None else bool(it.get("expect_ok"))
            contains = it.get("contains")
            clean_tests.append({"tool": tool, "args": args, "expect_ok": expect_ok, "contains": contains})

    return {
        "skill_name": skill_name,
        "description": description,
        "tools": clean_tools,
        "tests": clean_tests
    }, errors

def _run_loadability(scope: str, skill_id: str) -> Dict[str, Any]:
    entry = _build_entry(scope, skill_id)
    tools, errors = _discover_tools(entry)
    return {"ok": not errors, "entry": entry, "tools_found": tools, "errors": errors}

def _run_tool_tests(skill_name: str, tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    import importlib as _importlib
    _importlib.invalidate_caches()
    results: List[Dict[str, Any]] = []
    for t in (tests or []):
        tool = str((t or {}).get("tool") or "").strip()
        args = (t or {}).get("args") if isinstance((t or {}).get("args"), dict) else {}
        expect_ok = True if (t or {}).get("expect_ok") is None else bool((t or {}).get("expect_ok"))
        contains = (t or {}).get("contains")
        if not tool:
            continue
        module_name = f"app.auto_skills.{skill_name}.scripts.{tool}"
        try:
            mod = _importlib.import_module(module_name)
            obj = getattr(mod, tool, None)
            if obj is None or not hasattr(obj, "invoke"):
                results.append({"tool": tool, "ok": False, "error": f"未找到可调用工具: {tool}", "result": None})
                continue
            out = obj.invoke(args)
            ok = True
            if expect_ok:
                ok = isinstance(out, dict) and out.get("ok") is True
            if ok and contains is not None:
                ok = str(contains) in json.dumps(out, ensure_ascii=False)
            results.append({"tool": tool, "ok": ok, "error": "" if ok else "断言失败", "result": out})
        except Exception as e:
            results.append({"tool": tool, "ok": False, "error": str(e), "result": None})
    return results

class GenerateSkillPayload(BaseModel):
    request: str = Field(default="")
    skill_name: str = Field(default="")
    overwrite: bool = Field(default=False)
    dry_run: bool = Field(default=False)
    spec: Dict[str, Any] = Field(default_factory=dict)

def _llm_generate_spec(requirement: str, skill_name_hint: str = "") -> Dict[str, Any]:
    llm = create_llm()
    sys_text = "\n".join([
        "你是资深 Python 工程师，请把用户需求转成一个“技能规格”JSON。",
        "只输出 JSON，不要输出 markdown，不要解释。",
        "JSON schema:",
        "{",
        "  \"skill_name\": \"snake_case, 以字母开头\",",
        "  \"description\": \"一句话描述\",",
        "  \"tools\": [",
        "    {",
        "      \"name\": \"tool_name\",",
        "      \"description\": \"工具描述\",",
        "      \"args\": [{\"name\":\"arg\",\"type\":\"str|int|float|bool|list|dict\",\"default\":null,\"description\":\"\"}]",
        "    }",
        "  ],",
        "  \"tests\": [{\"tool\":\"tool_name\",\"args\":{},\"expect_ok\":true,\"contains\":\"可选子串\"}]",
        "}",
        "约束：工具数量 1-3 个；参数名必须是合法 Python 标识符；尽量给出 tests。",
    ])
    user_text = f"需求：{requirement.strip()}\nskill_name_hint：{skill_name_hint.strip()}"
    resp = llm.invoke([
        {"role": "system", "content": sys_text},
        {"role": "user", "content": user_text},
    ])
    text = getattr(resp, "content", "") if resp is not None else ""
    parsed = _safe_json_loads(text)
    if isinstance(parsed, dict):
        return parsed
    raise ValueError("LLM 未返回可解析的 JSON 规格")

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

@router.post("/generate")
async def generate_skill(payload: GenerateSkillPayload):
    started_at = time.time()
    try:
        req_text = str(payload.request or "")
        overwrite = bool(payload.overwrite)
        dry_run = bool(payload.dry_run)

        spec_raw: Optional[Dict[str, Any]] = None
        if isinstance(payload.spec, dict) and payload.spec:
            spec_raw = payload.spec
        if spec_raw is None:
            parsed = _safe_json_loads(req_text)
            if isinstance(parsed, dict) and ("tools" in parsed or "skill_name" in parsed or "name" in parsed):
                spec_raw = parsed
        if spec_raw is None:
            spec_raw = _llm_generate_spec(req_text, payload.skill_name)

        if not isinstance(spec_raw, dict):
            raise HTTPException(status_code=400, detail="无法生成规格")

        if payload.skill_name.strip():
            spec_raw["skill_name"] = payload.skill_name.strip()
        if "skill_name" not in spec_raw and "name" in spec_raw:
            spec_raw["skill_name"] = spec_raw.get("name")
        spec_raw["skill_name"] = _normalize_skill_name(spec_raw.get("skill_name"), req_text)

        spec, errors = _validate_spec(spec_raw)
        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        tools = spec.get("tools") or []
        tests = spec.get("tests") or []
        if not tests:
            auto_tests = []
            for t in tools:
                args = {}
                for a in (t.get("args") or []):
                    at = str(a.get("type") or "str")
                    an = str(a.get("name") or "")
                    dv = a.get("default") if "default" in a and a.get("default") is not None else _coerce_arg_default(at)
                    if an:
                        args[an] = dv
                auto_tests.append({"tool": t.get("name"), "args": args, "expect_ok": True})
            tests = auto_tests

        plan = {
            "skill_name": spec.get("skill_name"),
            "description": spec.get("description") or "",
            "tools": [{"name": t.get("name"), "description": t.get("description"), "args": t.get("args") or []} for t in tools],
            "tests": tests,
        }
        if dry_run:
            return {"ok": True, "dry_run": True, "plan": plan, "elapsed_ms": int((time.time() - started_at) * 1000)}

        scaffold_out = scaffold_skill.invoke({
            "skill_name": plan["skill_name"],
            "tools": plan["tools"],
            "description": plan["description"],
            "overwrite": overwrite,
        })
        scaffold_data = _safe_json_loads(scaffold_out)
        if not isinstance(scaffold_data, dict):
            raise HTTPException(status_code=500, detail=f"脚手架生成失败: {scaffold_out}")

        write_results = []
        for t in tools:
            tool_name = str(t.get("name") or "").strip()
            if not tool_name:
                continue
            code = _build_tool_module(t)
            root = _get_project_root()
            fp = os.path.join(root, "app", "auto_skills", plan["skill_name"], "scripts", f"{tool_name}.py")
            r = write_tool_code.invoke({"file_path": fp, "code": code})
            write_results.append({"tool": tool_name, "file": fp, "result": r})

        loadability = _run_loadability("auto_skills", plan["skill_name"])
        test_results = _run_tool_tests(plan["skill_name"], tests)

        shared.put_input("__RELOAD_SKILLS__")

        return {
            "ok": True,
            "dry_run": False,
            "plan": plan,
            "scaffold": scaffold_data,
            "write_results": write_results,
            "loadability": loadability,
            "tests": test_results,
            "elapsed_ms": int((time.time() - started_at) * 1000),
        }
    except HTTPException:
        raise
    except Exception as e:
        tb = traceback.format_exc(limit=8)
        raise HTTPException(status_code=500, detail=f"{e}\n{tb}")

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
