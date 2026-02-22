from langchain_core.tools import tool
import pandas as pd
from datetime import datetime
import json
from typing import Dict, Any, List
import os
from .collect_stock_data import collect_stock_data

@tool
def collect_multiple_stocks(stock_list: List[Dict[str, str]], start_date: str = "2023-01-01",
                           end_date: str = "2024-12-31", output_path: str = "D:\\dfCode\\stock_data.csv") -> Dict[str, Any]:
    """
    批量采集多只股票的历史数据
    
    Args:
        stock_list: 股票列表，每个元素为字典，包含symbol和name字段
        start_date: 开始日期，格式YYYY-MM-DD
        end_date: 结束日期，格式YYYY-MM-DD
        output_path: 输出CSV文件路径
    
    Returns:
        包含批量采集结果的字典
    """
    try:
        print(f"开始批量采集 {len(stock_list)} 只股票数据")
        print(f"时间范围: {start_date} 到 {end_date}")
        print(f"输出路径: {output_path}")
        
        all_data = []
        results = []
        failed_stocks = []
        
        # 确保输出目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"创建输出目录: {output_dir}")
        
        # 遍历股票列表
        for i, stock_info in enumerate(stock_list, 1):
            symbol = stock_info.get('symbol', '')
            name = stock_info.get('name', '')
            
            if not symbol or not name:
                print(f"跳过第 {i} 只股票: 缺少symbol或name")
                continue
            
            print(f"\n[{i}/{len(stock_list)}] 采集 {symbol} ({name})...")
            
            # 尝试不同的数据源
            data_sources = ["yfinance", "baostock", "akshare"]
            stock_result = None
            
            for data_source in data_sources:
                print(f"  尝试数据源: {data_source}")
                result = collect_stock_data(
                    symbol=symbol,
                    name=name,
                    start_date=start_date,
                    end_date=end_date,
                    data_source=data_source
                )
                
                if result.get("success", False):
                    stock_result = result
                    print(f"  成功从 {data_source} 获取数据")
                    break
                else:
                    print(f"  {data_source} 失败: {result.get('error', '未知错误')}")
            
            if stock_result and stock_result.get("success", False):
                # 提取数据并添加到总数据集中
                data = stock_result.get("data", [])
                if data:
                    # 转换为DataFrame
                    df = pd.DataFrame(data)
                    
                    # 确保有必要的列
                    required_columns = ['symbol', 'name', 'date', 'open', 'high', 'low', 'close', 'volume']
                    for col in required_columns:
                        if col not in df.columns:
                            df[col] = None
                    
                    # 只保留需要的列
                    df = df[required_columns]
                    
                    # 添加到总数据
                    all_data.append(df)
                    
                    # 记录结果
                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "status": "success",
                        "data_source": stock_result.get("data_source", "unknown"),
                        "data_points": len(df),
                        "date_range": stock_result.get("stats", {}).get("date_range", {}),
                        "message": stock_result.get("message", "")
                    })
                    
                    print(f"  成功采集 {len(df)} 条数据")
                else:
                    failed_stocks.append({
                        "symbol": symbol,
                        "name": name,
                        "error": "获取到数据但数据为空"
                    })
                    print(f"  失败: 获取到数据但数据为空")
            else:
                failed_stocks.append({
                    "symbol": symbol,
                    "name": name,
                    "error": "所有数据源都失败"
                })
                print(f"  失败: 所有数据源都失败")
        
        # 合并所有数据
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            
            # 按日期和股票代码排序
            if 'date' in combined_df.columns:
                combined_df['date'] = pd.to_datetime(combined_df['date'])
                combined_df = combined_df.sort_values(['symbol', 'date'])
            
            # 保存到CSV文件
            try:
                combined_df.to_csv(output_path, index=False, encoding='utf-8-sig')
                print(f"\n数据已保存到: {output_path}")
                print(f"总数据量: {len(combined_df)} 条记录")
                
                # 统计信息
                stock_counts = combined_df['symbol'].value_counts().to_dict()
                
                return {
                    "success": True,
                    "output_path": output_path,
                    "total_records": len(combined_df),
                    "successful_stocks": len(results),
                    "failed_stocks": len(failed_stocks),
                    "stock_counts": stock_counts,
                    "results": results,
                    "failed_stocks_list": failed_stocks,
                    "data_preview": combined_df.head(10).to_dict(orient='records'),
                    "message": f"成功采集 {len(results)} 只股票，共 {len(combined_df)} 条数据"
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "error": f"保存数据失败: {str(e)}",
                    "successful_stocks": len(results),
                    "failed_stocks": len(failed_stocks),
                    "results": results,
                    "failed_stocks_list": failed_stocks
                }
        else:
            return {
                "success": False,
                "error": "未成功采集到任何股票数据",
                "successful_stocks": 0,
                "failed_stocks": len(failed_stocks),
                "failed_stocks_list": failed_stocks
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"批量采集失败: {str(e)}"
        }