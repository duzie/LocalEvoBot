from langchain_core.tools import tool
import pyautogui

@tool
def show_desktop():
    """
    显示桌面，点击屏幕右下角的“显示桌面”区域。
    """
    try:
        width, height = pyautogui.size()
        x = max(0, width - 5)
        y = max(0, height - 5)
        pyautogui.moveTo(x, y, duration=0.2)
        pyautogui.click()
        return "已显示桌面"
    except Exception as e:
        return f"显示桌面失败: {e}"
