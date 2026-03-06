"""
删除索引工具
"""

from langchain_core.tools import tool
from .vector_index_manager import _get_manager

@tool
def delete_index(index_name: str):
    """删除索引
    
    Args:
        index_name: 索引名称
    
    Returns:
        包含删除结果的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "索引名称必须是有效的字符串"
            }
        
        # 获取删除前的统计信息
        before_stats = manager.get_stats(index_name)
        if before_stats is None:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 不存在"
            }
        
        # 执行删除
        success = manager.delete_index(index_name)
        
        if success:
            return {
                "success": True,
                "message": f"索引 '{index_name}' 删除成功",
                "deleted_index_info": {
                    "index_name": index_name,
                    "dimension": before_stats.get('dimension', 0),
                    "index_type": before_stats.get('index_type', 'unknown'),
                    "vector_count": before_stats.get('total_vectors', 0),
                    "index_size": before_stats.get('index_size', 0),
                    "created_at": before_stats.get('created_at', 'unknown')
                }
            }
        else:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 删除失败"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"删除索引时发生错误: {str(e)}"
        }