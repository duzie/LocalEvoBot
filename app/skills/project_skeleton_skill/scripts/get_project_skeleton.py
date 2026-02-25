from langchain_core.tools import tool
import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import hashlib

def _get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

def _get_cache_dir():
    base_dir = _get_base_dir()
    cache_dir = os.path.join(base_dir, "app", "data", "project_skeleton")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir

def _get_legacy_cache_path():
    base_dir = _get_base_dir()
    data_dir = os.path.join(base_dir, "app", "data")
    return os.path.join(data_dir, "project_skeleton.json")

def _get_project_cache_path(root_path: str):
    cache_dir = _get_cache_dir()
    key = hashlib.sha1(root_path.lower().encode("utf-8")).hexdigest()
    return os.path.join(cache_dir, f"{key}.json")

def _load_project_cache(root_path: str) -> Dict[str, Any]:
    path = _get_project_cache_path(root_path)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _load_legacy_cache_for_root(root_path: str) -> Dict[str, Any]:
    path = _get_legacy_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {}
        projects = data.get("projects")
        if isinstance(projects, dict):
            item = projects.get(root_path)
            return item if isinstance(item, dict) else {}
        return {}
    except Exception:
        return {}

def _save_project_cache(root_path: str, payload: Dict[str, Any]):
    path = _get_project_cache_path(root_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        return

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _build_skeleton(root_path: str, max_depth: int, include_hidden: bool, max_entries: int):
    root_path = os.path.abspath(root_path)
    entries: List[Dict[str, Any]] = []
    top_dirs: List[str] = []
    entrypoints: List[str] = []
    entrypoint_names = {
        "main.py",
        "app.py",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "README.md",
    }
    extra_entrypoints = {
        os.path.join("gateway", "index.js"),
        os.path.join("web", "backend", "main.py"),
        os.path.join("web", "frontend", "public", "index.html"),
    }
    for current, dirs, files in os.walk(root_path):
        rel = os.path.relpath(current, root_path)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > max_depth:
            dirs[:] = []
            continue
        if not include_hidden:
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            files = [f for f in files if not f.startswith(".")]
        if depth == 0:
            top_dirs.extend([d for d in dirs if d not in top_dirs])
        for d in dirs:
            entries.append({"path": os.path.join(rel, d).replace("\\", "/"), "type": "dir", "depth": depth})
            if len(entries) >= max_entries:
                return entries, top_dirs, entrypoints
        for f in files:
            rel_path = os.path.join(rel, f).replace("\\", "/")
            entries.append({"path": rel_path, "type": "file", "depth": depth})
            if f in entrypoint_names or rel_path in extra_entrypoints:
                entrypoints.append(rel_path)
            if len(entries) >= max_entries:
                return entries, top_dirs, entrypoints
    return entries, top_dirs, entrypoints

@tool
def get_project_skeleton(
    root_path: str,
    force_rebuild: bool = False,
    max_depth: int = 3,
    max_entries: int = 500,
    include_hidden: bool = False
) -> Dict[str, Any]:
    """
    生成并缓存项目骨架（目录/模块地图），优先复用本地缓存。
    
    Args:
        root_path: 项目根目录
        force_rebuild: 是否强制重建
        max_depth: 最大扫描深度
        max_entries: 最大条目数
        include_hidden: 是否包含隐藏文件/目录
    """
    if not root_path:
        return _error_payload("missing_root", "root_path 不能为空")
    root_path = os.path.abspath(root_path)
    if not os.path.exists(root_path):
        return _error_payload("not_found", f"路径不存在: {root_path}", root=root_path)
    if not os.path.isdir(root_path):
        return _error_payload("not_directory", f"路径不是目录: {root_path}", root=root_path)
    if not force_rebuild:
        item = _load_project_cache(root_path)
        if not item:
            legacy_item = _load_legacy_cache_for_root(root_path)
            if legacy_item:
                _save_project_cache(root_path, legacy_item)
                item = legacy_item
        if item:
        return _ok_payload(
            "已命中项目骨架缓存",
            cache_hit=True,
            cache_path=_get_project_cache_path(root_path),
            root=root_path,
            updated_at=item.get("updated_at"),
            entries=item.get("entries") or [],
            entrypoints=item.get("entrypoints") or [],
            top_level_dirs=item.get("top_level_dirs") or [],
            total_entries=item.get("total_entries") or 0,
            max_depth=item.get("max_depth"),
            include_hidden=item.get("include_hidden"),
        )
    entries, top_dirs, entrypoints = _build_skeleton(
        root_path=root_path,
        max_depth=max(0, int(max_depth or 0)),
        include_hidden=bool(include_hidden),
        max_entries=max(1, int(max_entries or 1)),
    )
    updated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "root": root_path,
        "updated_at": updated_at,
        "entries": entries,
        "entrypoints": entrypoints,
        "top_level_dirs": top_dirs,
        "total_entries": len(entries),
        "max_depth": max(0, int(max_depth or 0)),
        "include_hidden": bool(include_hidden),
    }
    _save_project_cache(root_path, payload)
    return _ok_payload(
        "已生成项目骨架并缓存",
        cache_hit=False,
        cache_path=_get_project_cache_path(root_path),
        **payload
    )
