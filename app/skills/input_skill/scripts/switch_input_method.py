from langchain_core.tools import tool
import pyautogui
import time
import ctypes

@tool
def switch_input_method(action: str = "toggle"):
    """
    切换或设置输入法状态。

    Args:
        action: 
            - "toggle": 模拟按下 Shift 键切换中英文 (默认)
            - "shift": 同 "toggle"
            - "win_space": 模拟 Win+Space 切换键盘布局
            - "ctrl_space": 模拟 Ctrl+Space 切换输入法
    """
    try:
        if action in ["toggle", "shift"]:
            pyautogui.press('shift')
            return "已模拟按下 Shift 键 (切换中英文)"
        elif action == "win_space":
            pyautogui.hotkey('win', 'space')
            return "已模拟 Win+Space (切换键盘布局)"
        elif action == "ctrl_space":
            pyautogui.hotkey('ctrl', 'space')
            return "已模拟 Ctrl+Space (切换输入法)"
        else:
            return f"未知动作: {action}"
    except Exception as e:
        return f"切换输入法失败: {e}"
