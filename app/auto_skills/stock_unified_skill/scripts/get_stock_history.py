from langchain_core.tools import tool
from datetime import datetime, timedelta
import json
import os
import requests
import time
from typing import Dict, Any, Optional, List

def _get_market_prefix(symbol: str) -> str:
    """获取股票市场前缀"""
    if symbol.startswith('6'):
        return 'sh'  # 上海
    elif symbol.startswith('0') or symbol.startswith('3'):
        return 'sz'  # 深圳
    elif symbol.startswith('4') or symbol.startswith('8'):
        return 'bj'  # 北京
    else:
        return 'sh'  # 默认上海

def _get_kline_block(root: Dict[str, Any], prefix: str, symbol: str, period: str) -> Optional[List[Any]]:
    qfq_property = f"qfq{period}"
    period_property = f"{period}qfq"
    if isinstance(root, dict) and qfq_property in root:
        return root.get(qfq_property)
    data = root.get("data") if isinstance(root, dict) else None
    if isinstance(data, dict):
        if qfq_property in data:
            return data.get(qfq_property)
        stock_key = f"{prefix}{symbol}"
        stock = data.get(stock_key)
        if isinstance(stock, dict):
            if qfq_property in stock:
                return stock.get(qfq_property)
            if period_property in stock:
                return stock.get(period_property)
            if period in stock:
                return stock.get(period)
    return None

def _parse_kline_block(klines: List[Any], symbol: str, period: str) -> List[Dict[str, Any]]:
    data_list = []
    for item in klines or []:
        if not isinstance(item, (list, tuple)) or len(item) < 6:
            continue
        date_str = str(item[0])
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            continue
        try:
            open_price = float(item[1]) if item[1] else 0.0
            close_price = float(item[2]) if item[2] else 0.0
            high = float(item[3]) if item[3] else 0.0
            low = float(item[4]) if item[4] else 0.0
            volume = int(float(item[5])) if item[5] else 0
        except Exception:
            continue
        data_list.append({
            'date': date_obj.strftime("%Y-%m-%d"),
            'open': round(open_price, 2),
            'close': round(close_price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'volume': volume,
            'symbol': symbol,
            'period': period
        })
    return data_list

def _get_gtimg_history(symbol: str, period: str) -> List[Dict[str, Any]]:
    """从腾讯财经获取历史K线数据"""
    try:
        prefix = _get_market_prefix(symbol)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{symbol},{period},,,320,qfq"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            print(f"腾讯财经历史数据API请求失败: {response.status_code}")
            return []
        data = response.json()
        if isinstance(data, dict) and data.get("code") not in (0, None):
            print(f"腾讯财经历史数据返回错误码: {data.get('code')}")
            return []
        klines = _get_kline_block(data, prefix, symbol, period)
        if not klines:
            return []
        return _parse_kline_block(klines, symbol, period)
    except Exception as e:
        print(f"获取腾讯财经历史数据失败: {e}")
        return []

def _load_cache(cache_file: str) -> Dict[str, Any]:
    """加载缓存数据"""
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"加载缓存失败: {e}")
    return None

def _save_cache(cache_file: str, data: Dict[str, Any], cache_days: int = 7):
    """保存缓存数据"""
    try:
        # 添加元数据
        cache_data = {
            'metadata': {
                'symbol': data.get('symbol', ''),
                'period': data.get('period', 'day'),
                'start_date': data.get('start_date', ''),
                'end_date': data.get('end_date', ''),
                'cache_time': datetime.now().isoformat(),
                'expiry_time': (datetime.now() + timedelta(days=cache_days)).isoformat(),
                'data_count': len(data.get('data', []))
            },
            'data': data
        }
        
        # 确保目录存在
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
        print(f"缓存已保存: {cache_file}")
        return True
    except Exception as e:
        print(f"保存缓存失败: {e}")
        return False

@tool
def get_stock_history(symbol: str, period: str = "day", start_date: str = "2023-01-01",
                     end_date: str = None, cache_dir: str = "app/data/stock_cache",
                     cache_days: int = 7, force_refresh: bool = False) -> Dict[str, Any]:
    """
    获取股票历史数据（腾讯财经API），支持缓存
    
    Args:
        symbol: 股票代码，如000001、600519等
        period: 数据周期：day（日线）、week（周线）、month（月线）
        start_date: 开始日期，格式YYYY-MM-DD
        end_date: 结束日期，格式YYYY-MM-DD，默认今天
        cache_dir: 缓存目录路径
        cache_days: 缓存有效期（天）
        force_refresh: 是否强制刷新缓存
    
    Returns:
        包含股票历史数据的字典
    """
    try:
        # 获取当前时间
        current_time = datetime.now()
        if end_date is None:
            end_date = current_time.strftime("%Y-%m-%d")
        
        print(f"获取股票历史数据: {symbol}, 周期: {period}, 时间范围: {start_date} 到 {end_date}")
        print(f"缓存目录: {cache_dir}, 缓存有效期: {cache_days}天, 强制刷新: {force_refresh}")
        
        # 确保缓存目录存在
        os.makedirs(cache_dir, exist_ok=True)
        
        # 构建缓存文件名
        cache_file = os.path.join(cache_dir, f"{symbol}_{period}.json")
        
        # 检查是否需要使用缓存
        use_cache = False
        cache_data = None
        cache_metadata = None
        
        if not force_refresh and os.path.exists(cache_file):
            try:
                cache_content = _load_cache(cache_file)
                
                # 检查缓存元数据
                if cache_content and 'metadata' in cache_content:
                    cache_metadata = cache_content['metadata']
                    cache_expiry = datetime.fromisoformat(cache_metadata.get('expiry_time', '2000-01-01'))
                    
                    # 检查缓存是否过期
                    if current_time < cache_expiry:
                        cache_data = cache_content.get('data', {})
                        
                        # 检查缓存数据的时间范围是否满足需求
                        cache_start = cache_data.get('start_date', '')
                        cache_end = cache_data.get('end_date', '')
                        
                        # 如果缓存数据的时间范围包含请求的时间范围，则使用缓存
                        if cache_start <= start_date and cache_end >= end_date:
                            use_cache = True
                            print(f"使用缓存数据 (有效期至: {cache_expiry})")
                        else:
                            print(f"缓存数据时间范围不足: {cache_start}~{cache_end}, 需要: {start_date}~{end_date}")
                    else:
                        print(f"缓存已过期: {cache_expiry}")
                else:
                    print("缓存元数据缺失")
                    
            except Exception as e:
                print(f"读取缓存失败: {e}")
        
        result_data = None
        
        if use_cache and cache_data:
            # 使用缓存数据
            result_data = cache_data
            result_data['from_cache'] = True
            result_data['cache_info'] = {
                'cache_file': cache_file,
                'cache_hit': True,
                'cache_updated': False,
                'cache_expiry': cache_metadata.get('expiry_time', ''),
                'original_cache_size': cache_metadata.get('data_count', 0)
            }
        else:
            print(f"从API获取数据: {symbol}")
            history_data = _get_gtimg_history(symbol, period)
            if not history_data:
                if cache_data:
                    print("API获取失败，使用过期缓存数据")
                    result_data = cache_data
                    result_data['from_cache'] = True
                    result_data['cache_info'] = {
                        'cache_file': cache_file,
                        'cache_hit': True,
                        'cache_updated': False,
                        'cache_expiry': '已过期',
                        'original_cache_size': len(cache_data.get('data', []))
                    }
                else:
                    return {
                        'success': False,
                        'error': f"无法获取股票 {symbol} 的历史数据",
                        'symbol': symbol,
                        'period': period,
                        'start_date': start_date,
                        'end_date': end_date,
                        'timestamp': int(time.time())
                    }
            else:
                merged = history_data
                if cache_data and isinstance(cache_data.get('data'), list):
                    by_date = {item.get("date"): item for item in cache_data.get('data', []) if item.get("date")}
                    for item in history_data:
                        if item.get("date"):
                            by_date[item.get("date")] = item
                    merged = list(by_date.values())
                try:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    filtered = [
                        item for item in merged
                        if start_dt <= datetime.strptime(item.get("date", "1900-01-01"), "%Y-%m-%d") <= end_dt
                    ]
                except Exception:
                    filtered = merged
                result_data = {
                    'success': True,
                    'symbol': symbol,
                    'period': period,
                    'start_date': start_date,
                    'end_date': end_date,
                    'data': filtered,
                    'data_count': len(filtered),
                    'from_cache': False,
                    'timestamp': int(time.time())
                }
                if _save_cache(cache_file, result_data, cache_days):
                    result_data['cache_info'] = {
                        'cache_file': cache_file,
                        'cache_hit': False,
                        'cache_updated': True,
                        'cache_expiry': (datetime.now() + timedelta(days=cache_days)).isoformat(),
                        'original_cache_size': len(filtered)
                    }
        
        return result_data
        
    except Exception as e:
        error_msg = f"获取历史数据时发生错误: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'symbol': symbol,
            'period': period,
            'start_date': start_date,
            'end_date': end_date,
            'timestamp': int(time.time())
        }
