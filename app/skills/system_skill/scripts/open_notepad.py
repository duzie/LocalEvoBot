from langchain_core.tools import tool
import subprocess
import platform
import os
import time
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
def open_notepad():
    """
    打开 Windows 记事本程序。无需参数。
    如果是 macOS，则尝试打开 TextEdit。
    """
    tool_name = "open_notepad"
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen("notepad.exe")
            _emit_event(tool_name, "open", app="notepad")
            return _ok_payload("已启动记事本", app="notepad.exe")
        elif system == "Darwin":
            subprocess.Popen(["open", "-a", "TextEdit"])
            _emit_event(tool_name, "open", app="TextEdit")
            return _ok_payload("已启动 TextEdit")
        else:
            return _error_payload("unsupported_platform", f"不支持的操作系统: {system}", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("open_failed", str(e), tool=tool_name)

@tool
def read_notepad_text(window_title: str = None, file_path: str = None, try_open: bool = True):
    """
    读取记事本中的文本内容或直接读取文件内容。

    Args:
        window_title: 记事本窗口标题正则，未提供时自动匹配包含“记事本/Notepad”的窗口
        file_path: 文件路径，若提供且存在则直接读取文件内容
        try_open: 当未找到窗口但提供了 file_path 时，尝试用记事本打开并读取
    """
    tool_name = "read_notepad_text"
    system = platform.system()
    if system != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows", tool=tool_name)
    if file_path and os.path.exists(file_path):
        try:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception:
                with open(file_path, "r", encoding="gbk", errors="ignore") as f:
                    content = f.read()
            _emit_event(tool_name, "read_file", path=file_path)
            return _ok_payload("读取成功", text=content, source="file", path=file_path)
        except Exception as e:
            _emit_event(tool_name, "error", error=str(e))
            return _error_payload("read_file_failed", str(e), tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        pattern = window_title or r".*(记事本|Notepad).*"
        win = desktop.window(title_re=pattern)
        if not win.exists(timeout=2):
            if file_path and try_open:
                try:
                    subprocess.Popen(["notepad.exe", file_path])
                    time.sleep(1.5)
                    base = os.path.basename(file_path)
                    alt = rf".*{base}.*"
                    win = desktop.window(title_re=alt)
                    if not win.exists(timeout=3):
                        win = desktop.window(title_re=r".*(记事本|Notepad).*")
                except Exception:
                    pass
            else:
                return _error_payload("window_not_found", f"未找到记事本窗口: {pattern}", tool=tool_name)
        try:
            win.set_focus()
        except Exception:
            pass
        try:
            edit = win.child_window(control_type="Edit")
            if edit.exists(timeout=1):
                text = edit.window_text()
                _emit_event(tool_name, "read_window")
                return _ok_payload("读取成功", text=text, source="window")
        except Exception:
            pass
        try:
            edit_list = win.descendants(control_type="Edit")
            if edit_list:
                text = edit_list[0].window_text()
                _emit_event(tool_name, "read_window")
                return _ok_payload("读取成功", text=text, source="window")
        except Exception:
            pass
        return _error_payload("text_control_not_found", "未找到可读取的文本控件", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("read_failed", str(e), tool=tool_name)
