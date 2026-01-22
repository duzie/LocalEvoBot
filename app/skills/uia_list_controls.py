from langchain_core.tools import tool
import platform
import json

@tool
def uia_list_controls(window_title: str = None, control_type: str = None, title_contains: str = None, max_results: int = 50, depth: int = 3):
    """
    枚举指定窗口的控件树（简化版），用于探索控件名称与类型。

    Args:
        window_title: (可选) 窗口标题或正则
        control_type: (可选) 控件类型过滤
        title_contains: (可选) 标题包含过滤
        max_results: 最大返回数量
        depth: 最大遍历深度
    """
    if platform.system() != "Windows":
        return json.dumps({"error": "当前仅支持 Windows UI Automation"}, ensure_ascii=False)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                return json.dumps({"error": f"未找到窗口: {window_title}"}, ensure_ascii=False)
        results = []
        type_filter = control_type.lower() if control_type else None
        title_filter = title_contains.lower() if title_contains else None

        def walk(elem, current_depth):
            if len(results) >= max_results or current_depth > depth:
                return
            try:
                info = elem.element_info
                name = (info.name or "").strip()
                ctype = (info.control_type or "").strip()
                auto_id = (info.automation_id or "").strip()
                if type_filter and type_filter not in ctype.lower():
                    pass
                else:
                    if title_filter and title_filter not in name.lower():
                        pass
                    else:
                        results.append({
                            "name": name,
                            "control_type": ctype,
                            "auto_id": auto_id
                        })
                for child in elem.children():
                    walk(child, current_depth + 1)
            except Exception:
                return

        walk(root, 0)
        return json.dumps(results, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)
