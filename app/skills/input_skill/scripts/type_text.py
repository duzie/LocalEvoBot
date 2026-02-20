from langchain_core.tools import tool
import pyautogui
import time
import pyperclip
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
def type_text(text: str, mode: str = "type", press_enter: bool = False, clear_before_input: bool = False):
    """
    输入文本。
    
    Args:
        text: 要输入的文本内容。
        mode: 输入模式。
            - "type": 模拟按键逐字输入 (默认)。
            - "paste": 使用剪贴板粘贴 (推荐，避开输入法)。
        press_enter: 是否在输入完成后按下回车键。
        clear_before_input: 是否在输入前先全选 (Ctrl+A)，常用于覆盖输入框原有内容。
    """
    tool_name = "type_text"
    try:
        if text is None:
            return _error_payload("invalid_args", "text 不能为空", tool=tool_name)
        time.sleep(0.5)
        
        # 自动处理 {ENTER} 后缀
        if text.endswith("{ENTER}"):
            text = text[:-7]
            press_enter = True
            
        if clear_before_input:
            pyautogui.hotkey('ctrl', 'a')
            time.sleep(0.1)
            
        mode_val = str(mode or "type").strip()
        if mode_val == "paste":
            # 备份剪贴板
            try:
                original = pyperclip.paste()
            except:
                original = ""
            
            pyperclip.copy(text)
            # Ctrl+V
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.1)
        else:
            pyautogui.write(text, interval=0.05)
            
        msg = f"已输入文本: {text} (模式: {mode_val})"
        if press_enter:
            time.sleep(0.1)
            pyautogui.press('enter')
            msg += " 并按下了回车"
        _emit_event(tool_name, "type", mode=mode_val, press_enter=bool(press_enter))
        return _ok_payload(msg, mode=mode_val, press_enter=bool(press_enter))
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("type_failed", str(e), tool=tool_name)
