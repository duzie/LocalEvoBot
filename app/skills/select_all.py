from langchain_core.tools import tool
import pyautogui
import time

@tool
def select_all():
    """
    全选当前焦点输入框中的文本 (Ctrl+A)。
    常用于在输入新内容前清除旧内容（全选后直接输入即可覆盖）。
    """
    try:
        time.sleep(0.1)
        pyautogui.hotkey('ctrl', 'a')
        return "已执行全选 (Ctrl+A)"
    except Exception as e:
        return f"全选失败: {e}"
