from langchain_core.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
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
def incremental_file_edit(file_path: str, operation: str, target_pattern: str, content: str, create_backup: bool = True):
    """
    增量编辑文件，只修改指定部分
    Args:
        file_path: 目标文件路径
        operation: 操作类型：insert_before/insert_after/replace/delete
        target_pattern: 目标位置模式（正则表达式）
        content: 要插入或替换的内容
        create_backup: 是否创建备份
    """
    tool_name = "incremental_file_edit"
    try:
        err = _error_payload("not_implemented", "未实现", tool=tool_name)
        _emit_event(tool_name, "not_implemented")
        return err
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err
