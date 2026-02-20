import json
from datetime import datetime
from typing import Any, Dict

from langchain_core.tools import tool

from . import _playwright_core as core
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
def playwright_start_network_capture(clear_logs: bool = True, max_entries: int = 500):
    """
    开始抓包并记录请求响应日志。
    """
    tool_name = "playwright_start_network_capture"
    _, err = core._ensure_page(headless=False)
    if err:
        _emit_event(tool_name, "error", error=str(err))
        return _error_payload("ensure_page_failed", str(err), tool=tool_name)
    try:
        core._network_log_limit = max(50, min(int(max_entries or 500), 5000))
        if clear_logs:
            core._network_logs = []
        core._network_capture_on = True
        core._ensure_network_listeners(core._page)
        _emit_event(tool_name, "start", max_entries=core._network_log_limit)
        return _ok_payload("已开始抓包", max_entries=core._network_log_limit)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("start_failed", str(e), tool=tool_name)


@tool
def playwright_stop_network_capture():
    """
    停止抓包。
    """
    tool_name = "playwright_stop_network_capture"
    core._network_capture_on = False
    _emit_event(tool_name, "stop")
    return _ok_payload("已停止抓包")


@tool
def playwright_get_network_logs(limit: int = 200, as_json: bool = True):
    """
    获取抓包日志。
    """
    tool_name = "playwright_get_network_logs"
    try:
        safe_limit = max(1, min(int(limit or 200), 2000))
        data = core._network_logs[-safe_limit:]
        _emit_event(tool_name, "get_logs", count=len(data))
        if as_json:
            return _ok_payload("已获取抓包日志", logs=data)
        text = "\n".join(
            [f"{d.get('type')} {d.get('method')} {d.get('status','')} {d.get('url')}" for d in data]
        )
        return _ok_payload("已获取抓包日志", text=text)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("get_logs_failed", str(e), tool=tool_name)


@tool
def playwright_clear_network_logs():
    """
    清空抓包日志。
    """
    tool_name = "playwright_clear_network_logs"
    core._network_logs = []
    _emit_event(tool_name, "clear")
    return _ok_payload("已清空抓包日志")
