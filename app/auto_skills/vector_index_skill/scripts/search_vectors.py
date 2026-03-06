"""
搜索向量工具
"""

from langchain_core.tools import tool
from typing import List, Dict, Optional
from .vector_index_manager import _get_manager, SearchResult

@tool
def search_vectors(index_name: str, query_vector: List[float], 
                   k: int = 10, filters: Optional[Dict] = None):
    """搜索向量
    
    Args:
        index_name: 索引名称
        query_vector: 查询向量，浮点数列表
        k: 返回结果数量，默认10
        filters: 过滤条件字典，例如 {"file_type": "py", "author": "system"}
    
    Returns:
        包含搜索结果和统计信息的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "索引名称必须是有效的字符串"
            }
        
        if not query_vector or not isinstance(query_vector, list):
            return {
                "success": False,
                "error": "query_vector必须是非空列表"
            }
        
        # 验证查询向量
        for i, value in enumerate(query_vector):
            if not isinstance(value, (int, float)):
                return {
                    "success": False,
                    "error": f"查询向量的第{i}个元素不是数字: {value}"
                }
        
        if not isinstance(k, int) or k <= 0:
            return {
                "success": False,
                "error": "k必须是正整数"
            }
        
        if filters is not None and not isinstance(filters, dict):
            return {
                "success": False,
                "error": "filters必须是字典"
            }
        
        # 执行搜索
        start_time = time.time()
        results = manager.search(index_name, query_vector, k, filters)
        search_time = time.time() - start_time
        
        # 格式化结果
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "distance": result.distance,
                "metadata": result.metadata
            })
        
        return {
            "success": True,
            "message": f"搜索完成，找到 {len(results)} 个结果",
            "index_name": index_name,
            "query_dimension": len(query_vector),
            "results_count": len(results),
            "search_time_ms": round(search_time * 1000, 2),
            "results": formatted_results
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"搜索向量时发生错误: {str(e)}"
        }

# 导入time模块
import time