from langchain_core.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
from web.backend.shared import shared
from .context_manager import get_context_manager

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
def analyze_file_context(file_path: str = None, file_type: str = "auto", max_raw_size_kb: int = 100, generate_summary: bool = True):
    """
    分析文件上下文信息，生成分层表示
    Args:
        file_path: 文件路径
        file_type: 文件类型：auto/py/cs/js/html/md等
        max_raw_size_kb: 最大原始内容大小（KB）
        generate_summary: 是否生成摘要
    """
    tool_name = "analyze_file_context"
    try:
        _emit_event(tool_name, "start", file_path=file_path, file_type=file_type)
        
        if not file_path:
            return _error_payload("missing_param", "缺少文件路径参数", tool=tool_name)
        
        # 获取上下文管理器
        context_manager = get_context_manager()
        
        # 分析文件
        result = context_manager.analyze_file(
            file_path=file_path,
            max_raw_size_kb=max_raw_size_kb,
            generate_summary=generate_summary
        )
        
        _emit_event(tool_name, "complete", 
                   file_path=file_path, 
                   success=result.get("ok", False))
        
        return result
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err