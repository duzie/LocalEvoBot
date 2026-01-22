from langchain_core.tools import tool
import pyautogui

@tool
def mouse_click(x: int, y: int, clicks: int = 1, button: str = 'left'):
    """
    模拟鼠标点击。
    
    Args:
        x: 屏幕 X 坐标
        y: 屏幕 Y 坐标
        clicks: 点击次数，默认为 1
        button: 鼠标按键，'left', 'middle', 'right'，默认为 'left'
    """
    try:
        pyautogui.moveTo(x, y, duration=0.5)
        pyautogui.click(clicks=clicks, button=button)
        return f"已在坐标 ({x}, {y}) 点击鼠标 {button} 键 {clicks} 次。"
    except Exception as e:
        return f"鼠标操作失败: {e}"
