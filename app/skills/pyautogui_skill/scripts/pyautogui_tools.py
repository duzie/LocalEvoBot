from langchain_core.tools import tool
import pyautogui
import time
import os
import json
from datetime import datetime
from typing import Optional, Any, Dict
from web.backend.shared import shared

# 设置PyAutoGUI的基本参数
pyautogui.PAUSE = 0.5  # 每次操作后的暂停时间
pyautogui.FAILSAFE = True  # 启用故障安全模式

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
def gui_click_element(x: int, y: int):
    """
    点击屏幕上的指定坐标位置。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    tool_name = "gui_click_element"
    try:
        pyautogui.click(x, y)
        _emit_event(tool_name, "click", x=x, y=y)
        return _ok_payload("已点击坐标", x=x, y=y)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("click_failed", str(e), tool=tool_name)

@tool
def gui_double_click(x: int, y: int):
    """
    在指定坐标位置双击。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    tool_name = "gui_double_click"
    try:
        pyautogui.doubleClick(x, y)
        _emit_event(tool_name, "double_click", x=x, y=y)
        return _ok_payload("已双击坐标", x=x, y=y)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("double_click_failed", str(e), tool=tool_name)

@tool
def gui_right_click(x: int, y: int):
    """
    在指定坐标位置右键点击。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    tool_name = "gui_right_click"
    try:
        pyautogui.rightClick(x, y)
        _emit_event(tool_name, "right_click", x=x, y=y)
        return _ok_payload("已右键点击坐标", x=x, y=y)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("right_click_failed", str(e), tool=tool_name)

@tool
def gui_move_mouse(x: int, y: int):
    """
    移动鼠标到指定坐标位置。
    
    Args:
        x: X坐标
        y: Y坐标
    """
    tool_name = "gui_move_mouse"
    try:
        pyautogui.moveTo(x, y)
        _emit_event(tool_name, "move", x=x, y=y)
        return _ok_payload("鼠标已移动到坐标", x=x, y=y)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("move_failed", str(e), tool=tool_name)

@tool
def gui_scroll(units: int):
    """
    滚动鼠标滚轮。
    
    Args:
        units: 滚动单位，正数向上滚动，负数向下滚动
    """
    tool_name = "gui_scroll"
    try:
        units_val = int(units or 0)
        pyautogui.scroll(units_val)
        _emit_event(tool_name, "scroll", units=units_val)
        return _ok_payload("已滚动", units=units_val)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("scroll_failed", str(e), tool=tool_name)

@tool
def gui_type_text(text: str):
    """
    输入文本。
    
    Args:
        text: 要输入的文本
    """
    tool_name = "gui_type_text"
    try:
        if text is None:
            return _error_payload("invalid_args", "text 不能为空", tool=tool_name)
        pyautogui.write(text)
        _emit_event(tool_name, "type")
        return _ok_payload("已输入文本")
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("type_failed", str(e), tool=tool_name)

@tool
def gui_press_key(key: str):
    """
    按下指定按键。
    
    Args:
        key: 按键名称 (如 'enter', 'tab', 'esc', 'win', 'ctrl', 'alt', 'shift' 等)
    """
    tool_name = "gui_press_key"
    try:
        key_val = str(key or "").strip()
        if not key_val:
            return _error_payload("invalid_args", "key 不能为空", tool=tool_name)
        pyautogui.press(key_val)
        _emit_event(tool_name, "press", key=key_val)
        return _ok_payload("已按下按键", key=key_val)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("press_failed", str(e), tool=tool_name)

@tool
def gui_hotkey(*keys: str):
    """
    按下组合键。
    
    Args:
        keys: 按键序列 (如 'ctrl', 'c' 或 'alt', 'tab')
    """
    tool_name = "gui_hotkey"
    try:
        keys_list = [str(k or "").strip() for k in (keys or []) if str(k or "").strip()]
        if not keys_list:
            return _error_payload("invalid_args", "keys 不能为空", tool=tool_name)
        pyautogui.hotkey(*keys_list)
        _emit_event(tool_name, "hotkey", keys=keys_list)
        return _ok_payload("已按下组合键", keys=keys_list)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("hotkey_failed", str(e), tool=tool_name)

@tool
def gui_wait(seconds: float):
    """
    等待指定秒数。
    
    Args:
        seconds: 等待的秒数
    """
    tool_name = "gui_wait"
    try:
        seconds_val = float(seconds or 0)
        if seconds_val < 0:
            return _error_payload("invalid_args", "seconds 不能为负数", tool=tool_name)
        time.sleep(seconds_val)
        _emit_event(tool_name, "wait", seconds=seconds_val)
        return _ok_payload("已等待", seconds=seconds_val)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("wait_failed", str(e), tool=tool_name)

@tool
def gui_get_screen_size():
    """
    获取屏幕尺寸。
    """
    tool_name = "gui_get_screen_size"
    try:
        width, height = pyautogui.size()
        _emit_event(tool_name, "screen_size", width=width, height=height)
        return _ok_payload("屏幕尺寸", width=width, height=height)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("screen_size_failed", str(e), tool=tool_name)

@tool
def gui_take_screenshot(filename: str = "screenshot.png"):
    """
    截取屏幕截图。
    
    Args:
        filename: 保存截图的文件名
    """
    tool_name = "gui_take_screenshot"
    try:
        name = str(filename or "").strip()
        if not name:
            return _error_payload("invalid_args", "filename 不能为空", tool=tool_name)
        screenshot = pyautogui.screenshot()
        screenshot.save(name)
        abs_path = os.path.abspath(name)
        _emit_event(tool_name, "screenshot", path=abs_path)
        return _ok_payload("截图已保存", path=abs_path)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("screenshot_failed", str(e), tool=tool_name)

@tool
def gui_find_and_click(image_path: str, confidence: float = 0.8):
    """
    查找屏幕上的图像并点击其中心位置。
    
    Args:
        image_path: 图像文件路径
        confidence: 匹配置信度 (0.0-1.0)
    """
    tool_name = "gui_find_and_click"
    try:
        path = str(image_path or "").strip()
        if not path:
            return _error_payload("invalid_args", "image_path 不能为空", tool=tool_name)
        import cv2
        conf_val = float(confidence or 0.8)
        location = pyautogui.locateOnScreen(path, confidence=conf_val)
        if location:
            center = pyautogui.center(location)
            pyautogui.click(center)
            x, y = center
            _emit_event(tool_name, "click", x=x, y=y, image_path=path, confidence=conf_val)
            return _ok_payload("找到图像并点击中心位置", x=x, y=y, image_path=path, confidence=conf_val)
        _emit_event(tool_name, "not_found", image_path=path, confidence=conf_val)
        return _error_payload("image_not_found", "未找到匹配图像", tool=tool_name, image_path=path, confidence=conf_val)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("find_and_click_failed", str(e), tool=tool_name)

@tool
def gui_focus_window(title: str):
    """
    激活指定标题的窗口。
    
    Args:
        title: 窗口标题的关键字
    """
    tool_name = "gui_focus_window"
    try:
        import pygetwindow as gw
        title_val = str(title or "").strip()
        if not title_val:
            return _error_payload("invalid_args", "title 不能为空", tool=tool_name)
        windows = gw.getWindowsWithTitle(title_val)
        if windows:
            window = windows[0]
            window.activate()
            _emit_event(tool_name, "focus", title=window.title)
            return _ok_payload("已激活窗口", title=window.title)
        return _error_payload("window_not_found", f"未找到包含关键字 '{title_val}' 的窗口", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("focus_failed", str(e), tool=tool_name)
