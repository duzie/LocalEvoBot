from langchain_core.tools import tool
import requests
import time
import re
from typing import Dict, Any, List
import warnings
warnings.filterwarnings('ignore')

def _normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^0-9]", "", str(symbol or ""))

def _market_from_symbol(symbol: str) -> str:
    if symbol.startswith('6'):
        return 'sh'
    if symbol.startswith('0') or symbol.startswith('3'):
        return 'sz'
    if symbol.startswith('4') or symbol.startswith('8'):
        return 'bj'
    return 'sh'

def _parse_sina_suggestion(data_str: str) -> List[Dict[str, Any]]:
    """解析新浪财经股票建议数据"""
    try:
        if '=' not in data_str:
            return []
        parts = data_str.split('=', 1)
        if len(parts) < 2:
            return []
        data_part = parts[1].strip().strip(';').strip()
        match = re.search(r'suggestion\s*=\s*["\'](.*?)["\']', data_str)
        if match:
            suggestion_data = match.group(1)
            items = [item for item in suggestion_data.split(';') if item]
            results = []
            for item in items:
                fields = item.split(',')
                if len(fields) >= 6 and fields[4]:
                    name = fields[4]
                    raw_code = fields[2]
                    symbol = _normalize_symbol(raw_code)
                    if not symbol:
                        continue
                    pinyin = fields[5]
                    market = _market_from_symbol(symbol)
                    results.append({
                        'symbol': symbol,
                        'name': name,
                        'pinyin': pinyin,
                        'full_pinyin': pinyin,
                        'market': market,
                        'display': f"{name} ({symbol})"
                    })
            return results
        match = re.search(r'\[(.*?)\]', data_part)
        if not match:
            return []
        items_str = match.group(1)
        items = [item.strip('"') for item in items_str.split(',')]
        results = []
        for item in items:
            if not item:
                continue
            fields = item.split('|')
            if len(fields) >= 4:
                name = fields[0]
                symbol = _normalize_symbol(fields[1])
                if not symbol:
                    continue
                pinyin = fields[2]
                full_pinyin = fields[3]
                market = _market_from_symbol(symbol)
                results.append({
                    'symbol': symbol,
                    'name': name,
                    'pinyin': pinyin,
                    'full_pinyin': full_pinyin,
                    'market': market,
                    'display': f"{name} ({symbol})"
                })
        return results
    except Exception as e:
        print(f"解析股票建议数据失败: {e}")
        return []

@tool
def search_stock(name: str, max_results: int = 10) -> Dict[str, Any]:
    """
    搜索股票代码和名称（新浪财经API）
    
    Args:
        name: 股票名称或拼音缩写，如"平安银行"、"PAYH"、"pinganyinhang"
        max_results: 最大返回结果数
    
    Returns:
        包含搜索结果的字典，结构为：
        {
            "query": 搜索关键词,
            "count": 结果数量,
            "results": [
                {
                    "symbol": 股票代码,
                    "name": 股票名称,
                    "pinyin": 拼音缩写,
                    "full_pinyin": 完整拼音,
                    "market": 市场（sh/sz/bj）,
                    "display": 显示文本
                },
                ...
            ],
            "timestamp": 时间戳
        }
    """
    try:
        print(f"搜索股票: {name}, 最大结果数: {max_results}")
        
        # 新浪财经股票建议API
        url = f"https://suggest3.sinajs.cn/suggest/?name=suggestion&type=111&key={name}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200 and response.content:
            try:
                response_text = response.content.decode('gbk', errors='ignore')
            except Exception:
                response_text = response.text
            results = _parse_sina_suggestion(response_text)
            
            # 过滤和排序结果
            filtered_results = []
            for result in results:
                # 只保留A股股票（排除基金、债券等）
                symbol = result['symbol']
                if (symbol.startswith('0') or  # 深圳主板、中小板
                    symbol.startswith('3') or  # 创业板
                    symbol.startswith('6') or  # 上海主板
                    symbol.startswith('4') or  # 北京三板
                    symbol.startswith('8')):   # 北京精选层
                    filtered_results.append(result)
            
            # 限制结果数量
            filtered_results = filtered_results[:max_results]
            
            print(f"找到 {len(filtered_results)} 个股票结果")
            
            return {
                'success': True,
                'query': name,
                'count': len(filtered_results),
                'results': filtered_results,
                'timestamp': int(time.time())
            }
        else:
            error_msg = f"搜索API请求失败: {response.status_code}"
            print(error_msg)
            
            return {
                'success': False,
                'error': error_msg,
                'query': name,
                'count': 0,
                'results': [],
                'timestamp': int(time.time())
            }
            
    except Exception as e:
        error_msg = f"搜索股票时发生错误: {str(e)}"
        print(error_msg)
        
        return {
            'success': False,
            'error': error_msg,
            'query': name,
            'count': 0,
            'results': [],
            'timestamp': int(time.time())
        }
