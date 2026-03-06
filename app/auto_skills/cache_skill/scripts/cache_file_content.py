from langchain_core.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
from web.backend.shared import shared
from .cache_manager import cache_manager


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
def cache_file_content(file_path: str, content: str, cache_strategy: str = "memory", ttl_seconds: int = 3600):
    """
    缓存文件内容，支持多种缓存策略
    Args:
        file_path: 文件路径
        content: 文件内容
        cache_strategy: 缓存策略：memory/disk/hybrid
        ttl_seconds: 缓存过期时间（秒）
    """
    tool_name = "cache_file_content"
    try:
        # 验证参数
        if not file_path:
            return _error_payload("invalid_param", "文件路径不能为空", tool=tool_name)
        
        if not content:
            return _error_payload("invalid_param", "文件内容不能为空", tool=tool_name)
        
        if cache_strategy not in ['memory', 'disk', 'hybrid']:
            return _error_payload("invalid_param", "缓存策略必须是 memory/disk/hybrid 之一", tool=tool_name)
        
        if ttl_seconds <= 0:
            return _error_payload("invalid_param", "缓存过期时间必须大于0", tool=tool_name)
        
        # 缓存文件内容
        success = cache_manager.cache_file_content(
            file_path=file_path,
            content=content,
            cache_strategy=cache_strategy,
            ttl_seconds=ttl_seconds
        )
        
        if success:
            # 获取缓存统计信息
            stats = cache_manager.get_cache_stats(cache_strategy='all')
            
            _emit_event(tool_name, "cache_success", 
                       file_path=file_path, 
                       cache_strategy=cache_strategy,
                       ttl_seconds=ttl_seconds,
                       content_size=len(content))
            
            return _ok_payload(
                f"文件内容已成功缓存 ({cache_strategy}策略)",
                file_path=file_path,
                cache_strategy=cache_strategy,
                ttl_seconds=ttl_seconds,
                content_size=len(content),
                cache_stats=stats
            )
        else:
            _emit_event(tool_name, "cache_failed", 
                       file_path=file_path, 
                       cache_strategy=cache_strategy,
                       error="缓存失败")
            
            return _error_payload("cache_failed", "文件内容缓存失败", 
                                 tool=tool_name, 
                                 file_path=file_path,
                                 cache_strategy=cache_strategy)
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err