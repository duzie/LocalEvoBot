from langchain_core.tools import tool
import platform
import ctypes
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

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

@tool
def uia_click_control(window_title: str = None, control_type: str = None, title: str = None, auto_id: str = None, clicks: int = 1, found_index: int = 0):
    """
    使用 Windows UI Automation 直接点击控件。
    
    Args:
        window_title: (可选) 窗口标题或正则
    """
    tool_name = "uia_click_control"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows UI Automation", tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                msg = f"未找到窗口: {window_title}"
                if not _is_admin():
                    msg += "\n[提示] 权限提示：若目标窗口是管理员权限，请尝试以管理员身份运行 Agent。"
                return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
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
            return _error_payload("control_not_found", "未找到匹配控件", tool=tool_name)
        click_times = max(1, int(clicks or 1))
        for _ in range(click_times):
            target.click_input()
        _emit_event(tool_name, "click", clicks=click_times)
        return _ok_payload("已点击控件", clicks=click_times)
    except Exception as e:
        msg = f"控件点击失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 操作失败可能是因为权限不足。若目标程序以管理员运行，请以管理员身份运行此 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("uia_click_failed", msg, tool=tool_name, is_admin=_is_admin())
