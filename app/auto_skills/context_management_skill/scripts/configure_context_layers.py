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
def configure_context_layers(raw_layer_size_mb: int = 1000, summary_layer_size_mb: int = 100, 
                            semantic_layer_size_mb: int = 500, compression_ratio: float = 0.5, 
                            min_accuracy: float = 0.9):
    """
    配置分层上下文参数
    Args:
        raw_layer_size_mb: 原始层最大缓存大小（MB）
        summary_layer_size_mb: 摘要层最大缓存大小（MB）
        semantic_layer_size_mb: 语义层向量数据库大小（MB）
        compression_ratio: 目标压缩比率（0-1）
        min_accuracy: 最小压缩准确率（0-1）
    """
    tool_name = "configure_context_layers"
    try:
        _emit_event(tool_name, "start", 
                   raw_layer_size_mb=raw_layer_size_mb,
                   summary_layer_size_mb=summary_layer_size_mb,
                   semantic_layer_size_mb=semantic_layer_size_mb,
                   compression_ratio=compression_ratio,
                   min_accuracy=min_accuracy)
        
        # 验证参数
        if raw_layer_size_mb <= 0:
            return _error_payload("invalid_param", 
                                 "原始层大小必须大于0",
                                 tool=tool_name)
        
        if summary_layer_size_mb <= 0:
            return _error_payload("invalid_param", 
                                 "摘要层大小必须大于0",
                                 tool=tool_name)
        
        if semantic_layer_size_mb <= 0:
            return _error_payload("invalid_param", 
                                 "语义层大小必须大于0",
                                 tool=tool_name)
        
        if not 0 < compression_ratio <= 1:
            return _error_payload("invalid_param", 
                                 "压缩比率必须在0到1之间",
                                 tool=tool_name)
        
        if not 0 < min_accuracy <= 1:
            return _error_payload("invalid_param", 
                                 "最小准确率必须在0到1之间",
                                 tool=tool_name)
        
        # 获取上下文管理器
        context_manager = get_context_manager()
        
        # 更新配置
        context_manager.update_config(
            raw_layer_size_mb=raw_layer_size_mb,
            summary_layer_size_mb=summary_layer_size_mb,
            semantic_layer_size_mb=semantic_layer_size_mb,
            compression_ratio=compression_ratio,
            min_accuracy=min_accuracy
        )
        
        # 获取当前配置
        current_config = context_manager.config
        
        result = {
            "message": "上下文层配置已更新",
            "new_config": current_config,
            "raw_layer_size_mb": current_config["raw_layer_size_mb"],
            "summary_layer_size_mb": current_config["summary_layer_size_mb"],
            "semantic_layer_size_mb": current_config["semantic_layer_size_mb"],
            "compression_ratio": current_config["compression_ratio"],
            "min_accuracy": current_config["min_accuracy"],
            "expected_size_reduction": f"{(1 - current_config['compression_ratio']) * 100:.1f}%"
        }
        
        _emit_event(tool_name, "complete", 
                   raw_layer_size_mb=raw_layer_size_mb,
                   summary_layer_size_mb=summary_layer_size_mb,
                   semantic_layer_size_mb=semantic_layer_size_mb)
        
        return _ok_payload(**result)
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err