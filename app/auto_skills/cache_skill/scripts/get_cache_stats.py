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
def get_cache_stats(cache_strategy: str = "all"):
    """
    获取缓存统计信息
    Args:
        cache_strategy: 缓存策略：all/memory/disk/hybrid
    """
    tool_name = "get_cache_stats"
    try:
        # 验证参数
        if cache_strategy not in ['all', 'memory', 'disk', 'hybrid']:
            return _error_payload("invalid_param", "缓存策略必须是 all/memory/disk/hybrid 之一", tool=tool_name)
        
        # 获取缓存统计信息
        stats = cache_manager.get_cache_stats(cache_strategy=cache_strategy)
        
        # 分析统计信息
        analysis = _analyze_cache_stats(stats)
        
        _emit_event(tool_name, "stats_retrieved", 
                   cache_strategy=cache_strategy,
                   stats_summary=analysis.get('summary', {}))
        
        return _ok_payload(
            "缓存统计信息获取成功",
            cache_strategy=cache_strategy,
            stats=stats,
            analysis=analysis,
            summary=analysis.get('summary', {})
        )
        
    except Exception as e:
        err = _error_payload("unknown_error", f"未知错误: {e}", tool=tool_name)
        _emit_event(tool_name, "error", error=str(e))
        return err


def _analyze_cache_stats(stats: Dict[str, Any]) -> Dict[str, Any]:
    """分析缓存统计信息"""
    analysis = {
        'summary': {},
        'recommendations': [],
        'warnings': [],
        'performance_metrics': {}
    }
    
    # 分析内存缓存
    if 'memory' in stats:
        memory_stats = stats['memory']
        hit_rate = memory_stats.get('hit_rate', 0)
        size_mb = memory_stats.get('size_mb', 0)
        max_size_mb = memory_stats.get('max_size_mb', 100)
        usage_percent = (size_mb / max_size_mb * 100) if max_size_mb > 0 else 0
        
        analysis['performance_metrics']['memory'] = {
            'hit_rate': hit_rate,
            'usage_percent': round(usage_percent, 2),
            'efficiency': '高' if hit_rate > 70 else '中' if hit_rate > 50 else '低'
        }
        
        if hit_rate < 50:
            analysis['recommendations'].append("内存缓存命中率较低，考虑调整缓存策略或增加缓存大小")
        
        if usage_percent > 80:
            analysis['warnings'].append(f"内存缓存使用率较高 ({usage_percent:.1f}%)，可能影响性能")
    
    # 分析磁盘缓存
    if 'disk' in stats:
        disk_stats = stats['disk']
        size_mb = disk_stats.get('size_mb', 0)
        max_size_mb = disk_stats.get('max_size_mb', 1000)
        usage_percent = (size_mb / max_size_mb * 100) if max_size_mb > 0 else 0
        expired_count = disk_stats.get('expired_count', 0)
        item_count = disk_stats.get('item_count', 0)
        
        analysis['performance_metrics']['disk'] = {
            'usage_percent': round(usage_percent, 2),
            'expired_ratio': round(expired_count / item_count * 100, 2) if item_count > 0 else 0,
            'health': '良好' if usage_percent < 70 and expired_count < item_count * 0.1 else '需关注'
        }
        
        if expired_count > item_count * 0.2:
            analysis['recommendations'].append(f"磁盘缓存有过期项 ({expired_count}个)，建议清理")
        
        if usage_percent > 90:
            analysis['warnings'].append(f"磁盘缓存使用率较高 ({usage_percent:.1f}%)，接近容量上限")
    
    # 总体分析
    if 'overall' in stats:
        overall_stats = stats['overall']
        overall_hit_rate = overall_stats.get('hit_rate', 0)
        
        analysis['summary']['overall_hit_rate'] = f"{overall_hit_rate}%"
        analysis['summary']['performance'] = '优秀' if overall_hit_rate > 80 else '良好' if overall_hit_rate > 60 else '一般'
        
        if overall_hit_rate < 60:
            analysis['recommendations'].append(f"总体缓存命中率较低 ({overall_hit_rate}%)，建议优化缓存策略")
    
    # 生成总结
    if analysis['performance_metrics']:
        analysis['summary']['status'] = '正常'
        if analysis['warnings']:
            analysis['summary']['status'] = '需关注'
        if len(analysis['warnings']) > 2:
            analysis['summary']['status'] = '警告'
    
    return analysis