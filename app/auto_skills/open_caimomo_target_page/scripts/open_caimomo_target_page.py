from langchain_core.tools import tool
from typing import Dict, Any, Optional
import os
import time
from urllib.parse import urlparse

# 导入playwright核心方法
from app.skills.playwright_skill.scripts import _playwright_core as core


@tool
def open_caimomo_target_page(
    url: str = "https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    headless: bool = False,
    module: Optional[str] = None,
    target_menu: str = "库存管理",  # 动态主菜单（如：库存管理/报表分析/连锁物流单据）
    target_option: str = "采购入库"  # 动态子选项（如：采购入库/部门进销存汇总表/要货单）
) -> Dict[str, Any]:
    """
    打开菜么么系统，定位**动态主菜单**并点击**动态子选项**（适配任意菜单/选项组合）
    核心：纯文本+层级定位，不依赖rel/for/class等固定属性，支持菜单动态切换
    
    Args:
        url: 菜么么系统首页/菜单页URL
        headless: 是否无头模式，默认False（显示浏览器）
        module: 模块名称（库存/总部/会员/报表/微信系统/营销中心）
        target_menu: 要展开的主菜单文本（如：库存管理、报表分析、连锁物流单据）
        target_option: 要点击的子选项文本（如：采购入库、部门进销存汇总表、要货单）
    
    Returns:
        包含操作结果、步骤、错误的字典
    """
    result = {
        "success": False,
        "message": "",
        "steps": [],
        "error": None,
        "screenshot": None
    }
    page = None
    try:
        module_url_map = {
            "库存": "https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
            "总部": "https://v2.caimomo.com/BaseDataWeb/GroupManager/NewMenu.aspx?appver=4",
            "系统设置": "https://v2.caimomo.com/BaseDataWeb/Setup/NewMenu.aspx?appver=4",
            "会员": "https://v2.caimomo.com/MemberWeb/CRM/NewMenu.aspx?appver=4",
            "报表": "https://v2.caimomo.com/ReportWeb/Report/NewMenu.aspx?appver=4",
            "微信系统": "https://v2.caimomo.com/WeiXinManager/WeiXin/NewMenu.aspx?appver=4",
            "营销中心": "https://v2.caimomo.com/WeiXinManager/WeiXin/ActivityMenu.aspx",
        }
        module_key = (module or "").strip()
        if module_key in module_url_map:
            url = module_url_map[module_key]
            result["steps"].append(f"使用模块[{module_key}]地址: {url}")

        # 1. 初始化Playwright页面（加载cookie、扩展）
        user_data_dir = os.getenv("PLAYWRIGHT_USER_DATA_DIR")
        extension_dir = os.getenv("PLAYWRIGHT_EXTENSION_DIR") or core._get_default_extension_dir()
        if user_data_dir:
            os.makedirs(user_data_dir, exist_ok=True)
        
        page, err = core._ensure_page(
            headless=headless, user_data_dir=user_data_dir, extension_dir=extension_dir
        )
        if err:
            result["error"] = err
            result["steps"].append(f"页面初始化失败: {err}")
            return result
        
        # 自动加载对应域名的cookie
        auto_load_cookie = (os.getenv("PLAYWRIGHT_AUTO_LOAD_COOKIES") or "1").strip().lower()
        if auto_load_cookie in ("1", "true", "yes", "on"):
            hostname = urlparse(url).hostname
            if hostname:
                core._apply_cookies_for_domain(hostname, base_url=url)
                result["steps"].append(f"已加载{hostname}的cookie")
        
        # 2. 导航到菜么么菜单页，等待核心菜单容器加载
        result["steps"].append(f"导航到菜单页: {url}")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # 等待根菜单容器#ulmenu加载（页面核心标识，不会动态变化）
        try:
            page.wait_for_selector("#ulmenu", timeout=8000, state="visible")
        except Exception:
            page.wait_for_selector("//div[contains(@class,'accordion') and @name='ulmenu']", timeout=8000, state="visible")
        result["steps"].append(f"页面加载完成，标题: {page.title()}")

        target_menu = (target_menu or "").strip()
        target_option = (target_option or "").strip()
        if not target_menu:
            first_menu = page.query_selector("//div[@id='ulmenu']//div[contains(@class, 'section')]//label")
            if not first_menu:
                raise Exception("未找到任何主菜单")
            target_menu = (first_menu.inner_text() or "").strip()
        result["steps"].append(f"开始定位主菜单: [{target_menu}]")
        menu_selector = f"//div[@id='ulmenu']//div[contains(@class, 'section')]//label[contains(normalize-space(.), '{target_menu}')]"
        try:
            menu_elem = page.wait_for_selector(
                menu_selector,
                timeout=5000,
                state="visible"
            )
            menu_elem.click(force=True)
            result["steps"].append(f"成功点击主菜单: [{target_menu}]")
            page.wait_for_selector(
                f"//label[contains(normalize-space(.), '{target_menu}')]/following-sibling::div[contains(@class, 'content')]",
                timeout=3000,
                state="visible"
            )
            result["steps"].append(f"主菜单[{target_menu}]已展开，加载子选项")
        except Exception as e:
            raise Exception(f"主菜单[{target_menu}]定位/点击失败: {str(e)[:60]}")

        if not target_option:
            first_option_selector = (
                f"//label[contains(normalize-space(.), '{target_menu}')]"
                f"/following-sibling::div[contains(@class, 'content')]"
                f"//ul//li//a"
            )
            first_option = page.query_selector(first_option_selector)
            if not first_option:
                raise Exception(f"主菜单[{target_menu}]下未找到子选项")
            target_option = (first_option.inner_text() or "").strip()
        result["steps"].append(f"开始定位子选项: [{target_option}]")
        option_selector = (
            f"//label[contains(normalize-space(.), '{target_menu}')]"
            f"/following-sibling::div[contains(@class, 'content')]"
            f"//ul//li//a[contains(normalize-space(.), '{target_option}')]"
        )
        try:
            option_elem = page.wait_for_selector(
                option_selector,
                timeout=5000,
                state="visible"
            )
            option_elem.scroll_into_view_if_needed()
            option_elem.click(force=True)
            result["steps"].append(f"成功点击子选项: [{target_option}]")
        except Exception as e:
            raise Exception(f"子选项[{target_option}]定位/点击失败: {str(e)[:60]}")

        # 5. 等待目标页面加载，验证操作结果
        result["steps"].append(f"等待[{target_option}]页面加载")
        page.wait_for_load_state("networkidle", timeout=15000)
        current_url = page.url
        result["steps"].append(f"目标页面加载完成，当前URL: {current_url}")

        # 6. 操作成功结果返回
        result["success"] = True
        result["message"] = f"成功打开[{target_menu}] -> [{target_option}]页面"
        result["steps"].append("所有操作完成，浏览器保持打开状态，可继续后续操作")

    except Exception as e:
        # 全局异常捕获，记录错误+截图
        result["success"] = False
        result["error"] = str(e)
        result["message"] = f"操作失败: {str(e)[:80]}"
        result["steps"].append(f"错误详情: {str(e)}")
        # 错误时自动截图（全页面）
        if page:
            try:
                screenshot_name = f"caimomo_error_{os.getpid()}_{int(time.time())}.png"
                page.screenshot(path=screenshot_name, full_page=True)
                result["screenshot"] = screenshot_name
                result["steps"].append(f"错误截图已保存: {screenshot_name}")
            except Exception as se:
                result["steps"].append(f"截图失败: {str(se)[:50]}")
    finally:
        # 可选：如果需要无头模式自动关闭，可取消注释（交互式保留浏览器）
        # if headless and page:
        #     page.close()
        pass

    return result
