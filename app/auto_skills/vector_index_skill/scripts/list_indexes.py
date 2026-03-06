"""
列出所有索引工具
"""

from langchain_core.tools import tool
from .vector_index_manager import _get_manager

@tool
def list_indexes():
    """列出所有索引
    
    Returns:
        包含所有索引信息的字典
    """
    try:
        manager = _get_manager()
        
        # 获取所有索引
        indexes = manager.list_indexes()
        
        # 计算总体统计
        total_indexes = len(indexes)
        total_vectors = sum(index.get('vector_count', 0) for index in indexes)
        
        # 按索引类型统计
        index_type_stats = {}
        for index in indexes:
            index_type = index.get('index_type', 'unknown')
            if index_type not in index_type_stats:
                index_type_stats[index_type] = {
                    'count': 0,
                    'total_vectors': 0
                }
            index_type_stats[index_type]['count'] += 1
            index_type_stats[index_type]['total_vectors'] += index.get('vector_count', 0)
        
        # 格式化索引信息
        formatted_indexes = []
        for index in indexes:
            # 计算索引年龄（天）
            created_at = index.get('created_at', '')
            if created_at:
                try:
                    from datetime import datetime
                    created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    now = datetime.now()
                    age_days = (now - created_date).days
                except Exception:
                    age_days = 0
            else:
                age_days = 0
            
            formatted_index = {
                'index_name': index.get('index_name', 'unknown'),
                'dimension': index.get('dimension', 0),
                'index_type': index.get('index_type', 'unknown'),
                'vector_count': index.get('vector_count', 0),
                'created_at': created_at,
                'age_days': age_days,
                'status': 'active'
            }
            
            # 根据向量数量评估索引状态
            vector_count = index.get('vector_count', 0)
            if vector_count == 0:
                formatted_index['status'] = 'empty'
            elif vector_count < 100:
                formatted_index['status'] = 'small'
            elif vector_count > 1000000:
                formatted_index['status'] = 'large'
            
            formatted_indexes.append(formatted_index)
        
        # 按向量数量排序
        formatted_indexes.sort(key=lambda x: x['vector_count'], reverse=True)
        
        return {
            "success": True,
            "message": f"找到 {total_indexes} 个索引，共 {total_vectors} 个向量",
            "total_indexes": total_indexes,
            "total_vectors": total_vectors,
            "index_type_stats": index_type_stats,
            "indexes": formatted_indexes,
            "summary": {
                "empty_indexes": sum(1 for idx in formatted_indexes if idx['status'] == 'empty'),
                "small_indexes": sum(1 for idx in formatted_indexes if idx['status'] == 'small'),
                "active_indexes": sum(1 for idx in formatted_indexes if idx['status'] == 'active'),
                "large_indexes": sum(1 for idx in formatted_indexes if idx['status'] == 'large')
            }
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"列出索引时发生错误: {str(e)}"
        }