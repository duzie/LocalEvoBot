from langchain_core.tools import tool
import pandas as pd
from datetime import datetime, timedelta
import json
from typing import Dict, Any, Optional
import yfinance as yf
import baostock as bs
import akshare as ak
import warnings
warnings.filterwarnings('ignore')

@tool
def collect_stock_data(symbol: str, name: str, start_date: str = "2023-01-01", 
                      end_date: str = "2024-12-31", data_source: str = "yfinance") -> Dict[str, Any]:
    """
    采集单只股票的历史数据
    
    Args:
        symbol: 股票代码，如000001、000002等
        name: 股票名称
        start_date: 开始日期，格式YYYY-MM-DD
        end_date: 结束日期，格式YYYY-MM-DD
        data_source: 数据源：akshare、yfinance、baostock
    
    Returns:
        包含股票数据的字典
    """
    try:
        print(f"开始采集股票数据: {symbol} ({name}), 数据源: {data_source}, 时间范围: {start_date} 到 {end_date}")
        
        stock_data = None
        source_used = data_source
        
        # 根据数据源选择不同的获取方式
        if data_source == "yfinance":
            # yfinance需要特定的股票代码格式
            # A股在yfinance中的格式：000001.SZ (平安银行), 600519.SS (贵州茅台)
            yf_symbol = symbol
            if symbol.startswith('6'):
                yf_symbol = f"{symbol}.SS"  # 上海证券交易所
            else:
                yf_symbol = f"{symbol}.SZ"  # 深圳证券交易所
            
            try:
                stock = yf.Ticker(yf_symbol)
                stock_data = stock.history(start=start_date, end=end_date)
                
                if stock_data.empty:
                    print(f"yfinance未找到数据，尝试其他数据源...")
                    source_used = "baostock"
                else:
                    print(f"yfinance成功获取 {len(stock_data)} 条数据")
                    
            except Exception as e:
                print(f"yfinance获取失败: {e}")
                source_used = "baostock"
        
        if data_source == "baostock" or (data_source == "yfinance" and (stock_data is None or stock_data.empty)):
            # 使用baostock获取数据
            try:
                # 登录baostock
                lg = bs.login()
                
                if lg.error_code != '0':
                    print(f"baostock登录失败: {lg.error_msg}")
                    source_used = "akshare"
                else:
                    # 设置股票代码格式
                    bs_symbol = symbol
                    if symbol.startswith('6'):
                        bs_symbol = f"sh.{symbol}"
                    else:
                        bs_symbol = f"sz.{symbol}"
                    
                    # 查询历史数据
                    rs = bs.query_history_k_data_plus(
                        bs_symbol,
                        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTTM,isST",
                        start_date=start_date,
                        end_date=end_date,
                        frequency="d",
                        adjustflag="3"  # 前复权
                    )
                    
                    if rs.error_code != '0':
                        print(f"baostock查询失败: {rs.error_msg}")
                        source_used = "akshare"
                    else:
                        data_list = []
                        while (rs.error_code == '0') & rs.next():
                            data_list.append(rs.get_row_data())
                        
                        if data_list:
                            stock_data = pd.DataFrame(data_list, columns=rs.fields)
                            print(f"baostock成功获取 {len(stock_data)} 条数据")
                        else:
                            print(f"baostock未找到数据")
                            source_used = "akshare"
                    
                    # 登出
                    bs.logout()
                    
            except Exception as e:
                print(f"baostock获取失败: {e}")
                source_used = "akshare"
        
        if data_source == "akshare" or source_used == "akshare":
            # 使用akshare获取数据
            try:
                # 处理股票代码格式
                ak_symbol = symbol
                if not symbol.startswith(('sh', 'sz', 'bj')):
                    if symbol.startswith('6'):
                        ak_symbol = f"sh{symbol}"
                    else:
                        ak_symbol = f"sz{symbol}"
                
                stock_data = ak.stock_zh_a_hist(
                    symbol=ak_symbol, 
                    period="daily", 
                    start_date=start_date, 
                    end_date=end_date, 
                    adjust="qfq"
                )
                
                if stock_data.empty:
                    print(f"akshare未找到数据")
                else:
                    print(f"akshare成功获取 {len(stock_data)} 条数据")
                    
            except Exception as e:
                print(f"akshare获取失败: {e}")
        
        # 检查是否获取到数据
        if stock_data is None or stock_data.empty:
            return {
                "success": False,
                "error": f"无法获取股票 {symbol} ({name}) 的数据，请检查股票代码和时间范围",
                "symbol": symbol,
                "name": name,
                "data_source": source_used
            }
        
        # 标准化数据格式
        if source_used == "yfinance":
            # yfinance数据格式处理
            stock_data = stock_data.reset_index()
            stock_data['Date'] = pd.to_datetime(stock_data['Date'])
            
            # 重命名列
            column_mapping = {
                'Date': 'date',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }
            stock_data = stock_data.rename(columns=column_mapping)
            
            # 只保留需要的列
            needed_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            stock_data = stock_data[[col for col in needed_columns if col in stock_data.columns]]
            
        elif source_used == "baostock":
            # baostock数据格式处理
            stock_data['date'] = pd.to_datetime(stock_data['date'])
            
            # 转换数据类型
            numeric_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_columns:
                if col in stock_data.columns:
                    stock_data[col] = pd.to_numeric(stock_data[col], errors='coerce')
            
            # 只保留需要的列
            needed_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
            stock_data = stock_data[[col for col in needed_columns if col in stock_data.columns]]
            
        elif source_used == "akshare":
            # akshare数据格式处理
            column_mapping = {
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume'
            }
            stock_data = stock_data.rename(columns={k: v for k, v in column_mapping.items() if k in stock_data.columns})
            
            if 'date' in stock_data.columns:
                stock_data['date'] = pd.to_datetime(stock_data['date'])
        
        # 添加股票代码和名称
        stock_data['symbol'] = symbol
        stock_data['name'] = name
        
        # 确保日期列是datetime类型并排序
        if 'date' in stock_data.columns:
            stock_data = stock_data.sort_values('date')
        
        # 计算统计信息
        stats = {
            "data_points": len(stock_data),
            "date_range": {
                "start": stock_data['date'].min().strftime("%Y-%m-%d") if 'date' in stock_data.columns else start_date,
                "end": stock_data['date'].max().strftime("%Y-%m-%d") if 'date' in stock_data.columns else end_date
            },
            "price_stats": {
                "open_avg": float(stock_data['open'].mean()) if 'open' in stock_data.columns else None,
                "close_avg": float(stock_data['close'].mean()) if 'close' in stock_data.columns else None,
                "high_max": float(stock_data['high'].max()) if 'high' in stock_data.columns else None,
                "low_min": float(stock_data['low'].min()) if 'low' in stock_data.columns else None
            },
            "volume_stats": {
                "avg_volume": float(stock_data['volume'].mean()) if 'volume' in stock_data.columns else None,
                "total_volume": float(stock_data['volume'].sum()) if 'volume' in stock_data.columns else None
            }
        }
        
        # 转换为字典格式
        data_dict = stock_data.to_dict(orient='records')
        
        return {
            "success": True,
            "symbol": symbol,
            "name": name,
            "data_source": source_used,
            "data": data_dict,
            "stats": stats,
            "columns": list(stock_data.columns),
            "dataframe_shape": stock_data.shape,
            "message": f"成功从 {source_used} 获取 {len(data_dict)} 条数据"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"采集股票数据失败: {str(e)}",
            "symbol": symbol,
            "name": name,
            "data_source": data_source
        }