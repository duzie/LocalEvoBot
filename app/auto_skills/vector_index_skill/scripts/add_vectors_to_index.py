"""
向索引添加向量工具
"""

from langchain_core.tools import tool
from typing import List, Dict, Optional
from .vector_index_manager import _get_manager

@tool
def add_vectors_to_index(index_name: str, vectors: List[List[float]], 
                         ids: Optional[List[str]] = None, 
                         metadata: Optional[List[Dict]] = None):
    """向索引添加向量
    
    Args:
        index_name: 索引名称
        vectors: 向量列表，每个向量是一个浮点数列表
        ids: 向量ID列表，如未提供则自动生成
        metadata: 元数据列表，每个元素是一个字典
    
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
        
        if not vectors or not isinstance(vectors, list):
            return {
                "success": False,
                "error": "vectors必须是非空列表"
            }
        
        # 验证向量维度一致性
        dimension = None
        for i, vector in enumerate(vectors):
            if not isinstance(vector, list):
                return {
                    "success": False,
                    "error": f"第{i}个向量不是列表"
                }
            
            # 检查向量元素是否为数字
            for j, value in enumerate(vector):
                if not isinstance(value, (int, float)):
                    return {
                        "success": False,
                        "error": f"第{i}个向量的第{j}个元素不是数字: {value}"
                    }
            
            # 检查维度一致性
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                return {
                    "success": False,
                    "error": f"向量维度不一致: 第0个向量维度为{dimension}, 第{i}个向量维度为{len(vector)}"
                }
        
        # 验证ids
        if ids is not None:
            if not isinstance(ids, list):
                return {
                    "success": False,
                    "error": "ids必须是列表"
                }
            if len(ids) != len(vectors):
                return {
                    "success": False,
                    "error": f"ids数量({len(ids)})与向量数量({len(vectors)})不匹配"
                }
        
        # 验证metadata
        if metadata is not None:
            if not isinstance(metadata, list):
                return {
                    "success": False,
                    "error": "metadata必须是列表"
                }
            if len(metadata) != len(vectors):
                return {
                    "success": False,
                    "error": f"metadata数量({len(metadata)})与向量数量({len(vectors)})不匹配"
                }
            for i, meta in enumerate(metadata):
                if not isinstance(meta, dict):
                    return {
                        "success": False,
                        "error": f"第{i}个metadata不是字典"
                    }
        
        # 添加向量
        success = manager.add_vectors(index_name, vectors, ids, metadata)
        
        if success:
            return {
                "success": True,
                "message": f"成功向索引 '{index_name}' 添加 {len(vectors)} 个向量",
                "index_name": index_name,
                "vectors_added": len(vectors),
                "dimension": dimension
            }
        else:
            return {
                "success": False,
                "error": f"向索引 '{index_name}' 添加向量失败，请检查索引是否存在或向量维度是否正确"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"添加向量时发生错误: {str(e)}"
        }