"""
获取索引统计信息工具
"""

from langchain_core.tools import tool
from .vector_index_manager import _get_manager

@tool
def get_index_stats(index_name: str):
    """获取索引统计信息
    
    Args:
        index_name: 索引名称
    
    Returns:
        包含索引统计信息的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "索引名称必须是有效的字符串"
            }
        
        # 获取统计信息
        stats = manager.get_stats(index_name)
        
        if stats is None:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 不存在"
            }
        
        # 格式化文件大小
        index_size = stats.get('index_size', 0)
        if index_size >= 1024 * 1024 * 1024:  # GB
            size_str = f"{index_size / (1024 * 1024 * 1024):.2f} GB"
        elif index_size >= 1024 * 1024:  # MB
            size_str = f"{index_size / (1024 * 1024):.2f} MB"
        elif index_size >= 1024:  # KB
            size_str = f"{index_size / 1024:.2f} KB"
        else:
            size_str = f"{index_size} bytes"
        
        # 计算索引密度（向量数/索引大小MB）
        if index_size > 0:
            density = stats['total_vectors'] / (index_size / (1024 * 1024))
        else:
            density = 0
        
        # 添加额外信息
        stats['index_size_human'] = size_str
        stats['vector_density_per_mb'] = round(density, 2)
        
        # 计算索引效率评分（0-100）
        efficiency_score = 0
        if stats['total_vectors'] > 0:
            # 基于向量密度和索引类型评分
            base_score = min(100, stats['total_vectors'] / 1000)  # 每1000个向量得1分，最多100分
            if stats['index_type'] == 'HNSW':
                efficiency_score = min(100, base_score * 1.2)  # HNSW效率较高
            elif stats['index_type'] == 'IVF_PQ':
                efficiency_score = min(100, base_score * 1.1)  # IVF_PQ压缩效率高
            else:
                efficiency_score = base_score
        
        stats['efficiency_score'] = round(efficiency_score)
        
        return {
            "success": True,
            "message": f"索引 '{index_name}' 统计信息",
            "stats": stats
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"获取索引统计信息时发生错误: {str(e)}"
        }