from langchain_core.tools import tool
import akshare as ak
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional
import json

@tool
def analyze_stock_fundamentals(symbol: str) -> Dict[str, Any]:
    """
    分析股票基本面
    
    Args:
        symbol: 股票代码
    
    Returns:
        包含股票基本面分析结果的字典
    """
    try:
        # 处理股票代码格式
        if not symbol.startswith(('sh', 'sz', 'bj')):
            if symbol.startswith('6'):
                symbol_full = f"sh{symbol}"
            elif symbol.startswith(('0', '3')):
                symbol_full = f"sz{symbol}"
            elif symbol.startswith('8'):
                symbol_full = f"bj{symbol}"
            else:
                symbol_full = f"sh{symbol}"
        else:
            symbol_full = symbol
        
        print(f"分析股票基本面: {symbol_full}")
        
        results = {
            "success": True,
            "symbol": symbol,
            "symbol_full": symbol_full,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "company_info": {},
            "financial_ratios": {},
            "valuation_metrics": {},
            "profitability": {},
            "growth_metrics": {},
            "risk_indicators": {},
            "recommendation": {}
        }
        
        # 1. 获取公司基本信息
        try:
            # 获取股票基本信息
            stock_info = ak.stock_individual_info_em(symbol=symbol_full.replace('sh', '').replace('sz', '').replace('bj', ''))
            if not stock_info.empty:
                info_dict = {}
                for _, row in stock_info.iterrows():
                    info_dict[row['item']] = row['value']
                
                results["company_info"] = {
                    "company_name": info_dict.get('公司名称', ''),
                    "industry": info_dict.get('所属行业', ''),
                    "listing_date": info_dict.get('上市时间', ''),
                    "total_shares": info_dict.get('总股本', ''),
                    "circulating_shares": info_dict.get('流通股本', ''),
                    "region": info_dict.get('地域', '')
                }
        except:
            pass  # 忽略基本信息获取失败
        
        # 2. 获取财务指标
        try:
            # 获取资产负债表、利润表、现金流量表
            # 这里使用简化的财务数据获取
            financial_data = ak.stock_financial_analysis_indicator(symbol=symbol_full.replace('sh', '').replace('sz', '').replace('bj', ''))
            
            if not financial_data.empty:
                # 获取最新一期数据
                latest_data = financial_data.iloc[0]
                
                # 盈利能力指标
                results["profitability"] = {
                    "roe": float(latest_data.get('净资产收益率', 0)),  # 净资产收益率
                    "roa": float(latest_data.get('总资产报酬率', 0)),  # 总资产报酬率
                    "gross_margin": float(latest_data.get('销售毛利率', 0)),  # 销售毛利率
                    "net_margin": float(latest_data.get('销售净利率', 0)),  # 销售净利率
                    "eps": float(latest_data.get('基本每股收益', 0))  # 每股收益
                }
                
                # 偿债能力指标
                results["risk_indicators"]["debt_ratios"] = {
                    "debt_to_asset": float(latest_data.get('资产负债率', 0)),  # 资产负债率
                    "current_ratio": float(latest_data.get('流动比率', 0)),  # 流动比率
                    "quick_ratio": float(latest_data.get('速动比率', 0))  # 速动比率
                }
                
                # 运营能力指标
                results["financial_ratios"]["operation"] = {
                    "inventory_turnover": float(latest_data.get('存货周转率', 0)),  # 存货周转率
                    "receivables_turnover": float(latest_data.get('应收账款周转率', 0)),  # 应收账款周转率
                    "total_asset_turnover": float(latest_data.get('总资产周转率', 0))  # 总资产周转率
                }
                
                # 成长性指标（需要多期数据计算）
                if len(financial_data) >= 2:
                    prev_data = financial_data.iloc[1]
                    
                    revenue_growth = 0
                    if latest_data.get('营业总收入') and prev_data.get('营业总收入'):
                        try:
                            revenue_current = float(latest_data['营业总收入'])
                            revenue_prev = float(prev_data['营业总收入'])
                            revenue_growth = (revenue_current - revenue_prev) / revenue_prev * 100
                        except:
                            pass
                    
                    profit_growth = 0
                    if latest_data.get('净利润') and prev_data.get('净利润'):
                        try:
                            profit_current = float(latest_data['净利润'])
                            profit_prev = float(prev_data['净利润'])
                            profit_growth = (profit_current - profit_prev) / profit_prev * 100
                        except:
                            pass
                    
                    results["growth_metrics"] = {
                        "revenue_growth_pct": revenue_growth,
                        "profit_growth_pct": profit_growth,
                        "eps_growth_pct": 0  # 需要计算
                    }
        
        except Exception as e:
            results["financial_data_error"] = f"财务数据获取失败: {str(e)}"
        
        # 3. 获取估值指标
        try:
            # 获取实时行情数据
            spot_data = ak.stock_zh_a_spot_em()
            if not spot_data.empty:
                stock_spot = spot_data[spot_data['代码'] == symbol_full.replace('sh', '').replace('sz', '').replace('bj', '')]
                if not stock_spot.empty:
                    current_price = float(stock_spot.iloc[0]['最新价'])
                    
                    # 计算简单的估值指标（需要财务数据）
                    if results["profitability"].get("eps", 0) > 0:
                        pe_ratio = current_price / results["profitability"]["eps"]
                        results["valuation_metrics"]["pe_ratio"] = pe_ratio
                    
                    # 获取市盈率、市净率等
                    try:
                        valuation_data = ak.stock_a_pe(symbol=symbol_full)
                        if not valuation_data.empty:
                            latest_valuation = valuation_data.iloc[0]
                            results["valuation_metrics"].update({
                                "pe_ttm": float(latest_valuation.get('市盈率', 0)),
                                "pb_ratio": float(latest_valuation.get('市净率', 0)),
                                "ps_ratio": float(latest_valuation.get('市销率', 0)),
                                "dividend_yield": float(latest_valuation.get('股息率', 0))
                            })
                    except:
                        pass
        
        except Exception as e:
            results["valuation_error"] = f"估值数据获取失败: {str(e)}"
        
        # 4. 生成基本面评分
        score = 0
        factors = []
        
        # ROE评分
        roe = results["profitability"].get("roe", 0)
        if roe > 20:
            score += 25
            factors.append({"factor": "ROE", "score": 25, "value": roe, "comment": "优秀"})
        elif roe > 15:
            score += 20
            factors.append({"factor": "ROE", "score": 20, "value": roe, "comment": "良好"})
        elif roe > 10:
            score += 15
            factors.append({"factor": "ROE", "score": 15, "value": roe, "comment": "一般"})
        else:
            score += 5
            factors.append({"factor": "ROE", "score": 5, "value": roe, "comment": "较差"})
        
        # 毛利率评分
        gross_margin = results["profitability"].get("gross_margin", 0)
        if gross_margin > 40:
            score += 20
            factors.append({"factor": "毛利率", "score": 20, "value": gross_margin, "comment": "优秀"})
        elif gross_margin > 30:
            score += 15
            factors.append({"factor": "毛利率", "score": 15, "value": gross_margin, "comment": "良好"})
        elif gross_margin > 20:
            score += 10
            factors.append({"factor": "毛利率", "score": 10, "value": gross_margin, "comment": "一般"})
        else:
            score += 5
            factors.append({"factor": "毛利率", "score": 5, "value": gross_margin, "comment": "较差"})
        
        # 资产负债率评分
        debt_ratio = results["risk_indicators"].get("debt_ratios", {}).get("debt_to_asset", 0)
        if debt_ratio < 40:
            score += 20
            factors.append({"factor": "资产负债率", "score": 20, "value": debt_ratio, "comment": "安全"})
        elif debt_ratio < 60:
            score += 15
            factors.append({"factor": "资产负债率", "score": 15, "value": debt_ratio, "comment": "适中"})
        elif debt_ratio < 80:
            score += 10
            factors.append({"factor": "资产负债率", "score": 10, "value": debt_ratio, "comment": "较高"})
        else:
            score += 5
            factors.append({"factor": "资产负债率", "score": 5, "value": debt_ratio, "comment": "风险高"})
        
        # 成长性评分
        revenue_growth = results["growth_metrics"].get("revenue_growth_pct", 0)
        if revenue_growth > 30:
            score += 20
            factors.append({"factor": "营收增长", "score": 20, "value": revenue_growth, "comment": "高速增长"})
        elif revenue_growth > 15:
            score += 15
            factors.append({"factor": "营收增长", "score": 15, "value": revenue_growth, "comment": "稳定增长"})
        elif revenue_growth > 0:
            score += 10
            factors.append({"factor": "营收增长", "score": 10, "value": revenue_growth, "comment": "缓慢增长"})
        else:
            score += 5
            factors.append({"factor": "营收增长", "score": 5, "value": revenue_growth, "comment": "负增长"})
        
        # 估值评分
        pe_ratio = results["valuation_metrics"].get("pe_ratio", 0) or results["valuation_metrics"].get("pe_ttm", 0)
        if 0 < pe_ratio < 15:
            score += 15
            factors.append({"factor": "市盈率", "score": 15, "value": pe_ratio, "comment": "低估"})
        elif 15 <= pe_ratio < 25:
            score += 10
            factors.append({"factor": "市盈率", "score": 10, "value": pe_ratio, "comment": "合理"})
        elif 25 <= pe_ratio < 40:
            score += 5
            factors.append({"factor": "市盈率", "score": 5, "value": pe_ratio, "comment": "偏高"})
        else:
            score += 0
            factors.append({"factor": "市盈率", "score": 0, "value": pe_ratio, "comment": "高估"})
        
        # 生成投资建议
        if score >= 80:
            recommendation = "强烈推荐"
            risk_level = "低"
        elif score >= 70:
            recommendation = "推荐"
            risk_level = "中低"
        elif score >= 60:
            recommendation = "谨慎推荐"
            risk_level = "中"
        elif score >= 50:
            recommendation = "中性"
            risk_level = "中高"
        else:
            recommendation = "回避"
            risk_level = "高"
        
        results["fundamental_score"] = {
            "total_score": score,
            "max_score": 100,
            "factors": factors,
            "recommendation": recommendation,
            "risk_level": risk_level,
            "summary": f"基本面综合评分: {score}/100 - {recommendation} (风险等级: {risk_level})"
        }
        
        results["message"] = f"成功分析 {symbol} 的基本面"
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": f"分析股票基本面失败: {str(e)}",
            "symbol": symbol
        }