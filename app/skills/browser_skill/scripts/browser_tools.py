from langchain_core.tools import tool
import json
import time
from typing import Optional, Dict, Any

# 由于我们无法直接访问OpenClaw的内部浏览器服务，
# 我们将创建一个与OpenClaw功能相似的基于Playwright的实现
# 这样可以提供类似OpenClaw浏览器工具的能力

# 使用全局变量来维护浏览器会话（类似OpenClaw的方式）
_browser_instance = None
_browser_context = None
_current_page = None

def _get_or_create_browser():
    """获取或创建浏览器实例（类似OpenClaw的浏览器管理）"""
    global _browser_instance, _browser_context, _current_page
    
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, "Playwright未安装。请运行 `pip install playwright` 并执行 `playwright install`。"
    
    # 如果浏览器尚未初始化，则启动它
    if _browser_instance is None:
        playwright = sync_playwright().start()
        try:
            _browser_instance = playwright.chromium.launch(headless=False)  # 类似OpenClaw的非headless模式
            _browser_context = _browser_instance.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            _current_page = _browser_context.new_page()
        except Exception as e:
            return None, f"启动浏览器失败: {str(e)}"
    
    return _current_page, None

def _ensure_browser_ready(page):
    """确保浏览器已准备好执行操作"""
    if page is None:
        return False, "浏览器未初始化，请先打开一个页面"
    try:
        # 检查页面是否可用
        page.url  # 尝试访问页面属性
        return True, None
    except:
        return False, "浏览器页面不可用"

def _simulate_openclaw_browser_call(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用Playwright模拟OpenClaw浏览器功能
    """
    global _browser_instance, _browser_context, _current_page
    
    page, error = _get_or_create_browser()
    if error:
        return {"error": error}
    
    ready, error = _ensure_browser_ready(page)
    if not ready:
        return {"error": error}
    
    try:
        if action == "open" or action == "navigate":
            url = params.get("url", "")
            page.goto(url, timeout=30000)
            # 等待页面加载
            try:
                page.wait_for_load_state("domcontentloaded", timeout=10000)
            except:
                pass  # 即使超时也继续执行
            return {"status": "success", "url": page.url, "title": page.title()}
        
        elif action == "snapshot":
            # 获取页面的DOM结构和可访问性树
            dom_content = page.content()
            title = page.title()
            url = page.url
            
            # 获取页面上所有可点击元素的信息
            elements_script = """
            Array.from(document.querySelectorAll('a, button, input, textarea, select, [role="button"], [role="link"], [onclick], [tabindex]'))
            .filter(el => !el.disabled && el.offsetParent !== null)  // 过滤掉禁用或隐藏的元素
            .map(el => ({
                tagName: el.tagName.toLowerCase(),
                id: el.id || null,
                className: el.className || null,
                text: el.textContent.trim().substring(0, 100) || null,
                accessibleName: el.getAttribute('aria-label') || el.getAttribute('title') || null,
                role: el.getAttribute('role') || null,
                selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ')[0] : '')
            }))
            """
            elements = page.evaluate(elements_script)
            
            return {
                "dom": dom_content,
                "url": url,
                "title": title,
                "elements": elements[:50],  # 限制返回元素数量
                "element_summary": f"共找到 {len(elements)} 个可交互元素"
            }
        
        elif action == "click":
            selector = params.get("selector", "")
            # 尝试多种方式定位元素
            selectors_to_try = [
                selector,  # 原始选择器
                f"text={selector}",  # 文本匹配
                f"[aria-label='{selector}']",  # aria-label
                f"[title='{selector}']"  # title属性
            ]
            
            last_error = ""
            for sel in selectors_to_try:
                try:
                    page.click(sel, timeout=10000)
                    return {"status": "success", "clicked_selector": sel}
                except Exception as e:
                    last_error = str(e)
                    continue  # 尝试下一个选择器
            
            return {"error": f"无法点击元素 '{selector}': {last_error}"}
        
        elif action == "fill":
            selector = params.get("selector", "")
            text = params.get("text", "")
            
            # 尝试多种方式定位元素
            selectors_to_try = [
                selector,
                f"[placeholder='{selector}']",  # 根据placeholder查找输入框
            ]
            
            last_error = ""
            for sel in selectors_to_try:
                try:
                    page.fill(sel, text, timeout=10000)
                    return {"status": "success", "filled_selector": sel, "text": text}
                except Exception as e:
                    last_error = str(e)
                    continue
            
            return {"error": f"无法填充元素 '{selector}': {last_error}"}
        
        elif action == "type":
            text = params.get("text", "")
            # 在当前焦点元素输入文本
            page.keyboard.type(text)
            return {"status": "success", "typed_text": text}
        
        elif action == "screenshot":
            path = params.get("path", f"browser_screenshot_{int(time.time())}.png")
            import os
            # 确保目录存在
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            page.screenshot(path=path, full_page=params.get("full_page", False))
            return {"status": "success", "screenshot_path": path}
        
        elif action == "execute_js":
            script = params.get("script", "")
            result = page.evaluate(script)
            return {"status": "success", "result": result}
        
        elif action == "close":
            if _browser_instance:
                _browser_instance.close()
                # 重置全局变量
                _browser_instance = None
                _browser_context = None
                _current_page = None
            return {"status": "success", "message": "浏览器已关闭"}
        
        else:
            return {"error": f"未知的操作: {action}"}
    
    except Exception as e:
        return {"error": f"执行操作时发生错误: {str(e)}"}

@tool
def browser_open(url: str):
    """
    打开浏览器并导航到指定URL。
    
    Args:
        url: 要打开的网页地址
    """
    result = _simulate_openclaw_browser_call("open", {"url": url})
    if "error" in result:
        return f"打开网页失败: {result['error']}"
    return f"已打开网页: {result.get('url', url)}\n页面标题: {result.get('title', 'Unknown')}"

@tool
def browser_snapshot():
    """
    获取当前页面的DOM快照和可交互元素。
    """
    result = _simulate_openclaw_browser_call("snapshot", {})
    if "error" in result:
        return f"获取快照失败: {result['error']}"
    
    elements_info = result.get('element_summary', 'No elements info')
    return f"页面标题: {result.get('title', 'Unknown')}\nURL: {result.get('url', 'Unknown')}\n{elements_info}\n\n如需详细DOM结构，请使用browser_execute_js获取特定内容。"

@tool
def browser_click(selector: str):
    """
    点击页面上的元素。
    
    Args:
        selector: 选择器，可以是CSS选择器或文本内容
    """
    result = _simulate_openclaw_browser_call("click", {"selector": selector})
    if "error" in result:
        return f"点击失败: {result['error']}"
    return f"已点击元素: {result.get('clicked_selector', selector)}"

@tool
def browser_fill(selector: str, text: str):
    """
    在表单元素中填入文本。
    
    Args:
        selector: CSS选择器，用于定位要填充的元素
        text: 要填入的文本
    """
    result = _simulate_openclaw_browser_call("fill", {"selector": selector, "text": text})
    if "error" in result:
        return f"填充失败: {result['error']}"
    return f"已在 {result.get('filled_selector', selector)} 中填入: {repr(result.get('text', text))}"

@tool
def browser_type(text: str):
    """
    在当前焦点元素输入文本。
    
    Args:
        text: 要输入的文本
    """
    result = _simulate_openclaw_browser_call("type", {"text": text})
    if "error" in result:
        return f"输入失败: {result['error']}"
    return f"已输入文本: {repr(result.get('typed_text', text))}"

@tool
def browser_navigate(url: str):
    """
    导航到新的URL。
    
    Args:
        url: 要导航到的网页地址
    """
    result = _simulate_openclaw_browser_call("navigate", {"url": url})
    if "error" in result:
        return f"导航失败: {result['error']}"
    return f"已导航到: {result.get('url', url)}\n页面标题: {result.get('title', 'Unknown')}"

@tool
def browser_screenshot(path: str = "browser_screenshot.png", full_page: bool = False):
    """
    截取当前页面截图。
    
    Args:
        path: 保存截图的路径，默认为"browser_screenshot.png"
        full_page: 是否截取完整页面，默认为False
    """
    result = _simulate_openclaw_browser_call("screenshot", {"path": path, "full_page": full_page})
    if "error" in result:
        return f"截图失败: {result['error']}"
    return f"截图已保存至: {result.get('screenshot_path', path)}"

@tool
def browser_execute_js(script: str):
    """
    在当前页面执行JavaScript代码。
    
    Args:
        script: 要执行的JavaScript代码
    """
    result = _simulate_openclaw_browser_call("execute_js", {"script": script})
    if "error" in result:
        return f"执行JS失败: {result['error']}"
    return f"JS执行结果: {result.get('result')}"

@tool
def browser_close():
    """
    关闭浏览器会话。
    """
    result = _simulate_openclaw_browser_call("close", {})
    if "error" in result:
        return f"关闭失败: {result['error']}"
    return "浏览器已关闭"
