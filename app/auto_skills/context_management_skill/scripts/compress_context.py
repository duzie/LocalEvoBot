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
def compress_context(file_path: str = None, target_ratio: float = 0.5, preserve_structure: bool = True, preserve_keywords: bool = True):
    """
    压缩上下文，减少大小
    Args:
        file_path: 文件路径
        target_ratio: 目标压缩比率（0-1）
        preserve_structure: 是否保留代码结构
        preserve_keywords: 是否保留关键词
    """
    tool_name = "compress_context"
    try:
        _emit_event(tool_name, "start", 
                   file_path=file_path, 
                   target_ratio=target_ratio,
                   preserve_structure=preserve_structure,
                   preserve_keywords=preserve_keywords)
        
        if not file_path:
            return _error_payload("missing_param", "缺少文件路径参数", tool=tool_name)
        
        # 验证参数
        if not 0 < target_ratio <= 1:
            return _error_payload("invalid_param", 
                                 "目标压缩比率必须在0到1之间",
                                 tool=tool_name)
        
        # 获取上下文管理器
        context_manager = get_context_manager()
        
        # 压缩上下文
        result = context_manager.compress_context(
            file_path=file_path,
            target_ratio=target_ratio,
            preserve_structure=preserve_structure,
            preserve_keywords=preserve_keywords
        )
        
        _emit_event(tool_name, "complete", 
                   file_path=file_path, 
                   success=result.get("ok", False))
        
        return result
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err