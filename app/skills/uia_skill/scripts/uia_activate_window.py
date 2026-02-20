from langchain_core.tools import tool
import platform
import time
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
def uia_activate_window(window_title: str):
    """
    激活并前置指定窗口（如果窗口被最小化，会尝试还原）。
    当 uia_click_control 提示“未找到匹配控件”但 uia_list_controls 能看到窗口时，请先使用此技能。

    Args:
        window_title: 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
    """
    tool_name = "uia_activate_window"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows UI Automation", tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        # 使用 title_re 进行模糊匹配
        window = desktop.window(title_re=window_title)
        
        if not window.exists(timeout=2):
            msg = f"未找到窗口: {window_title}"
            if not _is_admin():
                msg += "\n[提示] 当前 Agent 非管理员权限，可能无法看到管理员权限运行的窗口。"
            return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
            
        # 尝试还原和激活
        # 注意: minimize() / restore() 等方法有时需要 wrapper
        # 这里尝试直接调用 set_focus()，pywinauto 通常会自动处理 restore
        try:
            if window.get_show_state() == 2: # 2 = Minimized
                window.restore()
        except Exception:
            # 如果 get_show_state 失败，盲试 restore
            try:
                window.restore()
            except:
                pass
        
        window.set_focus()
        _emit_event(tool_name, "activate", window_title=window_title)
        return _ok_payload("已激活窗口", window_title=window_title)
    except Exception as e:
        msg = f"激活窗口失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 目标窗口可能拥有更高权限 (管理员)，请尝试以管理员身份运行此 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("activate_failed", msg, tool=tool_name, is_admin=_is_admin())
