"""
browser_act - 执行浏览器操作

支持点击、输入、按键等操作，使用 ref 定位元素
"""

from langchain_core.tools import tool
import json
from typing import Dict, Any, Optional
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


def _find_element_by_ref(ref: str, elements: list) -> Optional[Dict]:
    """根据 ref 查找元素"""
    for elem in elements:
        if elem.get("ref") == ref:
            return elem
    return None


@tool
def browser_act(
    kind: str,
    ref: Optional[str] = None,
    text: Optional[str] = None,
    key: Optional[str] = None,
    selector: Optional[str] = None
) -> Dict[str, Any]:
    """
    执行浏览器操作（点击/输入/按键）
    
    Args:
        kind: 操作类型
            - "click": 点击
            - "type": 输入文本
            - "fill": 填充表单（清空后输入）
            - "press": 按键（Enter/Escape 等）
            - "hover": 悬停
        ref: 元素 ref（从 browser_snapshot 获取，如 "e1"）
        text: 输入的文本（type/fill 时需要）
        key: 按键名称（press 时需要，如 "Enter", "ArrowDown"）
        selector: 备用 CSS Selector（如果 ref 找不到）
    
    Returns:
        {
            "ok": True,
            "message": "操作成功",
            "action": "click",
            "ref": "e1"
        }
    
    Example:
        # 点击
        browser_act.invoke({"kind": "click", "ref": "e1"})
        
        # 输入文本
        browser_act.invoke({"kind": "type", "ref": "e2", "text": "用户名"})
        
        # 按键
        browser_act.invoke({"kind": "press", "ref": "e2", "key": "Enter"})
    """
    tool_name = "browser_act"
    
    # 验证参数
    if not kind:
        return _error_payload("invalid_args", "kind 参数不能为空", tool=tool_name)
    
    if not ref and not selector:
        return _error_payload(
            "invalid_args", 
            "ref 或 selector 必须提供一个",
            tool=tool_name
        )
    
    valid_kinds = ["click", "type", "fill", "press", "hover"]
    if kind not in valid_kinds:
        return _error_payload(
            "invalid_args", 
            f"kind 必须是：{', '.join(valid_kinds)}",
            tool=tool_name
        )
    
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
        
        # 确定使用 ref 还是 selector
        target_selector = selector
        element_info = None
        
        if ref:
            # 尝试从最近的 snapshot 中查找
            # 注意：这里简化处理，实际应该缓存最近的 snapshot
            # 如果找不到，尝试用 ref 作为 CSS selector（兼容）
            if not selector:
                # 假设 ref 是类似 "e1" 的格式，尝试查找
                # 这里需要访问 browser_snapshot 的缓存
                # 简化：直接使用 ref 作为 data-ref 属性
                target_selector = f"[data-ref='{ref}']"
                element_info = {"ref": ref}
        
        if not target_selector:
            return _error_payload(
                "element_not_found",
                f"未找到元素：ref={ref}",
                tool=tool_name,
                ref=ref
            )
        
        # 执行操作
        action_desc = f"{kind} {ref or selector}"
        
        if kind == "click":
            page.click(target_selector, timeout=5000)
            
        elif kind in ["type", "fill"]:
            if not text:
                return _error_payload(
                    "invalid_args",
                    f"{kind} 操作需要提供 text 参数",
                    tool=tool_name
                )
            
            if kind == "fill":
                page.fill(target_selector, text, timeout=5000)
            else:
                page.type(target_selector, text, timeout=5000, delay=50)
            
            action_desc += f" \"{text[:20]}...\""
            
        elif kind == "press":
            if not key:
                return _error_payload(
                    "invalid_args",
                    "press 操作需要提供 key 参数",
                    tool=tool_name
                )
            page.press(target_selector, key, timeout=5000)
            action_desc += f" {key}"
            
        elif kind == "hover":
            page.hover(target_selector, timeout=5000)
        
        _emit_event(tool_name, "action", action=kind, ref=ref, selector=selector)
        
        return _ok_payload(
            f"操作成功：{action_desc}",
            action=kind,
            ref=ref,
            selector=selector
        )
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload(
            "action_failed",
            f"操作失败：{e}",
            tool=tool_name,
            action=kind,
            ref=ref
        )


# 便捷工具：点击
@tool
def browser_click(ref: str, selector: Optional[str] = None) -> Dict[str, Any]:
    """
    点击元素（browser_act 的便捷版本）
    
    Args:
        ref: 元素 ref
        selector: 备用 CSS Selector
    
    Example:
        browser_click.invoke({"ref": "e1"})
    """
    return browser_act.invoke({"kind": "click", "ref": ref, "selector": selector})


# 便捷工具：输入
@tool
def browser_type(ref: str, text: str, selector: Optional[str] = None) -> Dict[str, Any]:
    """
    输入文本（browser_act 的便捷版本）
    
    Args:
        ref: 元素 ref
        text: 要输入的文本
        selector: 备用 CSS Selector
    
    Example:
        browser_type.invoke({"ref": "e2", "text": "用户名"})
    """
    return browser_act.invoke({"kind": "type", "ref": ref, "text": text, "selector": selector})
