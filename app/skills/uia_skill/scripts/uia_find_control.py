from langchain_core.tools import tool
import platform
import json

@tool
def uia_find_control(window_title: str = None, control_type: str = None, title: str = None, auto_id: str = None, found_index: int = 0):
    """
    使用 Windows UI Automation 定位控件并返回坐标信息。

    Args:
        window_title: (可选) 窗口标题或正则，例如 "微信" 或 ".*WeChat.*"
        control_type: (可选) 控件类型，例如 "Button", "Edit", "ListItem"
        title: (可选) 控件标题或名称
        auto_id: (可选) 控件自动化 ID
        found_index: (可选) 当匹配到多个控件时，选择第几个（从0开始）。默认为0。
    """
    if platform.system() != "Windows":
        return json.dumps({"found": False, "error": "当前仅支持 Windows UI Automation"})
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                return json.dumps({"found": False, "error": f"未找到窗口: {window_title}"})
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
            return json.dumps({"found": False, "error": "未找到匹配控件"})
        rect = target.rectangle()
        x = int((rect.left + rect.right) / 2)
        y = int((rect.top + rect.bottom) / 2)
        return json.dumps({
            "found": True,
            "x": x,
            "y": y,
            "rect": {"left": rect.left, "top": rect.top, "right": rect.right, "bottom": rect.bottom}
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"found": False, "error": str(e)}, ensure_ascii=False)
