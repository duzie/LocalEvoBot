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
def optimize_context_layers(target_reduction: float = 0.5, min_accuracy: float = 0.9):
    """
    优化上下文层配置
    Args:
        target_reduction: 目标大小减少比率（0-1）
        min_accuracy: 最小准确率（0-1）
    """
    tool_name = "optimize_context_layers"
    try:
        _emit_event(tool_name, "start", 
                   target_reduction=target_reduction,
                   min_accuracy=min_accuracy)
        
        # 验证参数
        if not 0 < target_reduction <= 1:
            return _error_payload("invalid_param", 
                                 "目标减少比率必须在0到1之间",
                                 tool=tool_name)
        
        if not 0 < min_accuracy <= 1:
            return _error_payload("invalid_param", 
                                 "最小准确率必须在0到1之间",
                                 tool=tool_name)
        
        # 获取上下文管理器
        context_manager = get_context_manager()
        
        # 优化上下文层
        result = context_manager.optimize_context_layers(
            target_reduction=target_reduction,
            min_accuracy=min_accuracy
        )
        
        _emit_event(tool_name, "complete", 
                   success=result.get("ok", False))
        
        return result
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err