from langchain_core.tools import tool
import time
import json
import os
from datetime import datetime, timezone

# Lazy globals to maintain session across tool calls
_playwright = None
_browser = None
_context = None
_page = None

def _get_playwright_module():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright, None
    except ImportError:
        return None, "Playwright 未安装。请运行 `pip install playwright` 和 `playwright install`。"

def _ensure_page(headless: bool = False):
    global _playwright, _browser, _context, _page
    
    # If page is already alive, return it
    if _page:
        try:
            # Check if page is not closed (crude check)
            _page.title()
            return _page, None
        except Exception:
            # Page might be closed/crashed, reset
            _reset_browser()

    sync_playwright, err = _get_playwright_module()
    if err:
        return None, err

    try:
        if not _playwright:
            _playwright = sync_playwright().start()
        
        if not _browser:
            # Default to chromium, can be parameterized if needed
            _browser = _playwright.chromium.launch(headless=headless, slow_mo=50)
            
        if not _context:
            _context = _browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            
        if not _page:
            _page = _context.new_page()
            
        return _page, None
    except Exception as e:
        return None, f"启动浏览器失败: {e}"

def _reset_browser():
    global _playwright, _browser, _context, _page
    if _context:
        try:
            _context.close()
        except: pass
    if _browser:
        try:
            _browser.close()
        except: pass
    if _playwright:
        try:
            _playwright.stop()
        except: pass
    
    _context = None
    _browser = None
    _playwright = None
    _page = None

import platform
import shutil

def _get_tesseract_cmd():
    # 1. 检查 PATH
    if shutil.which("tesseract"):
        return None
    
    # 2. 检查常见 Windows 路径
    paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"D:\Program Files\Tesseract-OCR\tesseract.exe",
        r"E:\Program Files\Tesseract-OCR\tesseract.exe"
    ]
    for p in paths:
        if os.path.exists(p):
            return p
    return None

def _setup_tesseract(language: str = "chi_sim"):
    try:
        import pytesseract
    except ImportError:
        return None, "未安装 pytesseract，请运行 pip install pytesseract pillow"
        
    cmd = _get_tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    else:
        cmd = shutil.which("tesseract")
        
    if cmd:
        # 设置环境变量
        tessdata_dir = os.path.join(os.path.dirname(cmd), "tessdata")
        # 有些安装可能在 share/tessdata
        if not os.path.exists(tessdata_dir):
            alt_dir = os.path.join(os.path.dirname(cmd), "share", "tessdata")
            if os.path.exists(alt_dir):
                tessdata_dir = alt_dir
        
        # 设置环境变量，防止找不到 data
        # TESSDATA_PREFIX 应指向 tessdata 文件夹的父目录
        if os.path.exists(tessdata_dir):
            os.environ["TESSDATA_PREFIX"] = os.path.dirname(tessdata_dir)
            
            if language and "chi_sim" in language:
                lang_file = os.path.join(tessdata_dir, "chi_sim.traineddata")
                if not os.path.exists(lang_file):
                     return None, f"OCR 识别失败: 缺少中文语言包。请检查 {lang_file} 是否存在。\n解决方法: 重新安装 Tesseract 并勾选 'Additional language data -> Chinese (Simplified)'。"
            
    return pytesseract, None

@tool
def playwright_open(url: str, headless: bool = False):
    """
    使用 Playwright 打开指定网页并保持会话。
    
    Args:
        url: 目标网址
        headless: 是否无头模式 (默认 False，即显示浏览器)
    """
    page, err = _ensure_page(headless=headless)
    if err:
        return err
    try:
        page.goto(url, timeout=30000)
        # Wait for load state to be reasonably ready
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except:
            pass
        return f"已打开网页: {page.url}"
    except Exception as e:
        return f"打开网页失败: {e}"

@tool
def playwright_click(selector: str):
    """
    点击页面元素。
    
    Args:
        selector: CSS 选择器或文本定位 (text=Login)
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        # Playwright auto-waits for element to be visible and enabled
        _page.click(selector, timeout=10000)
        return "已点击元素"
    except Exception as e:
        return f"点击失败: {e}"

@tool
def playwright_type(selector: str, text: str, clear_first: bool = True):
    """
    在指定元素中输入文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
        clear_first: 是否先清空 (默认 True)
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        if clear_first:
            _page.fill(selector, text, timeout=10000)
        else:
            _page.type(selector, text, timeout=10000)
        return f"已输入文本: {text}"
    except Exception as e:
        return f"输入失败: {e}"

@tool
def playwright_get_text(selector: str):
    """
    获取元素文本内容。
    
    Args:
        selector: CSS 选择器
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        # Get text content
        content = _page.text_content(selector, timeout=10000)
        return content.strip() if content else ""
    except Exception as e:
        return f"获取文本失败: {e}"

@tool
def playwright_screenshot(save_path: str):
    """
    保存当前页面截图。
    
    Args:
        save_path: 保存路径 (如 reports/screenshot.png)
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _page.screenshot(path=path)
        return f"已保存截图: {path}"
    except Exception as e:
        return f"截图失败: {e}"

@tool
def playwright_close():
    """
    关闭浏览器会话。
    """
    try:
        _reset_browser()
        return "已关闭浏览器"
    except Exception as e:
        return f"关闭失败: {e}"

@tool
def playwright_run_steps(steps: list, screenshot_dir: str = "reports/screenshots"):
    """
    批量执行 Playwright 操作步骤。
    
    Args:
        steps: 步骤列表，每个步骤为 dict，包含 action 和参数
               actions: open, click, type, get_text, screenshot, wait
        screenshot_dir: 失败时截图保存目录
    """
    global _page
    results = []
    
    for i, step in enumerate(steps):
        action = step.get("action")
        try:
            if action == "open":
                url = step.get("url")
                headless = step.get("headless", False)
                res = playwright_open(url, headless)
                results.append(f"Step {i+1} [open]: {res}")
                
            elif action == "click":
                selector = step.get("selector")
                res = playwright_click(selector)
                results.append(f"Step {i+1} [click]: {res}")
                
            elif action == "type":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_type(selector, text)
                results.append(f"Step {i+1} [type]: {res}")
                
            elif action == "get_text":
                selector = step.get("selector")
                text = playwright_get_text(selector)
                results.append(f"Step {i+1} [get_text]: {text}")
                
            elif action == "screenshot":
                path = step.get("path", f"{screenshot_dir}/step_{i+1}.png")
                res = playwright_screenshot(path)
                results.append(f"Step {i+1} [screenshot]: {res}")
                
            elif action == "wait":
                sec = step.get("seconds", 1)
                time.sleep(sec)
                results.append(f"Step {i+1} [wait]: Waited {sec}s")
                
            else:
                results.append(f"Step {i+1} [unknown]: Unknown action {action}")
                
        except Exception as e:
            err_msg = f"Step {i+1} [{action}] Failed: {e}"
            results.append(err_msg)
            # Try to take screenshot on failure
            try:
                if _page:
                    fail_path = os.path.abspath(os.path.join(screenshot_dir, f"fail_step_{i+1}.png"))
                    os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                    _page.screenshot(path=fail_path)
                    results.append(f"Failure screenshot saved to {fail_path}")
            except:
                pass
            return "\n".join(results)

@tool
def playwright_click_by_ocr(text: str, index: int = 0, offset_x: int = 0, offset_y: int = 0, exact_match: bool = False, double_click: bool = False):
    """
    通过 OCR 识别屏幕文字并点击指定位置。
    当无法通过 CSS 选择器定位元素时，可使用此方法。
    
    Args:
        text: 要查找的文字
        index: 如果有多个匹配，点击第几个 (默认 0)
        offset_x: 点击位置相对于文字中心的 X 轴偏移量
        offset_y: 点击位置相对于文字中心的 Y 轴偏移量
        exact_match: 是否完全匹配文字 (默认 False，使用包含匹配)
        double_click: 是否双击 (默认 False)
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
        
    pytesseract, err = _setup_tesseract(language="chi_sim")
    if err:
        return err

    try:
        from PIL import Image
        from pytesseract import Output
        import io
        
        # 截图到内存
        screenshot_bytes = _page.screenshot()
        image = Image.open(io.BytesIO(screenshot_bytes))
        
        # OCR 识别
        # lang='chi_sim+eng' 覆盖中英文
        data = pytesseract.image_to_data(image, lang='chi_sim+eng', output_type=Output.DICT)
        
        matches = []
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            content = data['text'][i].strip()
            if not content:
                continue
            
            match = False
            if exact_match:
                if content == text:
                    match = True
            else:
                if text in content:
                    match = True
            
            if match:
                matches.append({
                    'x': data['left'][i],
                    'y': data['top'][i],
                    'w': data['width'][i],
                    'h': data['height'][i],
                    'text': content
                })
        
        if not matches:
            return f"未找到包含 '{text}' 的文字"
            
        if index >= len(matches):
            return f"找到 {len(matches)} 个匹配，但索引 {index} 超出范围"
            
        target = matches[index]
        
        # 计算中心点
        center_x = target['x'] + target['w'] / 2
        center_y = target['y'] + target['h'] / 2
        
        final_x = center_x + offset_x
        final_y = center_y + offset_y
        
        if double_click:
            _page.mouse.dblclick(final_x, final_y)
        else:
            _page.mouse.click(final_x, final_y)
        
        return f"已点击文字 '{target['text']}' 位置 ({final_x}, {final_y})"
        
    except Exception as e:
        return f"OCR 点击失败: {e}"

@tool
def playwright_type_current(text: str, delay: int = 50):
    """
    在当前焦点元素输入文本。
    通常配合 playwright_click_by_ocr 使用 (先点击输入框或标签，再输入)。
    
    Args:
        text: 要输入的文本
        delay: 按键间隔 (毫秒)，默认 50
    """
    global _page
    if not _page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        _page.keyboard.type(text, delay=delay)
        return f"已输入: {text}"
    except Exception as e:
        return f"输入失败: {e}"

    return "\n".join(results)
