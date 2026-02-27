from langchain_core.tools import tool
import os
import json
import glob
from datetime import datetime, timedelta
from typing import Dict, Any, List

@tool
def clear_stock_cache(symbol: str = None, cache_dir: str = "app/data/stock_cache", 
                     max_age_days: int = 30) -> Dict[str, Any]:
    """
    清理股票缓存文件
    
    Args:
        symbol: 股票代码，为空则清理所有缓存
        cache_dir: 缓存目录路径
        max_age_days: 最大缓存天数，超过此天数的缓存将被清理
    
    Returns:
        包含清理结果的字典
    """
    try:
        print(f"清理股票缓存: symbol={symbol}, cache_dir={cache_dir}, max_age_days={max_age_days}")
        
        # 检查缓存目录是否存在
        if not os.path.exists(cache_dir):
            return {
                'success': True,
                'message': f"缓存目录不存在: {cache_dir}",
                'cleaned_files': [],
                'total_files': 0
            }
        
        # 确定要清理的文件模式
        if symbol:
            file_pattern = os.path.join(cache_dir, f"{symbol}_*.json")
            cache_files = glob.glob(file_pattern)
        else:
            file_pattern = os.path.join(cache_dir, "*.json")
            cache_files = glob.glob(file_pattern)
        
        print(f"找到 {len(cache_files)} 个缓存文件")
        
        cleaned_files = []
        kept_files = []
        current_time = datetime.now()
        
        for cache_file in cache_files:
            try:
                # 检查文件修改时间
                file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                file_age = (current_time - file_mtime).days
                
                # 检查缓存过期时间（如果文件中有元数据）
                cache_expired = False
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    
                    if 'metadata' in cache_data and 'expiry_time' in cache_data['metadata']:
                        expiry_time = datetime.fromisoformat(cache_data['metadata']['expiry_time'])
                        if current_time > expiry_time:
                            cache_expired = True
                except:
                    pass  # 忽略JSON解析错误
                
                # 清理条件：文件超过最大天数 或 缓存已过期 或 JSON损坏
                if file_age > max_age_days or cache_expired:
                    os.remove(cache_file)
                    cleaned_files.append({
                        'file': os.path.basename(cache_file),
                        'reason': '过期' if cache_expired else f'超过{max_age_days}天',
                        'age_days': file_age
                    })
                    print(f"清理文件: {os.path.basename(cache_file)} (原因: {'过期' if cache_expired else f'超过{max_age_days}天'})")
                else:
                    kept_files.append({
                        'file': os.path.basename(cache_file),
                        'age_days': file_age,
                        'size_bytes': os.path.getsize(cache_file)
                    })
                    
            except Exception as e:
                print(f"处理文件 {cache_file} 时出错: {e}")
                # 如果文件损坏无法读取，也删除
                try:
                    os.remove(cache_file)
                    cleaned_files.append({
                        'file': os.path.basename(cache_file),
                        'reason': '损坏文件',
                        'age_days': -1
                    })
                except:
                    pass
        
        return {
            'success': True,
            'message': f"清理完成，清理了 {len(cleaned_files)} 个文件，保留了 {len(kept_files)} 个文件",
            'cleaned_files': cleaned_files,
            'kept_files': kept_files,
            'total_files': len(cache_files),
            'cache_dir': cache_dir,
            'max_age_days': max_age_days,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        error_msg = f"清理缓存时发生错误: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'cleaned_files': [],
            'kept_files': [],
            'total_files': 0,
            'timestamp': datetime.now().isoformat()
        }