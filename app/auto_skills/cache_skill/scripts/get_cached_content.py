from langchain_core.tools import tool
import json
from datetime import datetime
from typing import Dict, Any
from web.backend.shared import shared
from .cache_manager import cache_manager
import time


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
def get_cached_content(file_path: str, cache_strategy: str = "auto"):
    """
    获取缓存的文件内容
    Args:
        file_path: 文件路径
        cache_strategy: 缓存策略：auto/memory/disk/hybrid
    """
    tool_name = "get_cached_content"
    try:
        # 验证参数
        if not file_path:
            return _error_payload("invalid_param", "文件路径不能为空", tool=tool_name)
        
        if cache_strategy not in ['auto', 'memory', 'disk', 'hybrid']:
            return _error_payload("invalid_param", "缓存策略必须是 auto/memory/disk/hybrid 之一", tool=tool_name)
        
        # 记录开始时间，用于性能监控
        start_time = time.time()
        
        # 获取缓存内容
        content = cache_manager.get_cached_content(
            file_path=file_path,
            cache_strategy=cache_strategy
        )
        
        # 计算响应时间
        response_time_ms = (time.time() - start_time) * 1000
        
        if content is not None:
            # 获取缓存统计信息
            stats = cache_manager.get_cache_stats(cache_strategy='all')
            
            _emit_event(tool_name, "cache_hit", 
                       file_path=file_path, 
                       cache_strategy=cache_strategy,
                       response_time_ms=response_time_ms,
                       content_size=len(str(content)))
            
            return _ok_payload(
                f"成功从缓存获取文件内容 (响应时间: {response_time_ms:.2f}ms)",
                file_path=file_path,
                content=content,
                cache_strategy=cache_strategy,
                response_time_ms=round(response_time_ms, 2),
                cache_hit=True,
                cache_stats=stats
            )
        else:
            _emit_event(tool_name, "cache_miss", 
                       file_path=file_path, 
                       cache_strategy=cache_strategy,
                       response_time_ms=response_time_ms)
            
            return _ok_payload(
                f"缓存未命中，文件内容不在缓存中 (响应时间: {response_time_ms:.2f}ms)",
                file_path=file_path,
                cache_strategy=cache_strategy,
                response_time_ms=round(response_time_ms, 2),
                cache_hit=False,
                content=None
            )
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err