from langchain_core.tools import tool
"""
菜么么库存管理系统采购入库操作工具
同步执行，用于打开菜么么库存页面并导航到采购入库功能
"""

import asyncio
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, BrowserContext
import time


def open_caimomo_purchase_in(
    url: str = "https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    headless: bool = False
) -> Dict[str, Any]:
    """
    打开菜么么库存管理系统并导航到采购入库页面
    
    同步执行，包含完整的操作流程：
    1. 打开库存页面
    2. 展开库存管理菜单
    3. 点击采购入库选项
    
    Args:
        url: 菜么么库存页面URL，默认为库存管理页面
        headless: 是否无头模式，默认False（显示浏览器）
    
    Returns:
        包含操作结果的字典
    """
    result = {
        "success": False,
        "message": "",
        "steps": [],
        "error": None
    }
    
    playwright = None
    browser = None
    context = None
    page = None
    
    try:
        # 步骤1: 初始化Playwright
        result["steps"].append("初始化Playwright")
        playwright = await async_playwright().start()
        
        # 步骤2: 启动浏览器
        result["steps"].append(f"启动浏览器（无头模式：{headless}）")
        browser = await playwright.chromium.launch(headless=headless)
        
        # 步骤3: 创建上下文和页面
        result["steps"].append("创建浏览器上下文和页面")
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # 步骤4: 导航到菜么么库存页面
        result["steps"].append(f"导航到菜么么库存页面: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        
        # 等待页面加载完成
        await page.wait_for_load_state("networkidle")
        
        # 检查页面标题，确认是否成功加载
        page_title = await page.title()
        result["steps"].append(f"页面标题: {page_title}")
        
        # 等待页面完全加载
        await asyncio.sleep(2)
        
        # 步骤5: 展开"库存管理"菜单
        result["steps"].append("展开'库存管理'菜单")
        
        # 尝试多种方式定位库存管理菜单
        menu_selectors = [
            "text=库存管理",
            "//span[contains(text(), '库存管理')]",
            "//div[contains(text(), '库存管理')]",
            "//li[contains(text(), '库存管理')]"
        ]
        
        menu_found = False
        for selector in menu_selectors:
            try:
                menu_element = await page.wait_for_selector(selector, timeout=5000)
                if menu_element:
                    # 检查菜单是否已经展开
                    menu_class = await menu_element.get_attribute("class") or ""
                    if "collapsed" in menu_class or "closed" in menu_class:
                        # 点击展开菜单
                        await menu_element.click()
                        result["steps"].append("点击展开库存管理菜单")
                    else:
                        result["steps"].append("库存管理菜单已展开")
                    menu_found = True
                    break
            except Exception:
                continue
        
        if not menu_found:
            # 如果通过文本找不到，尝试通过页面结构查找
            try:
                # 查找所有可点击的菜单项
                all_menus = await page.query_selector_all("a, button, div[role='button'], li")
                for menu in all_menus:
                    menu_text = await menu.text_content() or ""
                    if "库存管理" in menu_text.strip():
                        await menu.click()
                        result["steps"].append("通过页面结构找到并点击库存管理菜单")
                        menu_found = True
                        break
            except Exception:
                pass
        
        if not menu_found:
            raise Exception("未找到库存管理菜单")
        
        # 等待菜单展开动画
        await asyncio.sleep(1)
        
        # 步骤6: 点击"采购入库"选项
        result["steps"].append("点击'采购入库'选项")
        
        # 尝试多种方式定位采购入库选项
        purchase_selectors = [
            "text=采购入库",
            "//a[contains(text(), '采购入库')]",
            "//span[contains(text(), '采购入库')]",
            "//li[contains(text(), '采购入库')]"
        ]
        
        purchase_found = False
        for selector in purchase_selectors:
            try:
                purchase_element = await page.wait_for_selector(selector, timeout=5000)
                if purchase_element:
                    await purchase_element.click()
                    result["steps"].append("点击采购入库选项")
                    purchase_found = True
                    break
            except Exception:
                continue
        
        if not purchase_found:
            # 如果通过文本找不到，尝试通过页面结构查找
            try:
                # 在展开的菜单中查找采购入库
                all_options = await page.query_selector_all("a, li, div.menu-item")
                for option in all_options:
                    option_text = await option.text_content() or ""
                    if "采购入库" in option_text.strip():
                        await option.click()
                        result["steps"].append("通过页面结构找到并点击采购入库选项")
                        purchase_found = True
                        break
            except Exception:
                pass
        
        if not purchase_found:
            raise Exception("未找到采购入库选项")
        
        # 等待采购入库页面加载
        await asyncio.sleep(2)
        
        # 步骤7: 验证采购入库页面是否成功加载
        result["steps"].append("验证采购入库页面加载")
        
        # 检查页面URL或标题变化
        current_url = page.url
        result["steps"].append(f"当前URL: {current_url}")
        
        # 检查是否有iframe加载采购入库内容
        frames = page.frames
        if len(frames) > 1:
            # 通常菜么么系统会在iframe中加载功能页面
            for frame in frames:
                frame_url = frame.url
                if "purchase" in frame_url.lower() or "入库" in frame_url.lower():
                    result["steps"].append(f"找到采购入库iframe: {frame_url}")
                    break
        
        # 检查页面中是否有采购入库相关元素
        purchase_indicators = [
            "采购入库单",
            "采购入库",
            "入库管理",
            "采购单号"
        ]
        
        page_content = await page.content()
        for indicator in purchase_indicators:
            if indicator in page_content:
                result["steps"].append(f"页面包含采购入库标识: {indicator}")
                break
        
        # 最终等待确保页面稳定
        await asyncio.sleep(1)
        
        result["success"] = True
        result["message"] = "成功打开菜么么库存管理系统并导航到采购入库页面"
        result["steps"].append("操作完成")
        
    except Exception as e:
        result["success"] = False
        result["message"] = f"打开采购入库页面失败: {str(e)}"
        result["error"] = str(e)
        result["steps"].append(f"错误: {str(e)}")
        
        # 如果页面已打开，尝试截图
        if page:
            try:
                screenshot_path = f"caimomo_purchase_error_{int(time.time())}.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                result["screenshot"] = screenshot_path
                result["steps"].append(f"错误截图已保存: {screenshot_path}")
            except Exception as screenshot_error:
                result["steps"].append(f"截图失败: {str(screenshot_error)}")
    
    finally:
        # 注意：这里不关闭浏览器，让用户继续操作
        # 只清理资源但不关闭页面
        if playwright:
            # 保持浏览器打开状态
            result["steps"].append("浏览器保持打开状态，用户可继续操作")
    
    return result


@tool
def open_caimomo_purchase_in_sync(
    url: str = "https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    headless: bool = False
) -> Dict[str, Any]:
    """
    同步版本的菜么么采购入库打开函数
    包装异步函数以便在同步环境中使用
    """
    return asyncio.run(open_caimomo_purchase_in(url, headless))


# 主函数，用于直接测试
if __name__ == "__main__":
    print("测试菜么么采购入库打开功能...")
    result = open_caimomo_purchase_in_sync(headless=False)
    print(f"操作结果: {result['success']}")
    print(f"消息: {result['message']}")
    print("步骤记录:")
    for i, step in enumerate(result["steps"], 1):
        print(f"  {i}. {step}")
    if result.get("error"):
        print(f"错误: {result['error']}")