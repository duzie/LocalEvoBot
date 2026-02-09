from langchain_core.tools import tool
import pyautogui
import time

@tool
def press_key(key: str, times: int = 1):
    """
    模拟按下特定的键盘按键。
    
    Args:
        key: 按键名称，例如 "enter", "tab", "esc", "backspace", "space", "up", "down", "left", "right"
             也支持组合键如 "ctrl+c" (尚未完全支持解析，建议仅用单键)
        times: 按下次数，默认为 1
    """
    try:
        time.sleep(0.2)
        valid_keys = ['enter', 'tab', 'esc', 'backspace', 'space', 'up', 'down', 'left', 'right', 
                      'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12',
                      'pageup', 'pagedown', 'home', 'end', 'insert', 'delete']
        
        key_lower = key.lower()
        if key_lower not in valid_keys and len(key_lower) > 1:
             return f"不支持的按键: {key}。请仅使用单功能键。"

        pyautogui.press(key_lower, presses=times)
        return f"已按下 {times} 次 {key}"
    except Exception as e:
        return f"按键失败: {e}"
