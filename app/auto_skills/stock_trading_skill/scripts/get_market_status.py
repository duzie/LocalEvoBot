from langchain_core.tools import tool
import akshare as ak
import pandas as pd
from datetime import datetime
from typing import Dict, Any
import json

@tool
def get_market_status(market: str = "A股") -> Dict[str, Any]:
    """
    获取市场状态和热门股票
    
    Args:
        market: 市场：A股、港股、美股
    
    Returns:
        包含市场状态信息的字典
    """
    try:
        results = {
            "success": True,
            "market": market,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "market_overview": {},
            "top_gainers": [],
            "top_losers": [],
            "most_active": [],
            "sector_performance": [],
            "market_indices": []
        }
        
        if market == "A股":
            # 获取A股市场概览
            try:
                # 获取上证指数
                sh_index = ak.stock_zh_index_spot()
                sh_df = sh_index[sh_index['代码'] == 'sh000001']
                if not sh_df.empty:
                    results["market_indices"].append({
                        "name": "上证指数",
                        "symbol": "sh000001",
                        "price": float(sh_df.iloc[0]['最新价']),
                        "change": float(sh_df.iloc[0]['涨跌额']),
                        "change_pct": float(sh_df.iloc[0]['涨跌幅'].replace('%', ''))
                    })
                
                # 获取深证成指
                sz_df = sh_index[sh_index['代码'] == 'sz399001']
                if not sz_df.empty:
                    results["market_indices"].append({
                        "name": "深证成指",
                        "symbol": "sz399001",
                        "price": float(sz_df.iloc[0]['最新价']),
                        "change": float(sz_df.iloc[0]['涨跌额']),
                        "change_pct": float(sz_df.iloc[0]['涨跌幅'].replace('%', ''))
                    })
                
                # 获取创业板指
                cyb_df = sh_index[sh_index['代码'] == 'sz399006']
                if not cyb_df.empty:
                    results["market_indices"].append({
                        "name": "创业板指",
                        "symbol": "sz399006",
                        "price": float(cyb_df.iloc[0]['最新价']),
                        "change": float(cyb_df.iloc[0]['涨跌额']),
                        "change_pct": float(cyb_df.iloc[0]['涨跌幅'].replace('%', ''))
                    })
                
                # 获取A股涨跌统计
                stock_summary = ak.stock_zh_a_spot_em()
                if not stock_summary.empty:
                    total_stocks = len(stock_summary)
                    rising = len(stock_summary[stock_summary['涨跌幅'] > 0])
                    falling = len(stock_summary[stock_summary['涨跌幅'] < 0])
                    unchanged = len(stock_summary[stock_summary['涨跌幅'] == 0])
                    
                    results["market_overview"] = {
                        "total_stocks": total_stocks,
                        "rising": rising,
                        "falling": falling,
                        "unchanged": unchanged,
                        "rise_ratio": rising / total_stocks * 100 if total_stocks > 0 else 0,
                        "fall_ratio": falling / total_stocks * 100 if total_stocks > 0 else 0
                    }
                    
                    # 获取涨幅榜（前10）
                    top_gainers = stock_summary.nlargest(10, '涨跌幅')
                    results["top_gainers"] = top_gainers[['代码', '名称', '最新价', '涨跌幅', '换手率']].to_dict('records')
                    
                    # 获取跌幅榜（前10）
                    top_losers = stock_summary.nsmallest(10, '涨跌幅')
                    results["top_losers"] = top_losers[['代码', '名称', '最新价', '涨跌幅', '换手率']].to_dict('records')
                    
                    # 获取成交额榜（前10）
                    most_active = stock_summary.nlargest(10, '成交额')
                    results["most_active"] = most_active[['代码', '名称', '最新价', '涨跌幅', '成交额']].to_dict('records')
                
                # 获取板块涨幅榜
                try:
                    sector_data = ak.stock_board_industry_name_em()
                    if not sector_data.empty:
                        top_sectors = sector_data.nlargest(10, '涨跌幅')
                        results["sector_performance"] = top_sectors[['板块名称', '涨跌幅', '总市值', '换手率']].to_dict('records')
                except:
                    pass  # 忽略板块数据获取失败
                
            except Exception as e:
                results["market_overview"]["error"] = f"获取A股数据时出错: {str(e)}"
        
        elif market == "港股":
            try:
                # 获取港股主要指数
                hk_index = ak.stock_hk_index_spot()
                if not hk_index.empty:
                    # 恒生指数
                    hsi = hk_index[hk_index['index_code'] == 'HSI']
                    if not hsi.empty:
                        results["market_indices"].append({
                            "name": "恒生指数",
                            "symbol": "HSI",
                            "price": float(hsi.iloc[0]['close']),
                            "change": float(hsi.iloc[0]['change']),
                            "change_pct": float(hsi.iloc[0]['change_pct'])
                        })
                
                results["market_overview"] = {
                    "message": "港股数据获取成功",
                    "data_source": "akshare"
                }
                
            except Exception as e:
                results["market_overview"]["error"] = f"获取港股数据时出错: {str(e)}"
        
        elif market == "美股":
            try:
                # 获取美股主要指数
                us_index = ak.stock_us_spot()
                if not us_index.empty:
                    # 道琼斯指数
                    dow = us_index[us_index['symbol'] == '.DJI']
                    if not dow.empty:
                        results["market_indices"].append({
                            "name": "道琼斯指数",
                            "symbol": ".DJI",
                            "price": float(dow.iloc[0]['price']),
                            "change": float(dow.iloc[0]['change']),
                            "change_pct": float(dow.iloc[0]['change'].replace('%', '')) if isinstance(dow.iloc[0]['change'], str) else 0
                        })
                
                results["market_overview"] = {
                    "message": "美股数据获取成功",
                    "data_source": "akshare"
                }
                
            except Exception as e:
                results["market_overview"]["error"] = f"获取美股数据时出错: {str(e)}"
        
        else:
            return {
                "success": False,
                "error": f"不支持的市场类型: {market}，支持 A股、港股、美股"
            }
        
        # 添加市场状态判断
        if results["market_overview"] and "rise_ratio" in results["market_overview"]:
            rise_ratio = results["market_overview"]["rise_ratio"]
            if rise_ratio > 60:
                market_status = "强势上涨"
            elif rise_ratio > 40:
                market_status = "温和上涨"
            elif rise_ratio > 20:
                market_status = "震荡偏强"
            elif rise_ratio > 10:
                market_status = "震荡偏弱"
            else:
                market_status = "弱势下跌"
            
            results["market_status"] = market_status
        
        results["message"] = f"成功获取 {market} 市场状态"
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": f"获取市场状态失败: {str(e)}",
            "market": market
        }