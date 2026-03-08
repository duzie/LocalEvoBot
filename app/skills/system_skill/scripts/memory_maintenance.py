"""
Memory Maintenance Tools - 记忆维护工具

定期整理和优化记忆系统，避免记忆膨胀和质量下降。
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from langchain_core.tools import tool

from .experience_tools import (
    get_operation_experience,
    add_operation_experience,
    list_operation_experiences,
    _init_components,
    invalidate_retriever_cache,
)


def _get_memory_dir() -> str:
    """获取 memory 目录路径"""
    current = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(current, "memory")


def _get_memory_md_path() -> str:
    """获取 MEMORY.md 路径"""
    return os.path.join(_get_memory_dir(), "MEMORY.md")


def compress_old_memories(days_old: int = 30) -> str:
    """
    压缩旧记忆
    
    Args:
        days_old: 多少天前的记忆需要压缩
    """
    cutoff = datetime.now() - timedelta(days=days_old)
    all_memories = list_operation_experiences(limit=1000)
    
    compressed_count = 0
    for mem in all_memories:
        try:
            created = datetime.fromisoformat(mem["created_at"].replace('Z', '+00:00'))
            if created.replace(tzinfo=None) < cutoff:
                # 标记为需要压缩（实际应该合并到摘要中）
                compressed_count += 1
        except Exception:
            continue
    
    return f"标记了 {compressed_count} 条旧记忆用于压缩（>{days_old}天）"


def merge_similar_memories(threshold: float = 0.85) -> str:
    """
    合并相似记忆
    
    Args:
        threshold: 相似度阈值 (0-1)
    """
    all_memories = list_operation_experiences(limit=500)
    merged_count = 0
    
    # 按系统分组
    by_system: Dict[str, List] = {}
    for mem in all_memories:
        system = mem.get("system", "unknown")
        if system not in by_system:
            by_system[system] = []
        by_system[system].append(mem)
    
    # 在每组内查找相似记忆
    for system, memories in by_system.items():
        for i, mem1 in enumerate(memories):
            for mem2 in memories[i+1:]:
                content1 = mem1.get("content", "")
                content2 = mem2.get("content", "")
                
                # 简单相似度计算（可以优化）
                if len(content1) == 0 or len(content2) == 0:
                    continue
                
                # 检查是否有大量重叠
                words1 = set(content1.lower().split())
                words2 = set(content2.lower().split())
                
                if len(words1) == 0 or len(words2) == 0:
                    continue
                
                similarity = len(words1 & words2) / len(words1 | words2)
                
                if similarity > threshold:
                    # 合并标签
                    tags1 = mem1.get("tags", [])
                    tags2 = mem2.get("tags", [])
                    merged_tags = list(set(tags1 + tags2))
                    
                    # 合并内容（简化版：直接拼接）
                    merged_content = f"{content1}\n\nRelated: {content2}"
                    
                    # 添加合并后的经验
                    add_operation_experience(
                        system_name=system,
                        content=merged_content,
                        tags=merged_tags
                    )
                    
                    merged_count += 1
    
    invalidate_retriever_cache()
    return f"合并了 {merged_count} 对相似记忆"


def cleanup_short_term_markdown(days_old: int = 7) -> str:
    """
    清理短期记忆 Markdown 归档
    
    Args:
        days_old: 保留最近多少天的文件
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    md_dir = os.path.join(base_dir, "app", "data", "short_term_markdown")
    
    if not os.path.exists(md_dir):
        return "短期记忆 Markdown 目录不存在"
    
    cutoff = datetime.now() - timedelta(days=days_old)
    deleted = 0
    
    for filename in os.listdir(md_dir):
        if filename.endswith(".md"):
            filepath = os.path.join(md_dir, filename)
            try:
                mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
                if mtime < cutoff:
                    os.remove(filepath)
                    deleted += 1
            except Exception as e:
                print(f"清理失败 {filepath}: {e}")
    
    return f"清理了 {deleted} 个旧 Markdown 文件（>{days_old}天）"


def review_memory_quality() -> Dict:
    """
    检查记忆质量
    
    Returns:
        质量报告
    """
    all_memories = list_operation_experiences(limit=1000)
    
    # 统计
    total = len(all_memories)
    by_system: Dict[str, int] = {}
    recent_count = 0
    old_count = 0
    
    cutoff = datetime.now() - timedelta(days=30)
    
    for mem in all_memories:
        system = mem.get("system", "unknown")
        by_system[system] = by_system.get(system, 0) + 1
        
        try:
            created = datetime.fromisoformat(mem["created_at"].replace('Z', '+00:00'))
            if created.replace(tzinfo=None) >= cutoff:
                recent_count += 1
            else:
                old_count += 1
        except Exception:
            old_count += 1
    
    return {
        "total": total,
        "recent_30_days": recent_count,
        "older_than_30_days": old_count,
        "by_system": by_system,
        "health": "good" if recent_count > 0 else "stale"
    }


@tool
def maintain_memories(task: str = "all", days_old: int = 30) -> str:
    """
    执行记忆维护任务
    
    Args:
        task: 维护任务类型 (compress/merge/cleanup/review/all)
        days_old: 多少天前的记忆需要处理
    
    Returns:
        维护结果报告
    """
    results = []
    
    if task in ["compress", "all"]:
        results.append(compress_old_memories(days_old))
    
    if task in ["merge", "all"]:
        results.append(merge_similar_memories(0.85))
    
    if task in ["cleanup", "all"]:
        results.append(cleanup_short_term_markdown(7))
    
    if task in ["review", "all"]:
        quality = review_memory_quality()
        results.append(f"记忆质量报告：总计{quality['total']}条，"
                      f"最近 30 天{quality['recent_30_days']}条，"
                      f"健康状态：{quality['health']}")
    
    return "\n".join(results)


@tool
def add_to_memory_md(content: str, section: str = None) -> str:
    """
    添加内容到 MEMORY.md（长期记忆 curated）
    
    Args:
        content: 要记录的内容
        section: 可选的章节标题
    
    Returns:
        操作结果
    """
    memory_path = _get_memory_md_path()
    memory_dir = _get_memory_dir()
    
    # 确保目录存在
    os.makedirs(memory_dir, exist_ok=True)
    
    timestamp = datetime.now().isoformat()
    
    # 构建内容
    if section:
        entry = f"\n\n## {timestamp} - {section}\n\n{content}\n"
    else:
        entry = f"\n\n## {timestamp}\n\n{content}\n"
    
    # 追加到文件
    try:
        with open(memory_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return f"[OK] 已添加到 MEMORY.md"
    except Exception as e:
        return f"[ERR] 添加失败：{e}"


@tool
def read_memory_md() -> str:
    """
    读取 MEMORY.md 内容
    
    Returns:
        MEMORY.md 的内容
    """
    memory_path = _get_memory_md_path()
    
    if not os.path.exists(memory_path):
        return "[INFO] MEMORY.md 不存在（还没有 curated 的长期记忆）"
    
    try:
        with open(memory_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"❌ 读取失败：{e}"
