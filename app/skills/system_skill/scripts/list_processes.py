from langchain_core.tools import tool
import subprocess
import platform
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

@tool
def list_processes(keyword: str = None, as_json: bool = False):
    """
    列出当前系统的进程清单，并可按关键词过滤。
    
    Args:
        keyword: (可选) 关键词筛选，忽略大小写
        as_json: (可选) 是否以 JSON 数组返回
    """
    tool_name = "list_processes"
    system = platform.system()
    try:
        if system == "Windows":
            output = subprocess.run("tasklist", shell=True, capture_output=True, text=True, encoding="gbk", errors="ignore", timeout=10).stdout
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            lines = [line for line in lines if not line.lower().startswith("image name") and not set(line) == {"="}]
            if keyword:
                kw = keyword.lower()
                lines = [line for line in lines if kw in line.lower()]
            payload = _ok_payload("已列出进程", processes=lines)
            _emit_event(tool_name, "list", count=len(lines))
            return json.dumps(payload, ensure_ascii=False) if as_json else payload
        if system in ["Darwin", "Linux"]:
            output = subprocess.run(["ps", "-A", "-o", "pid,comm"], capture_output=True, text=True, timeout=10).stdout
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if keyword:
                kw = keyword.lower()
                lines = [line for line in lines if kw in line.lower()]
            payload = _ok_payload("已列出进程", processes=lines)
            _emit_event(tool_name, "list", count=len(lines))
            return json.dumps(payload, ensure_ascii=False) if as_json else payload
        return _error_payload("unsupported_platform", f"不支持的操作系统: {system}", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("list_processes_failed", str(e), tool=tool_name)
