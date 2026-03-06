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
def configure_cache(max_memory_size_mb: int = 100, max_disk_size_mb: int = 1000,
                   default_ttl_seconds: int = 3600, eviction_policy: str = "lru"):
    """
    配置缓存参数
    Args:
        max_memory_size_mb: 最大内存缓存大小（MB）
        max_disk_size_mb: 最大磁盘缓存大小（MB）
        default_ttl_seconds: 默认缓存过期时间（秒）
        eviction_policy: 淘汰策略：lru/lfu/random
    """
    tool_name = "configure_cache"
    try:
        # 验证参数
        if max_memory_size_mb <= 0:
            return _error_payload("invalid_param", "最大内存缓存大小必须大于0", tool=tool_name)
        
        if max_disk_size_mb <= 0:
            return _error_payload("invalid_param", "最大磁盘缓存大小必须大于0", tool=tool_name)
        
        if default_ttl_seconds <= 0:
            return _error_payload("invalid_param", "默认缓存过期时间必须大于0", tool=tool_name)
        
        if eviction_policy not in ['lru', 'lfu', 'random']:
            return _error_payload("invalid_param", "淘汰策略必须是 lru/lfu/random 之一", tool=tool_name)
        
        # 获取配置前的统计信息
        before_stats = cache_manager.get_cache_stats(cache_strategy='all')
        
        # 配置缓存参数
        config_result = cache_manager.configure_cache(
            max_memory_size_mb=max_memory_size_mb,
            max_disk_size_mb=max_disk_size_mb,
            default_ttl_seconds=default_ttl_seconds,
            eviction_policy=eviction_policy
        )
        
        # 获取配置后的统计信息
        after_stats = cache_manager.get_cache_stats(cache_strategy='all')
        
        # 生成配置摘要
        config_summary = {
            'memory_cache': f"{max_memory_size_mb}MB ({eviction_policy.upper()}淘汰策略)",
            'disk_cache': f"{max_disk_size_mb}MB",
            'default_ttl': f"{default_ttl_seconds}秒 ({default_ttl_seconds/3600:.1f}小时)",
            'cache_strategy': '混合缓存 (内存+磁盘)'
        }
        
        _emit_event(tool_name, "cache_configured", 
                   config_summary=config_summary,
                   before_stats=before_stats.get('summary', {}),
                   after_stats=after_stats.get('summary', {}))
        
        return _ok_payload(
            "缓存配置已更新",
            config_result=config_result,
            config_summary=config_summary,
            before_stats=before_stats,
            after_stats=after_stats,
            recommendations=_generate_config_recommendations(
                max_memory_size_mb, max_disk_size_mb, default_ttl_seconds, eviction_policy
            )
        )
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def _generate_config_recommendations(memory_mb: int, disk_mb: int, ttl_seconds: int, policy: str) -> list:
    """生成配置建议"""
    recommendations = []
    
    # 内存缓存建议
    if memory_mb < 50:
        recommendations.append("内存缓存大小较小 (<50MB)，对于大文件处理可能不够用")
    elif memory_mb > 1024:
        recommendations.append("内存缓存大小较大 (>1GB)，注意系统内存使用情况")
    
    # 磁盘缓存建议
    if disk_mb < 500:
        recommendations.append("磁盘缓存大小较小 (<500MB)，可能无法缓存大量文件")
    elif disk_mb > 10000:
        recommendations.append("磁盘缓存大小较大 (>10GB)，确保有足够的磁盘空间")
    
    # TTL建议
    if ttl_seconds < 300:
        recommendations.append("缓存过期时间较短 (<5分钟)，可能导致频繁缓存失效")
    elif ttl_seconds > 86400:
        recommendations.append("缓存过期时间较长 (>24小时)，可能缓存过时内容")
    
    # 淘汰策略建议
    if policy == 'lru':
        recommendations.append("LRU淘汰策略适合大多数访问模式")
    elif policy == 'lfu':
        recommendations.append("LFU淘汰策略适合热点数据访问模式")
    else:
        recommendations.append("随机淘汰策略简单但可能不是最优选择")
    
    # 性能优化建议
    if memory_mb >= 100 and disk_mb >= 1000:
        recommendations.append("当前配置适合处理中等规模项目")
    
    if memory_mb >= 500 and disk_mb >= 5000:
        recommendations.append("当前配置适合处理大规模项目")
    
    return recommendations