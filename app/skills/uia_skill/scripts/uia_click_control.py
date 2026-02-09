from langchain_core.tools import tool
import platform
import ctypes

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

@tool
def uia_click_control(window_title: str = None, control_type: str = None, title: str = None, auto_id: str = None, clicks: int = 1, found_index: int = 0):
    """
    使用 Windows UI Automation 直接点击控件。
    
    Args:
        window_title: (可选) 窗口标题或正则
    """
    if platform.system() != "Windows":
        return "当前仅支持 Windows UI Automation"
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                msg = f"未找到窗口: {window_title}"
                if not _is_admin():
                    msg += "\n[提示] 权限提示：若目标窗口是管理员权限，请尝试以管理员身份运行 Agent。"
                return msg
        criteria = {}
        if title:
            criteria["title"] = title
        if control_type:
            criteria["control_type"] = control_type
        if auto_id:
            criteria["auto_id"] = auto_id
        if found_index < 0:
            found_index = 0
        target = root.child_window(found_index=found_index, **criteria)
        if not target.exists(timeout=1):
            return "未找到匹配控件"
        for _ in range(max(1, clicks)):
            target.click_input()
        return "已点击控件"
    except Exception as e:
        msg = f"控件点击失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 操作失败可能是因为权限不足。若目标程序以管理员运行，请以管理员身份运行此 Agent。"
        return msg
