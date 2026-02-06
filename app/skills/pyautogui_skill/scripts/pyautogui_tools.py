from langchain_core.tools import tool
import pyautogui
import time
import os
from typing import Optional

# 设置PyAutoGUI的基本参数
pyautogui.PAUSE = 0.5  # 每次操作后的暂停时间
pyautogui.FAILSAFE = True  # 启用故障安全模式

@tool
def gui_click_element(x: int, y: int):
    """
    点击屏幕上的指定坐标位置。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    try:
        pyautogui.click(x, y)
        return f"已点击坐标 ({x}, {y})"
    except Exception as e:
        return f"点击失败: {str(e)}"

@tool
def gui_double_click(x: int, y: int):
    """
    在指定坐标位置双击。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    try:
        pyautogui.doubleClick(x, y)
        return f"已双击坐标 ({x}, {y})"
    except Exception as e:
        return f"双击失败: {str(e)}"

@tool
def gui_right_click(x: int, y: int):
    """
    在指定坐标位置右键点击。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    try:
        pyautogui.rightClick(x, y)
        return f"已右键点击坐标 ({x}, {y})"
    except Exception as e:
        return f"右键点击失败: {str(e)}"

@tool
def gui_move_mouse(x: int, y: int):
    """
    移动鼠标到指定坐标位置。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    try:
        pyautogui.moveTo(x, y)
        return f"鼠标已移动到坐标 ({x}, {y})"
    except Exception as e:
        return f"移动鼠标失败: {str(e)}"

@tool
def gui_scroll(units: int):
    """
    滚动鼠标滚轮。
    
    Args:
        units: 滚动单位，正数向上滚动，负数向下滚动
    """
    try:
        pyautogui.scroll(units)
        return f"已滚动 {units} 单位"
    except Exception as e:
        return f"滚动失败: {str(e)}"

@tool
def gui_type_text(text: str):
    """
    输入文本。
    
    Args:
        text: 要输入的文本
    """
    try:
        pyautogui.write(text)
        return f"已输入文本: {text}"
    except Exception as e:
        return f"输入文本失败: {str(e)}"

@tool
def gui_press_key(key: str):
    """
    按下指定按键。
    
    Args:
        key: 按键名称 (如 'enter', 'tab', 'esc', 'win', 'ctrl', 'alt', 'shift' 等)
    """
    try:
        pyautogui.press(key)
        return f"已按下按键: {key}"
    except Exception as e:
        return f"按键失败: {str(e)}"

@tool
def gui_hotkey(*keys: str):
    """
    按下组合键。
    
    Args:
        keys: 按键序列 (如 'ctrl', 'c' 或 'alt', 'tab')
    """
    try:
        pyautogui.hotkey(*keys)
        return f"已按下组合键: {'+'.join(keys)}"
    except Exception as e:
        return f"组合键失败: {str(e)}"

@tool
def gui_wait(seconds: float):
    """
    等待指定秒数。
    
    Args:
        seconds: 等待的秒数
    """
    try:
        time.sleep(seconds)
        return f"已等待 {seconds} 秒"
    except Exception as e:
        return f"等待失败: {str(e)}"

@tool
def gui_get_screen_size():
    """
    获取屏幕尺寸。
    """
    try:
        width, height = pyautogui.size()
        return f"屏幕尺寸: {width} x {height}"
    except Exception as e:
        return f"获取屏幕尺寸失败: {str(e)}"

@tool
def gui_take_screenshot(filename: str = "screenshot.png"):
    """
    截取屏幕截图。
    
    Args:
        filename: 保存截图的文件名
    """
    try:
        screenshot = pyautogui.screenshot()
        screenshot.save(filename)
        abs_path = os.path.abspath(filename)
        return f"截图已保存至: {abs_path}"
    except Exception as e:
        return f"截图失败: {str(e)}"

@tool
def gui_find_and_click(image_path: str, confidence: float = 0.8):
    """
    查找屏幕上的图像并点击其中心位置。
    
    Args:
        image_path: 图像文件路径
        confidence: 匹配置信度 (0.0-1.0)
    """
    try:
        import cv2
        # 尝试在屏幕上找到指定图像
        location = pyautogui.locateOnScreen(image_path, confidence=confidence)
        if location:
            center = pyautogui.center(location)
            pyautogui.click(center)
            x, y = center
            return f"找到图像并点击中心位置: ({x}, {y})"
        else:
            return f"未找到匹配图像: {image_path} (置信度: {confidence})"
    except Exception as e:
        return f"查找并点击失败: {str(e)}"

@tool
def gui_focus_window(title: str):
    """
    激活指定标题的窗口。
    
    Args:
        title: 窗口标题的关键字
    """
    try:
        import pygetwindow as gw
        windows = gw.getWindowsWithTitle(title)
        if windows:
            window = windows[0]
            window.activate()
            return f"已激活窗口: {window.title}"
        else:
            return f"未找到包含关键字 '{title}' 的窗口"
    except Exception as e:
        return f"窗口激活失败: {str(e)}"