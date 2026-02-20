from langchain_core.tools import tool
import platform
import json
import ctypes
from typing import Dict, List, Any
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
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def _get_element_info(element) -> Dict[str, Any]:
    """Helper to extract safe element info"""
    try:
        # Check if it needs unwrapping (e.g. WindowSpecification)
        if hasattr(element, "wrapper_object"):
            wrapper = element.wrapper_object()
        else:
            wrapper = element
        
        info = {
            "control_type": wrapper.element_info.control_type,
            "name": wrapper.element_info.name,
            "auto_id": wrapper.element_info.automation_id,
            "class_name": wrapper.element_info.class_name,
            "enabled": wrapper.is_enabled(),
            "visible": wrapper.is_visible(),
        }
        
        # Get rectangle safely
        try:
            rect = wrapper.rectangle()
            info["rect"] = {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.width(),
                "height": rect.height()
            }
        except:
            info["rect"] = None
            
        # Get text content if available (for Edit/Text controls)
        try:
            if hasattr(wrapper, 'texts'):
                texts = wrapper.texts()
                if texts and texts[0]:
                    info["value"] = texts[0]
        except:
            pass
            
        return info
    except Exception as e:
        return {"error": str(e)}

@tool
def uia_dump_tree(window_title: str = None, depth: int = 5, max_children: int = 20, output_format: str = "json") -> Dict[str, Any]:
    """
    获取指定窗口的 UI 控件树结构（分层分析）。
    
    Args:
        window_title: (可选) 窗口标题或正则。如果不传，则尝试获取当前活动窗口。
        depth: (可选) 遍历的最大深度，默认 5。
        max_children: (可选) 每个节点最大返回子节点数，默认 20。防止树过大。
        output_format: (可选) 输出格式，支持 "json" 或 "xml" (简化版)。默认 "json"。
    """
    tool_name = "uia_dump_tree"
    if platform.system() != "Windows":
        return _error_payload("unsupported_platform", "当前仅支持 Windows UI Automation", tool=tool_name)

    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        
        target = None
        if window_title:
            target = desktop.window(title_re=window_title)
            if not target.exists(timeout=2):
                msg = f"未找到窗口: {window_title}"
                if not _is_admin():
                    msg += "\n[提示] 权限提示：若目标窗口是管理员权限，请尝试以管理员身份运行 Agent。"
                return _error_payload("window_not_found", msg, tool=tool_name, is_admin=_is_admin())
        else:
            return _error_payload("invalid_args", "请指定 window_title 以精确定位窗口。", tool=tool_name)

        # 定义递归遍历函数
        def walk(element, current_depth):
            if current_depth > depth:
                return None
            
            node_info = _get_element_info(element)
            
            # 过滤不可见元素? 可选。这里保留，但在前端展示时可能需要过滤。
            # 为了 LLM 分析，通常只需要 visible 的
            # if not node_info.get("visible", True):
            #      return None

            children_nodes = []
            try:
                # 获取子元素
                children = element.children()
                for i, child in enumerate(children):
                    if i >= max_children:
                        children_nodes.append({"_truncated": f"剩余 {len(children) - i} 个子节点未显示..."})
                        break
                    
                    child_node = walk(child, current_depth + 1)
                    if child_node:
                        children_nodes.append(child_node)
            except Exception:
                pass
            
            if children_nodes:
                node_info["children"] = children_nodes
                
            return node_info

        # 开始遍历 (target 是 WindowSpecification, 需要 wrapper_object)
        root_element = target.wrapper_object()
        tree = walk(root_element, 0)
        
        output_format_val = str(output_format or "json").lower()
        if output_format_val == "xml":
            data = _to_xml(tree)
            _emit_event(tool_name, "dump_tree", format="xml")
            return _ok_payload("控件树获取完成", format="xml", data=data)
        _emit_event(tool_name, "dump_tree", format="json")
        return _ok_payload("控件树获取完成", format="json", data=tree)

    except Exception as e:
        msg = f"获取控件树失败: {e}"
        if not _is_admin():
            msg += "\n[提示] 权限提示：若目标窗口是管理员权限，请尝试以管理员身份运行 Agent。"
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("dump_tree_failed", msg, tool=tool_name, is_admin=_is_admin())

def _to_xml(node, level=0):
    """Helper to convert JSON tree to simplified XML string"""
    if not node:
        return ""
    
    if "_truncated" in node:
        return "  " * level + f"<!-- {node['_truncated']} -->\n"

    indent = "  " * level
    tag = node.get("control_type", "Control").replace(" ", "")
    
    # 构建属性字符串
    attrs = []
    if node.get("name"):
        attrs.append(f'Name="{node["name"]}"')
    if node.get("auto_id"):
        attrs.append(f'AutomationId="{node["auto_id"]}"')
    if node.get("value"):
        attrs.append(f'Value="{node["value"]}"')
        
    attr_str = " " + " ".join(attrs) if attrs else ""
    
    # 递归处理子节点
    children = node.get("children", [])
    if children:
        xml = f"{indent}<{tag}{attr_str}>\n"
        for child in children:
            xml += _to_xml(child, level + 1)
        xml += f"{indent}</{tag}>\n"
    else:
        xml = f"{indent}<{tag}{attr_str} />\n"
        
    return xml
