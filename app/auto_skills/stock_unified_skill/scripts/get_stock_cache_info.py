from langchain_core.tools import tool
import os
import json
import glob
from datetime import datetime
from typing import Dict, Any, List

@tool
def get_stock_cache_info(cache_dir: str = "app/data/stock_cache") -> Dict[str, Any]:
    """
    获取股票缓存信息
    
    Args:
        cache_dir: 缓存目录路径
    
    Returns:
        包含缓存信息的字典
    """
    try:
        print(f"获取股票缓存信息: {cache_dir}")
        
        # 检查缓存目录是否存在
        if not os.path.exists(cache_dir):
            return {
                'success': True,
                'message': f"缓存目录不存在: {cache_dir}",
                'cache_files': [],
                'statistics': {
                    'total_files': 0,
                    'total_size_bytes': 0,
                    'cache_dir': cache_dir,
                    'directory_exists': False
                }
            }
        
        # 获取所有缓存文件
        cache_files = glob.glob(os.path.join(cache_dir, "*.json"))
        print(f"找到 {len(cache_files)} 个缓存文件")
        
        cache_info_list = []
        total_size = 0
        
        for cache_file in cache_files:
            try:
                file_size = os.path.getsize(cache_file)
                total_size += file_size
                
                file_mtime = datetime.fromtimestamp(os.path.getmtime(cache_file))
                file_age_days = (datetime.now() - file_mtime).days
                
                # 读取缓存元数据
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                
                metadata = cache_data.get('metadata', {})
                data_info = cache_data.get('data', {})
                
                # 提取股票信息
                symbol = metadata.get('symbol', '未知')
                period = metadata.get('period', 'day')
                data_count = metadata.get('data_count', 0)
                
                # 检查缓存是否过期
                is_expired = False
                expiry_time_str = metadata.get('expiry_time', '')
                if expiry_time_str:
                    expiry_time = datetime.fromisoformat(expiry_time_str)
                    is_expired = datetime.now() > expiry_time
                
                cache_info_list.append({
                    'file_name': os.path.basename(cache_file),
                    'symbol': symbol,
                    'period': period,
                    'file_size_bytes': file_size,
                    'file_size_human': f"{file_size / 1024:.1f} KB",
                    'modified_time': file_mtime.isoformat(),
                    'age_days': file_age_days,
                    'data_count': data_count,
                    'expiry_time': expiry_time_str,
                    'is_expired': is_expired,
                    'cache_time': metadata.get('cache_time', ''),
                    'start_date': data_info.get('start_date', ''),
                    'end_date': data_info.get('end_date', '')
                })
                
            except Exception as e:
                print(f"读取缓存文件 {cache_file} 信息失败: {e}")
                # 添加损坏文件信息
                cache_info_list.append({
                    'file_name': os.path.basename(cache_file),
                    'symbol': '损坏文件',
                    'period': '未知',
                    'file_size_bytes': os.path.getsize(cache_file),
                    'file_size_human': f"{os.path.getsize(cache_file) / 1024:.1f} KB",
                    'modified_time': datetime.fromtimestamp(os.path.getmtime(cache_file)).isoformat(),
                    'age_days': (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_file))).days,
                    'data_count': 0,
                    'expiry_time': '',
                    'is_expired': True,
                    'cache_time': '',
                    'start_date': '',
                    'end_date': ''
                })
        
        # 按股票代码分组统计
        symbol_stats = {}
        for info in cache_info_list:
            symbol = info['symbol']
            if symbol not in symbol_stats:
                symbol_stats[symbol] = {
                    'count': 0,
                    'total_size': 0,
                    'periods': set(),
                    'expired_count': 0
                }
            
            symbol_stats[symbol]['count'] += 1
            symbol_stats[symbol]['total_size'] += info['file_size_bytes']
            symbol_stats[symbol]['periods'].add(info['period'])
            if info['is_expired']:
                symbol_stats[symbol]['expired_count'] += 1
        
        # 转换set为list
        for symbol in symbol_stats:
            symbol_stats[symbol]['periods'] = list(symbol_stats[symbol]['periods'])
        
        # 统计过期文件
        expired_files = [info for info in cache_info_list if info['is_expired']]
        
        return {
            'success': True,
            'cache_files': cache_info_list,
            'statistics': {
                'total_files': len(cache_files),
                'total_size_bytes': total_size,
                'total_size_human': f"{total_size / 1024 / 1024:.2f} MB",
                'expired_files': len(expired_files),
                'valid_files': len(cache_files) - len(expired_files),
                'unique_symbols': len(symbol_stats),
                'symbol_statistics': symbol_stats,
                'cache_dir': cache_dir,
                'directory_exists': True,
                'timestamp': datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        error_msg = f"获取缓存信息时发生错误: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'cache_files': [],
            'statistics': {
                'total_files': 0,
                'total_size_bytes': 0,
                'cache_dir': cache_dir,
                'directory_exists': os.path.exists(cache_dir)
            }
        }