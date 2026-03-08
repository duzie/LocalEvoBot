"""
browser_snapshot - 获取页面 ARIA 树

解析页面 DOM，提取可交互元素，自动分配 ref（如 e1, e2, e3...）
"""

from langchain_core.tools import tool
import json
from typing import Dict, Any, List
from datetime import datetime
from web.backend.shared import shared


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
    payload = {
        "event": str(event or ""),
        "tool": str(tool_name or ""),
        "time": datetime.now().isoformat()
    }
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))


def _extract_interactive_elements(page) -> List[Dict[str, Any]]:
    """
    提取页面所有可交互元素
    
    返回：
    [
        {
            "ref": "e1",
            "role": "button",
            "name": "登录按钮",
            "type": "button",
            "selector": "#login-btn",  # 备用 CSS Selector
            "visible": True,
            "enabled": True
        },
        ...
    ]
    """
    elements = []
    ref_counter = [0]  # 使用列表实现闭包
    
    def should_include(element) -> bool:
        """判断元素是否应该包含"""
        role = element.get("role", "")
        tag = element.get("tagName", "").lower()
        
        # 可交互元素
        interactive_roles = [
            "button", "link", "checkbox", "radio", "textbox", 
            "combobox", "listbox", "menuitem", "tab"
        ]
        interactive_tags = [
            "button", "a", "input", "select", "textarea"
        ]
        
        return (role in interactive_roles or tag in interactive_tags)
    
    def traverse(node, parent_selector: str = ""):
        """递归遍历 ARIA 树"""
        if not isinstance(node, dict):
            return
        
        # 检查当前节点
        if should_include(node):
            ref_counter[0] += 1
            ref = f"e{ref_counter[0]}"
            
            # 构建选择器
            selector = node.get("selector", "")
            if not selector and parent_selector:
                selector = f"{parent_selector} > {node.get('tagName', '')}"
            
            elements.append({
                "ref": ref,
                "role": node.get("role", node.get("tagName", "")),
                "name": node.get("name", node.get("ariaLabel", "")),
                "type": node.get("type", ""),
                "text": node.get("text", "")[:50],  # 限制长度
                "selector": selector,
                "visible": node.get("visible", True),
                "enabled": node.get("enabled", True)
            })
        
        # 遍历子节点
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                traverse(child, selector)
    
    try:
        # 使用 Playwright 获取 ARIA 树
        # 注意：这里需要调用 playwright_core 的辅助函数
        from app.skills.playwright_skill.scripts import _playwright_core as core
        
        page = core._sync_latest_page()
        if not page:
            return elements
        
        # 获取无障碍树
        snapshot = page.accessibility.snapshot()
        if snapshot:
            traverse(snapshot)
            
    except Exception as e:
        print(f"提取元素失败：{e}")
    
    return elements


@tool
def browser_snapshot() -> Dict[str, Any]:
    """
    获取当前页面 ARIA 树，自动分配 ref
    
    Returns:
        {
            "ok": True,
            "url": "https://example.com",
            "title": "页面标题",
            "refs": {
                "e1": "登录按钮",
                "e2": "用户名输入框",
                "e3": "密码输入框"
            },
            "elements": [
                {
                    "ref": "e1",
                    "role": "button",
                    "name": "登录按钮",
                    "selector": "#login-btn"
                },
                ...
            ]
        }
    
    Example:
        result = browser_snapshot.invoke({})
        if result.get("ok"):
            print(result.get("refs"))
            # {"e1": "登录按钮", "e2": "用户名输入框"}
    """
    tool_name = "browser_snapshot"
    
    try:
        from app.skills.playwright_skill.scripts import _playwright_core as core
        
        # 获取最新页面
        page = core._sync_latest_page()
        if not page:
            return _error_payload(
                "browser_not_ready", 
                "浏览器未启动，请先调用 browser_open",
                tool=tool_name
            )
        
        # 获取页面信息
        url = page.url
        title = page.title()
        
        # 提取可交互元素
        elements = _extract_interactive_elements(page)
        
        # 构建 refs 字典
        refs = {}
        for elem in elements:
            name = elem.get("name") or elem.get("text") or elem.get("role")
            if name:
                refs[elem["ref"]] = name[:30]  # 限制长度
        
        _emit_event(tool_name, "snapshot", element_count=len(elements))
        
        return _ok_payload(
            f"获取页面结构成功，共 {len(elements)} 个可交互元素",
            url=url,
            title=title,
            refs=refs,
            elements=elements,
            element_count=len(elements)
        )
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("snapshot_failed", f"获取页面结构失败：{e}", tool=tool_name)
