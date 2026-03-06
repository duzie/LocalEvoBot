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
def get_context_stats(file_path: str = "", layer: str = "all"):
    """
    获取上下文统计信息
    Args:
        file_path: 文件路径（空表示所有文件）
        layer: 上下文层：all/raw/summary/semantic/metadata
    """
    tool_name = "get_context_stats"
    try:
        _emit_event(tool_name, "start", file_path=file_path, layer=layer)
        
        # 验证层参数
        valid_layers = ["all", "raw", "summary", "semantic", "metadata"]
        if layer not in valid_layers:
            return _error_payload("invalid_param", 
                                 f"无效的层参数: {layer}，有效值: {', '.join(valid_layers)}",
                                 tool=tool_name)
        
        # 获取上下文管理器
        context_manager = get_context_manager()
        
        # 获取统计信息
        result = context_manager.get_context_stats(
            file_path=file_path,
            layer=layer
        )
        
        _emit_event(tool_name, "complete", 
                   file_path=file_path, 
                   layer=layer,
                   success=result.get("ok", False))
        
        return result
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err