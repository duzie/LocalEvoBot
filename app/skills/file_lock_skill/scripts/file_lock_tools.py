from langchain_core.tools import tool
import os
import json
import time
import hashlib
from typing import Dict, Any

def _get_base_dir():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def _get_lock_dir():
    base = os.path.join(_get_base_dir(), "app", "data", "locks")
    os.makedirs(base, exist_ok=True)
    return base

def _lock_key(target: str) -> str:
    text = str(target or "").strip().lower()
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def _lock_path(target: str) -> str:
    return os.path.join(_get_lock_dir(), _lock_key(target) + ".lock")

def _read_lock(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _is_expired(payload: Dict[str, Any]) -> bool:
    try:
        expires_at = float(payload.get("expires_at") or 0)
        if expires_at <= 0:
            return False
        return time.time() > expires_at
    except Exception:
        return False

@tool
def acquire_file_lock(target_path: str, owner: str = "", ttl: int = 900, allow_reuse: bool = False) -> Dict[str, Any]:
    """
    获取文件锁。
    """
    target = str(target_path or "").strip()
    if not target:
        return {"ok": False, "error": "target_path 不能为空"}
    path = _lock_path(target)
    now = time.time()
    payload = {
        "owner": owner or "",
        "target": os.path.abspath(target),
        "created_at": now,
        "expires_at": now + max(1, int(ttl or 1))
    }
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False))
        return {"ok": True, "lock_path": path, "payload": payload}
    except FileExistsError:
        existing = _read_lock(path)
        if existing and _is_expired(existing):
            try:
                os.remove(path)
            except Exception:
                return {"ok": False, "error": "锁已过期但无法移除", "existing": existing, "lock_path": path}
            return acquire_file_lock(target_path, owner, ttl, allow_reuse)
        if allow_reuse and existing and str(existing.get("owner") or "") == str(owner or ""):
            return {"ok": True, "lock_path": path, "payload": existing, "reused": True}
        return {"ok": False, "error": "锁已被占用", "existing": existing, "lock_path": path}
    except Exception as e:
        return {"ok": False, "error": str(e), "lock_path": path}

@tool
def release_file_lock(target_path: str, owner: str = "") -> Dict[str, Any]:
    """
    释放文件锁。
    """
    target = str(target_path or "").strip()
    if not target:
        return {"ok": False, "error": "target_path 不能为空"}
    path = _lock_path(target)
    if not os.path.exists(path):
        return {"ok": True, "released": False, "message": "锁不存在", "lock_path": path}
    existing = _read_lock(path)
    if owner and existing and str(existing.get("owner") or "") != str(owner or ""):
        return {"ok": False, "error": "owner 不匹配", "existing": existing, "lock_path": path}
    try:
        os.remove(path)
        return {"ok": True, "released": True, "lock_path": path}
    except Exception as e:
        return {"ok": False, "error": str(e), "lock_path": path}

@tool
def renew_file_lock(target_path: str, owner: str = "", ttl: int = 900) -> Dict[str, Any]:
    """
    续租文件锁。
    """
    target = str(target_path or "").strip()
    if not target:
        return {"ok": False, "error": "target_path 不能为空"}
    path = _lock_path(target)
    if not os.path.exists(path):
        return {"ok": False, "error": "锁不存在", "lock_path": path}
    existing = _read_lock(path)
    if owner and existing and str(existing.get("owner") or "") != str(owner or ""):
        return {"ok": False, "error": "owner 不匹配", "existing": existing, "lock_path": path}
    now = time.time()
    existing["expires_at"] = now + max(1, int(ttl or 1))
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps(existing, ensure_ascii=False))
        return {"ok": True, "lock_path": path, "payload": existing}
    except Exception as e:
        return {"ok": False, "error": str(e), "lock_path": path}

@tool
def check_file_lock(target_path: str) -> Dict[str, Any]:
    """
    检查文件锁。
    """
    target = str(target_path or "").strip()
    if not target:
        return {"ok": False, "error": "target_path 不能为空"}
    path = _lock_path(target)
    if not os.path.exists(path):
        return {"ok": True, "locked": False, "lock_path": path}
    existing = _read_lock(path)
    return {"ok": True, "locked": True, "lock_path": path, "payload": existing, "expired": _is_expired(existing)}
