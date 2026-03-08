"""
browser_open - 打开网页

简化的打开网页工具，保持与 playwright_open 兼容
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
def browser_open(
    url: str,
    headless: bool = False,
    user_data_dir: Optional[str] = None,
    extension_dir: Optional[str] = None
) -> Dict[str, Any]:
    """
    打开网页（简化的 browser_open）
    
    Args:
        url: 目标网址
        headless: 是否无头模式（默认 False）
        user_data_dir: 用户数据目录（可选，用于持久化登录）
        extension_dir: 扩展目录（可选）
    
    Returns:
        {
            "ok": True,
            "message": "已打开网页",
            "url": "https://...",
            "title": "页面标题"
        }
    
    Example:
        browser_open.invoke({"url": "https://taobao.com"})
    """
    tool_name = "browser_open"
    
    if not url or not str(url).strip():
        return _error_payload("invalid_args", "url 不能为空", tool=tool_name)
    
    try:
        from app.skills.playwright_skill.scripts import _playwright_core as core
        
        # 使用默认配置
        if not user_data_dir:
            user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
        if not extension_dir:
            extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR")
        if not extension_dir:
            # 使用默认扩展目录
            extension_dir = core._get_default_extension_dir()
        
        # 确保目录存在
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
        
        # 创建页面
        page, err = core._ensure_page(
            headless=headless,
            user_data_dir=user_data_dir,
            extension_dir=extension_dir
        )
        
        if err:
            _emit_event(tool_name, "error", error=str(err))
            return _error_payload("ensure_page_failed", str(err), tool=tool_name)
        
        # 打开网页
        page.goto(url, timeout=30000)
        
        # 等待加载
        try:
            page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass  # 不强制等待
        
        _emit_event(tool_name, "open", url=page.url)
        
        return _ok_payload(
            "已打开网页",
            url=page.url,
            title=page.title()
        )
        
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("open_failed", f"打开网页失败：{e}", tool=tool_name)
