from langchain_core.tools import tool
import platform

@tool
def uia_click_control(window_title: str = None, control_type: str = None, title: str = None, auto_id: str = None, clicks: int = 1, found_index: int = 0):
    """
    使用 Windows UI Automation 直接点击控件。

    Args:
        window_title: (可选) 窗口标题或正则
        control_type: (可选) 控件类型
        title: (可选) 控件标题或名称
        auto_id: (可选) 控件自动化 ID
        clicks: 点击次数
        found_index: (可选) 当匹配到多个控件时，选择第几个（从0开始）。默认为0。
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
                return f"未找到窗口: {window_title}"
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
        return f"控件点击失败: {e}"
