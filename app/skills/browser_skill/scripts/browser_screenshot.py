"""
browser_screenshot - 截图

保存当前页面截图
"""

from langchain_core.tools import tool
import json
import os
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


@tool
def browser_screenshot(
    path: Optional[str] = None,
    full_page: bool = False
) -> Dict[str, Any]:
    """
    保存当前页面截图
    
    Args:
        path: 保存路径（可选，默认自动生成）
        full_page: 是否截取整个页面（默认 False，只截取可视区域）
    
    Returns:
        {
            "ok": True,
            "message": "截图成功",
            "path": "/path/to/screenshot.png"
        }
    
    Example:
        browser_screenshot.invoke({})
        browser_screenshot.invoke({"path": "result.png", "full_page": True})
    """
    tool_name = "browser_screenshot"
    
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
        
        # 生成默认路径
        if not path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshots_dir = os.path.join(os.getcwd(), "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            path = os.path.join(screenshots_dir, f"screenshot_{timestamp}.png")
        
        # 确保目录存在
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # 截图
        page.screenshot(path=path, full_page=full_page)
        
        _emit_event(tool_name, "screenshot", path=path)
        
        return _ok_payload(
            "截图成功",
            path=path,
            full_page=full_page
        )
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("screenshot_failed", f"截图失败：{e}", tool=tool_name)
