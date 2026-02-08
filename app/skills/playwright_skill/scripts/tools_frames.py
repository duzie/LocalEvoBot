import json

from langchain_core.tools import tool

from . import _playwright_core as core


@tool
def playwright_list_frames():
    """
    列出当前页面的 iframe 列表。
    """
    core._sync_latest_page()
    if not core._page:
        return "浏览器未启动，请先调用 playwright_open"
    try:
        items = []
        for f in core._page.frames:
            items.append({"name": f.name, "url": f.url})
        return json.dumps(items, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"获取 iframe 失败: {e}"


@tool
def playwright_execute_js_in_frame(script: str, frame_name: str = None, frame_url: str = None, frame_selector: str = None):
    """
    在指定 iframe 中执行 JavaScript。
    """
    frame, err = core._resolve_frame(frame_name, frame_url, frame_selector)
    if err:
        return err
    try:
        wrapped, err = core._wrap_script(script)
        if err:
            return f"执行失败: {err}"
        result = frame.evaluate(wrapped)
        return f"JS执行结果: {result}"
    except Exception as e:
        return f"执行失败: {e}"


@tool
def playwright_snapshot_in_frame(frame_name: str = None, frame_url: str = None, frame_selector: str = None):
    """
    获取指定 iframe 的 DOM 快照与可交互元素摘要。
    """
    frame, err = core._resolve_frame(frame_name, frame_url, frame_selector)
    if err:
        return err
    try:
        dom_content = frame.content()
        title = frame.title()
        url = frame.url
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
        elements = frame.evaluate(elements_script)
        element_summary = f"共找到 {len(elements)} 个可交互元素"
        _ = dom_content
        return f"页面标题: {title}\nURL: {url}\n{element_summary}\n\n如需详细DOM结构，请使用 playwright_execute_js_in_frame 获取特定内容。"
    except Exception as e:
        return f"获取快照失败: {e}"

