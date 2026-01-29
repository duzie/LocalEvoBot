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

    return "\n".join(results)
