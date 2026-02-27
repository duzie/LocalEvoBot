from langchain_core.tools import tool
import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional
import warnings
warnings.filterwarnings('ignore')

# 实时数据缓存（5秒有效期）
_realtime_cache = {}
_cache_timestamps = {}

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

def _parse_gtimg_data(data_str: str, symbol: str) -> Dict[str, Any]:
    """解析腾讯财经API返回的数据"""
    try:
        # 腾讯财经API返回格式：v_sh600519="51~贵州茅台~600519~1700.00~..."
        if '=' not in data_str:
            return None
            
        parts = data_str.split('=')
        if len(parts) < 2:
            return None
            
        data_part = parts[1].strip('"')
        fields = data_part.split('~')
        
        if len(fields) < 40:
            return None
            
        # 解析字段
        name = fields[1] if len(fields) > 1 else ''
        current_price = float(fields[3]) if len(fields) > 3 and fields[3] else 0.0
        yesterday_close = float(fields[4]) if len(fields) > 4 and fields[4] else 0.0
        today_open = float(fields[5]) if len(fields) > 5 and fields[5] else 0.0
        high = float(fields[33]) if len(fields) > 33 and fields[33] else 0.0
        low = float(fields[34]) if len(fields) > 34 and fields[34] else 0.0
        volume = int(fields[36]) if len(fields) > 36 and fields[36] else 0
        amount = float(fields[37]) if len(fields) > 37 and fields[37] else 0.0
        
        # 计算涨跌
        change = current_price - yesterday_close if yesterday_close > 0 else 0.0
        change_percent = (change / yesterday_close * 100) if yesterday_close > 0 else 0.0
        
        return {
            'symbol': symbol,
            'name': name,
            'current': round(current_price, 2),
            'yesterday_close': round(yesterday_close, 2),
            'today_open': round(today_open, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'volume': volume,  # 成交量（手）
            'amount': round(amount / 10000, 2),  # 成交额（万元）
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': '腾讯财经',
            'timestamp': int(time.time())
        }
    except Exception as e:
        print(f"解析腾讯财经数据失败: {e}")
        return None

def _parse_sina_data(data_str: str, symbol: str) -> Dict[str, Any]:
    """解析新浪财经API返回的数据"""
    try:
        # 新浪财经API返回格式：var hq_str_sh600519="贵州茅台,1700.00,..."
        if '=' not in data_str:
            return None
            
        parts = data_str.split('=')
        if len(parts) < 2:
            return None
            
        data_part = parts[1].strip('"')
        fields = data_part.split(',')
        
        if len(fields) < 30:
            return None
            
        name = fields[0] if fields[0] else ''
        current_price = float(fields[3]) if len(fields) > 3 and fields[3] else 0.0
        yesterday_close = float(fields[2]) if len(fields) > 2 and fields[2] else 0.0
        today_open = float(fields[1]) if len(fields) > 1 and fields[1] else 0.0
        high = float(fields[4]) if len(fields) > 4 and fields[4] else 0.0
        low = float(fields[5]) if len(fields) > 5 and fields[5] else 0.0
        volume = int(fields[8]) if len(fields) > 8 and fields[8] else 0
        amount = float(fields[9]) if len(fields) > 9 and fields[9] else 0.0
        
        # 计算涨跌
        change = current_price - yesterday_close if yesterday_close > 0 else 0.0
        change_percent = (change / yesterday_close * 100) if yesterday_close > 0 else 0.0
        
        return {
            'symbol': symbol,
            'name': name,
            'current': round(current_price, 2),
            'yesterday_close': round(yesterday_close, 2),
            'today_open': round(today_open, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'volume': volume,  # 成交量（手）
            'amount': round(amount / 10000, 2),  # 成交额（万元）
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source': '新浪财经',
            'timestamp': int(time.time())
        }
    except Exception as e:
        print(f"解析新浪财经数据失败: {e}")
        return None

@tool
def get_stock_realtime(symbol: str, use_cache: bool = True, fallback_source: str = "sina") -> Dict[str, Any]:
    """
    获取股票实时行情数据（腾讯财经API）
    
    Args:
        symbol: 股票代码，如000001、600519等
        use_cache: 是否使用缓存（5秒内有效）
        fallback_source: 备用数据源：sina、eastmoney
    
    Returns:
        包含实时行情数据的字典，包含以下字段：
        - symbol: 股票代码
        - name: 股票名称
        - current: 当前价格
        - yesterday_close: 昨日收盘价
        - today_open: 今日开盘价
        - high: 最高价
        - low: 最低价
        - volume: 成交量（手）
        - amount: 成交额（万元）
        - change: 涨跌额
        - change_percent: 涨跌幅（%）
        - time: 更新时间
        - source: 数据源
        - timestamp: 时间戳
    """
    try:
        print(f"获取股票实时数据: {symbol}, 使用缓存: {use_cache}, 备用数据源: {fallback_source}")
        
        # 检查缓存
        cache_key = f"realtime_{symbol}"
        current_time = time.time()
        
        if use_cache and cache_key in _realtime_cache:
            cache_data, cache_time = _realtime_cache[cache_key], _cache_timestamps[cache_key]
            if current_time - cache_time < 5:  # 5秒缓存有效期
                print(f"使用缓存数据 (缓存时间: {current_time - cache_time:.1f}秒前)")
                return cache_data
        
        # 获取市场前缀
        prefix = _get_market_prefix(symbol)
        
        # 尝试腾讯财经API（主数据源）
        try:
            url = f"https://qt.gtimg.cn/q={prefix}{symbol}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.encoding = 'gbk'  # 腾讯财经使用GBK编码
            
            if response.status_code == 200 and response.text:
                data = _parse_gtimg_data(response.text, symbol)
                if data:
                    # 更新缓存
                    _realtime_cache[cache_key] = data
                    _cache_timestamps[cache_key] = current_time
                    
                    print(f"成功获取实时数据 (来源: {data['source']})")
                    return data
        except Exception as e:
            print(f"腾讯财经API请求失败: {e}")
        
        # 尝试备用数据源
        if fallback_source == "sina":
            try:
                url = f"https://hq.sinajs.cn/list={prefix}{symbol}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Referer': 'https://finance.sina.com.cn'
                }
                
                response = requests.get(url, headers=headers, timeout=10)
                response.encoding = 'gbk'  # 新浪财经使用GBK编码
                
                if response.status_code == 200 and response.text:
                    data = _parse_sina_data(response.text, symbol)
                    if data:
                        # 更新缓存
                        _realtime_cache[cache_key] = data
                        _cache_timestamps[cache_key] = current_time
                        
                        print(f"成功获取实时数据 (来源: {data['source']})")
                        return data
            except Exception as e:
                print(f"新浪财经API请求失败: {e}")
        
        # 所有数据源都失败
        error_msg = f"无法获取股票 {symbol} 的实时数据"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'symbol': symbol,
            'timestamp': int(current_time)
        }
        
    except Exception as e:
        error_msg = f"获取实时数据时发生错误: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'symbol': symbol,
            'timestamp': int(time.time())
        }