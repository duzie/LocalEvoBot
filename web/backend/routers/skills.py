from fastapi import APIRouter, HTTPException
import os
import importlib
import pkgutil
import inspect
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
