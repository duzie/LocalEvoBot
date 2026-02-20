from langchain_core.tools import tool
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
def uia_find_control(window_title: str = None, control_type: str = None, title: str = None, auto_id: str = None, found_index: int = 0):
    """
    使用 Windows UI Automation 定位控件并返回坐标信息。

    Args:
        window_title: (可选) 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
        control_type: (可选) 控件类型，例如 "Button", "Edit", "ListItem"
        title: (可选) 控件标题或名称
        auto_id: (可选) 控件自动化 ID
        found_index: (可选) 当匹配到多个控件时，选择第几个（从0开始）。默认为0。
    """
    tool_name = "uia_find_control"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows UI Automation", tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                return _error_payload("window_not_found", f"未找到窗口: {window_title}", tool=tool_name, found=False)
        criteria = {}
        if title:
            criteria["title"] = title
        if control_type:
            criteria["control_type"] = control_type
        if auto_id:
            criteria["auto_id"] = auto_id
        if found_index < 0:
            found_index = 0
        target = root.child_window(found_index=found_index, **criteria)
        if not target.exists(timeout=1):
            return _error_payload("control_not_found", "未找到匹配控件", tool=tool_name, found=False)
        rect = target.rectangle()
        x = int((rect.left + rect.right) / 2)
        y = int((rect.top + rect.bottom) / 2)
        _emit_event(tool_name, "found", x=x, y=y)
        return _ok_payload(
            "已找到控件",
            found=True,
            x=x,
            y=y,
            rect={"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
        )
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("uia_find_failed", str(e), tool=tool_name)
