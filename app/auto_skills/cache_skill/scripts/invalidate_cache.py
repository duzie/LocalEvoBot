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
def invalidate_cache(file_path: str = "", cache_strategy: str = "all"):
    """
    使缓存失效
    Args:
        file_path: 文件路径（可选，为空则清除所有缓存）
        cache_strategy: 缓存策略：all/memory/disk/hybrid
    """
    tool_name = "invalidate_cache"
    try:
        # 验证参数
        if cache_strategy not in ['all', 'memory', 'disk', 'hybrid']:
            return _error_payload("invalid_param", "缓存策略必须是 all/memory/disk/hybrid 之一", tool=tool_name)
        
        # 获取清理前的统计信息
        before_stats = cache_manager.get_cache_stats(cache_strategy='all')
        
        # 使缓存失效
        result = cache_manager.invalidate_cache(
            file_path=file_path if file_path else None,
            cache_strategy=cache_strategy
        )
        
        # 获取清理后的统计信息
        after_stats = cache_manager.get_cache_stats(cache_strategy='all')
        
        # 计算清理效果
        memory_cleaned = result.get('memory_deleted', 0)
        disk_cleaned = result.get('disk_deleted', 0)
        total_cleaned = memory_cleaned + disk_cleaned
        
        if file_path:
            message = f"已使文件缓存失效: {file_path}"
            if total_cleaned > 0:
                message += f" (清理了 {total_cleaned} 个缓存项)"
            else:
                message += " (未找到对应的缓存项)"
        else:
            message = f"已清除所有缓存 (清理了 {total_cleaned} 个缓存项)"
        
        _emit_event(tool_name, "cache_invalidated", 
                   file_path=file_path if file_path else "all",
                   cache_strategy=cache_strategy,
                   memory_cleaned=memory_cleaned,
                   disk_cleaned=disk_cleaned,
                   total_cleaned=total_cleaned)
        
        return _ok_payload(
            message,
            file_path=file_path if file_path else None,
            cache_strategy=cache_strategy,
            memory_cleaned=memory_cleaned,
            disk_cleaned=disk_cleaned,
            total_cleaned=total_cleaned,
            before_stats=before_stats,
            after_stats=after_stats,
            cleanup_result=result
        )
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err