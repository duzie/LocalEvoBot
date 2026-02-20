from langchain_core.tools import tool
import platform
import json
from datetime import datetime
from typing import Any, Dict
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
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

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
    tool_name = "uia_list_controls"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows UI Automation", tool=tool_name)
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        root = desktop
        if window_title:
            root = desktop.window(title_re=window_title)
            if not root.exists(timeout=1):
                return _error_payload("window_not_found", f"未找到窗口: {window_title}", tool=tool_name)
        results = []
        type_filter = control_type.lower() if control_type else None
        title_filter = title_contains.lower() if title_contains else None
        max_results_val = max(1, int(max_results or 1))
        depth_val = max(0, int(depth or 0))

        def walk(elem, current_depth):
            if len(results) >= max_results_val or current_depth > depth_val:
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
        _emit_event(tool_name, "list_controls", count=len(results))
        return _ok_payload("已列出控件", results=results, count=len(results))
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("list_controls_failed", str(e), tool=tool_name)
