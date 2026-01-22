from langchain_core.tools import tool
import platform
import time

@tool
def uia_activate_window(window_title: str):
    """
    激活并前置指定窗口（如果窗口被最小化，会尝试还原）。
    当 uia_click_control 提示“未找到匹配控件”但 uia_list_controls 能看到窗口时，请先使用此技能。

    Args:
        window_title: 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
    """
    if platform.system() != "Windows":
        return "当前仅支持 Windows UI Automation"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        # 使用 title_re 进行模糊匹配
        window = desktop.window(title_re=window_title)
        
        if not window.exists(timeout=2):
            return f"未找到窗口: {window_title}"
            
        # 尝试还原和激活
        # 注意: minimize() / restore() 等方法有时需要 wrapper
        # 这里尝试直接调用 set_focus()，pywinauto 通常会自动处理 restore
        try:
            if window.get_show_state() == 2: # 2 = Minimized
                window.restore()
        except Exception:
            # 如果 get_show_state 失败，盲试 restore
            try:
                window.restore()
            except:
                pass
        
        window.set_focus()
        return f"已激活窗口: {window_title}"
    except Exception as e:
        return f"激活窗口失败: {e}"
