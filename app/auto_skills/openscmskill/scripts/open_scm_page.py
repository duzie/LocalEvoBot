from langchain_core.tools import tool
from typing import Dict, Any, Optional
import json
import os

from app.skills.playwright_skill.scripts import _playwright_core as core


@tool
def open_scm_page(
    url: str = "https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    headless: bool = False,
    get_accessibility_snapshot: bool = True
) -> Dict[str, Any]:
    """
    打开菜么么库存页面并获取无障碍快照
    
    Args:
        url: 目标网址，默认为菜么么库存页面
        headless: 是否无头模式，默认False（显示浏览器）
        get_accessibility_snapshot: 是否获取无障碍快照，默认True
        
    Returns:
        包含操作结果的字典
    """
    try:
        result = {
            "success": False,
            "url": url,
            "headless": headless,
            "final_url": None,
            "title": None,
            "accessibility_snapshot": None,
            "error": None
        }

        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
        extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR") or core._get_default_extension_dir()
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
        page, err = core._ensure_page(
            headless=headless, user_data_dir=user_data_dir, extension_dir=extension_dir
        )
        if err:
            result["error"] = err
            return result

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
            response = page.goto(url, timeout=30000, wait_until="networkidle")
            result["final_url"] = page.url
            result["title"] = page.title()

            page.wait_for_load_state("networkidle")

            page_content = page.content()
            is_caimomo_page = "菜么么" in page_content or "caimomo" in page_content.lower()

            if get_accessibility_snapshot:
                try:
                    snapshot = page.accessibility.snapshot()
                    result["accessibility_snapshot"] = snapshot
                except Exception as e:
                    result["accessibility_snapshot_error"] = str(e)

            result["success"] = True
            result["is_caimomo_page"] = is_caimomo_page
            result["status_code"] = response.status if response else None
            result["browser_context"] = "保持打开状态，需要手动关闭"
            result["message"] = "页面已成功打开，浏览器保持运行状态"
        except Exception as e:
            result["error"] = str(e)
        return result
        
    except ImportError as e:
        return {
            "success": False,
            "error": f"缺少依赖: {str(e)}。请安装playwright: pip install playwright && playwright install chromium",
            "url": url
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "url": url
        }
