"""
创建向量索引工具
"""

from langchain_core.tools import tool
from .vector_index_manager import _get_manager

@tool
def create_vector_index(index_name: str, dimension: int, index_type: str = "HNSW"):
    """创建向量索引
    
    Args:
        index_name: 索引名称
        dimension: 向量维度
        index_type: 索引类型，可选 HNSW/IVF_FLAT/IVF_PQ，默认 HNSW
    
    Returns:
        包含操作结果的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "索引名称必须是有效的字符串"
            }
        
        if not isinstance(dimension, int) or dimension <= 0:
            return {
                "success": False,
                "error": "向量维度必须是正整数"
            }
        
        valid_index_types = ["HNSW", "IVF_FLAT", "IVF_PQ", "FLAT"]
        if index_type not in valid_index_types:
            return {
                "success": False,
                "error": f"索引类型必须是以下之一: {', '.join(valid_index_types)}"
            }
        
        # 创建索引
        success = manager.create_index(index_name, dimension, index_type)
        
        if success:
            return {
                "success": True,
                "message": f"向量索引 '{index_name}' 创建成功",
                "index_name": index_name,
                "dimension": dimension,
                "index_type": index_type
            }
        else:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 已存在或创建失败"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"创建向量索引时发生错误: {str(e)}"
        }