"""
优化索引工具
"""

from langchain_core.tools import tool
from .vector_index_manager import _get_manager

@tool
def optimize_index(index_name: str):
    """优化索引
    
    Args:
        index_name: 索引名称
    
    Returns:
        包含优化结果的字典
    """
    try:
        manager = _get_manager()
        
        # 验证参数
        if not index_name or not isinstance(index_name, str):
            return {
                "success": False,
                "error": "索引名称必须是有效的字符串"
            }
        
        # 获取优化前的统计信息
        before_stats = manager.get_stats(index_name)
        if before_stats is None:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 不存在"
            }
        
        # 执行优化
        start_time = time.time()
        success = manager.optimize(index_name)
        optimize_time = time.time() - start_time
        
        if success:
            # 获取优化后的统计信息
            after_stats = manager.get_stats(index_name)
            
            # 计算优化效果
            optimization_info = {
                "optimization_time_ms": round(optimize_time * 1000, 2),
                "before_vector_count": before_stats.get('total_vectors', 0),
                "after_vector_count": after_stats.get('total_vectors', 0) if after_stats else 0,
                "index_type": before_stats.get('index_type', 'unknown'),
                "optimization_applied": True
            }
            
            # 检查是否需要重新训练
            if before_stats.get('index_type') in ['IVF_FLAT', 'IVF_PQ']:
                optimization_info['retraining_required'] = True
                optimization_info['retraining_applied'] = True
            else:
                optimization_info['retraining_required'] = False
                optimization_info['retraining_applied'] = False
            
            return {
                "success": True,
                "message": f"索引 '{index_name}' 优化完成",
                "optimization_info": optimization_info
            }
        else:
            return {
                "success": False,
                "error": f"索引 '{index_name}' 优化失败"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": f"优化索引时发生错误: {str(e)}"
        }

# 导入time模块
import time