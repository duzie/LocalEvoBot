import json
import os
import time

from langchain_core.tools import tool

from . import _playwright_core as core


@tool
def playwright_open(url: str, headless: bool = False, user_data_dir: str = None, extension_dir: str = None):
    """
    使用 Playwright 打开指定网页并保持会话。
    
    Args:
        url: 目标网址
        headless: 是否无头模式 (默认 False，即显示浏览器)
        user_data_dir: 用户数据目录，传入后可持久化登录状态
        extension_dir: 扩展目录，传入后自动加载扩展
    """
    if not user_data_dir:
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
    if not extension_dir:
        extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR")
    if not extension_dir:
        extension_dir = core._get_default_extension_dir()
    if user_data_dir:
        os.makedirs(user_data_dir, exist_ok=True)
    page, err = core._ensure_page(
        headless=headless, user_data_dir=user_data_dir, extension_dir=extension_dir
    )
    if err:
        return err
    try:
        auto = (os.getenv("PLAYWRIGHT_AUTO_LOAD_COOKIES") or "1").strip().lower()
        if auto in ("1", "true", "yes", "on"):
            try:
                from urllib.parse import urlparse

                hostname = urlparse(url).hostname
            except Exception:
                hostname = None
            if hostname:
                core._apply_cookies_for_domain(hostname, base_url=url)
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        return f"已打开网页: {page.url}"
    except Exception as e:
        return f"打开网页失败: {e}"


@tool
def playwright_navigate(url: str):
    """
    导航到新的网页地址。
    
    Args:
        url: 目标网址
    """
    page, err = core._ensure_page(headless=False)
    if err:
        return err
    try:
        page.goto(url, timeout=30000)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass
        return f"已导航到: {page.url}"
    except Exception as e:
        return f"导航失败: {e}"


@tool
def playwright_click(selector: str):
    """
    点击页面元素。
    
    Args:
        selector: CSS 选择器或文本定位 (text=Login)
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        core._page.click(selector, timeout=10000)
        core._maybe_wait_new_page(1200)
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
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        if clear_first:
            core._page.fill(selector, text, timeout=10000)
        else:
            core._page.type(selector, text, timeout=10000)
        return f"已输入文本: {text}"
    except Exception as e:
        return f"输入失败: {e}"


@tool
def playwright_fill(selector: str, text: str):
    """
    在指定元素中填充文本。
    
    Args:
        selector: CSS 选择器
        text: 输入文本
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        core._page.fill(selector, text, timeout=10000)
        return f"已填充文本: {text}"
    except Exception as e:
        return f"填充失败: {e}"


@tool
def playwright_execute_js(script: str):
    """
    在当前页面执行 JavaScript 代码。
    
    Args:
        script: JavaScript 代码
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        wrapped, err = core._wrap_script(script)
        if err:
            return f"执行失败: {err}"
        result = core._page.evaluate(wrapped)
        return f"JS执行结果: {result}"
    except Exception as e:
        return f"执行失败: {e}"


@tool
def playwright_snapshot():
    """
    获取当前页面的 DOM 快照与可交互元素摘要。
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        dom_content = core._page.content()
        title = core._page.title()
        url = core._page.url
        elements_script = """
        Array.from(document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]'))
        .filter(el => !el.disabled && el.offsetParent !== null)
        .map(el => ({
            tagName: el.tagName.toLowerCase(),
            id: el.id || null,
            className: el.className || null,
            text: (el.textContent || '').trim().substring(0, 100) || null,
            accessibleName: el.getAttribute('aria-label') || el.getAttribute('title') || null,
            role: el.getAttribute('role') || null,
            selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ')[0] : '')
        }))
        """
        elements = core._page.evaluate(elements_script)
        element_summary = f"共找到 {len(elements)} 个可交互元素"
        _ = dom_content
        return f"页面标题: {title}\nURL: {url}\n{element_summary}\n\n如需详细DOM结构，请使用 playwright_execute_js 获取特定内容。"
    except Exception as e:
        return f"获取快照失败: {e}"


@tool
def playwright_get_text(selector: str):
    """
    获取元素文本内容。
    
    Args:
        selector: CSS 选择器
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        content = core._page.text_content(selector, timeout=10000)
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
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        path = os.path.abspath(save_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        core._page.screenshot(path=path)
        return f"已保存截图: {path}"
    except Exception as e:
        return f"截图失败: {e}"


@tool
def playwright_close():
    """
    关闭浏览器会话。
    """
    try:
        core._reset_browser()
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

            elif action == "fill":
                selector = step.get("selector")
                text = step.get("text")
                res = playwright_fill(selector, text)
                results.append(f"Step {i+1} [fill]: {res}")

            elif action == "get_text":
                selector = step.get("selector")
                text = playwright_get_text(selector)
                results.append(f"Step {i+1} [get_text]: {text}")

            elif action == "navigate":
                url = step.get("url")
                res = playwright_navigate(url)
                results.append(f"Step {i+1} [navigate]: {res}")

            elif action == "screenshot":
                path = step.get("path", f"{screenshot_dir}/step_{i+1}.png")
                res = playwright_screenshot(path)
                results.append(f"Step {i+1} [screenshot]: {res}")

            elif action == "execute_js":
                script = step.get("script")
                res = playwright_execute_js(script)
                results.append(f"Step {i+1} [execute_js]: {res}")

            elif action == "wait":
                sec = step.get("seconds", 1)
                time.sleep(sec)
                results.append(f"Step {i+1} [wait]: Waited {sec}s")

            else:
                results.append(f"Step {i+1} [unknown]: Unknown action {action}")

        except Exception as e:
            err_msg = f"Step {i+1} [{action}] Failed: {e}"
            results.append(err_msg)
            try:
                if core._page:
                    fail_path = os.path.abspath(
                        os.path.join(screenshot_dir, f"fail_step_{i+1}.png")
                    )
                    os.makedirs(os.path.dirname(fail_path), exist_ok=True)
                    core._page.screenshot(path=fail_path)
                    results.append(f"Failure screenshot saved to {fail_path}")
            except Exception:
                pass
            return "\n".join(results)

    return "\n".join(results)

