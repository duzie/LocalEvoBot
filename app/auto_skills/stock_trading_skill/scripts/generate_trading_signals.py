from langchain_core.tools import tool
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

@tool
def generate_trading_signals(symbol: str, strategy: str = "multi_factor") -> Dict[str, Any]:
    """
    生成交易信号
    
    Args:
        symbol: 股票代码
        strategy: 策略：multi_factor（多因子）、momentum（动量）、mean_reversion（均值回归）
    
    Returns:
        包含交易信号的字典
    """
    try:
        # 导入akshare获取数据
        import akshare as ak
        
        print(f"生成交易信号: {symbol}, 策略: {strategy}")
        
        # 获取最近60天的数据
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")  # 获取180天数据用于计算指标
        
        # 处理股票代码
        if not symbol.startswith(('sh', 'sz', 'bj')):
            if symbol.startswith('6'):
                symbol_full = f"sh{symbol}"
            elif symbol.startswith(('0', '3')):
                symbol_full = f"sz{symbol}"
            else:
                symbol_full = f"sh{symbol}"
        else:
            symbol_full = symbol
        
        # 获取股票数据
        stock_df = ak.stock_zh_a_hist(symbol=symbol_full, period="daily", 
                                     start_date=start_date, end_date=end_date, 
                                     adjust="qfq")
        
        if stock_df.empty:
            return {
                "success": False,
                "error": f"未找到股票 {symbol} 的数据"
            }
        
        # 重命名列
        column_mapping = {
            '日期': 'date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
            '涨跌幅': 'change_pct'
        }
        
        stock_df = stock_df.rename(columns={k: v for k, v in column_mapping.items() if k in stock_df.columns})
        
        # 确保必要的列存在
        required_cols = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_cols:
            if col not in stock_df.columns:
                return {
                    "success": False,
                    "error": f"数据缺少必要列: {col}"
                }
        
        # 转换数据类型
        stock_df['date'] = pd.to_datetime(stock_df['date'])
        for col in ['open', 'high', 'low', 'close', 'volume']:
            stock_df[col] = pd.to_numeric(stock_df[col], errors='coerce')
        
        # 按日期排序
        stock_df = stock_df.sort_values('date').reset_index(drop=True)
        
        # 计算技术指标
        # 1. 移动平均线
        stock_df['MA5'] = stock_df['close'].rolling(window=5, min_periods=1).mean()
        stock_df['MA10'] = stock_df['close'].rolling(window=10, min_periods=1).mean()
        stock_df['MA20'] = stock_df['close'].rolling(window=20, min_periods=1).mean()
        stock_df['MA60'] = stock_df['close'].rolling(window=60, min_periods=1).mean()
        
        # 2. RSI
        delta = stock_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        stock_df['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. MACD
        ema_short = stock_df['close'].ewm(span=12, adjust=False).mean()
        ema_long = stock_df['close'].ewm(span=26, adjust=False).mean()
        stock_df['MACD_DIF'] = ema_short - ema_long
        stock_df['MACD_DEA'] = stock_df['MACD_DIF'].ewm(span=9, adjust=False).mean()
        stock_df['MACD_hist'] = stock_df['MACD_DIF'] - stock_df['MACD_DEA']
        
        # 4. 布林带
        stock_df['BOLL_mid'] = stock_df['close'].rolling(window=20, min_periods=1).mean()
        std = stock_df['close'].rolling(window=20, min_periods=1).std()
        stock_df['BOLL_upper'] = stock_df['BOLL_mid'] + 2 * std
        stock_df['BOLL_lower'] = stock_df['BOLL_mid'] - 2 * std
        
        # 5. 成交量指标
        stock_df['VOL_MA5'] = stock_df['volume'].rolling(window=5, min_periods=1).mean()
        stock_df['VOL_MA10'] = stock_df['volume'].rolling(window=10, min_periods=1).mean()
        
        # 6. 动量指标
        stock_df['MOMENTUM_5'] = stock_df['close'].pct_change(periods=5)
        stock_df['MOMENTUM_10'] = stock_df['close'].pct_change(periods=10)
        stock_df['MOMENTUM_20'] = stock_df['close'].pct_change(periods=20)
        
        # 获取最新数据
        latest = stock_df.iloc[-1]
        prev = stock_df.iloc[-2] if len(stock_df) > 1 else latest
        
        signals = []
        confidence = 0
        signal_strength = "弱"
        
        # 根据策略生成信号
        if strategy == "multi_factor":
            # 多因子策略：综合考虑多个技术指标
            
            buy_signals = 0
            sell_signals = 0
            total_factors = 0
            
            # 1. 均线系统信号
            total_factors += 1
            if latest['MA5'] > latest['MA10'] > latest['MA20']:
                buy_signals += 1
                signals.append({"factor": "均线多头排列", "signal": "买入", "weight": 1})
            elif latest['MA5'] < latest['MA10'] < latest['MA20']:
                sell_signals += 1
                signals.append({"factor": "均线空头排列", "signal": "卖出", "weight": 1})
            
            # 2. RSI信号
            total_factors += 1
            if latest['RSI'] < 30:
                buy_signals += 1
                signals.append({"factor": "RSI超卖", "signal": "买入", "weight": 1})
            elif latest['RSI'] > 70:
                sell_signals += 1
                signals.append({"factor": "RSI超买", "signal": "卖出", "weight": 1})
            
            # 3. MACD信号
            total_factors += 1
            if latest['MACD_DIF'] > latest['MACD_DEA'] and prev['MACD_DIF'] <= prev['MACD_DEA']:
                buy_signals += 1
                signals.append({"factor": "MACD金叉", "signal": "买入", "weight": 1})
            elif latest['MACD_DIF'] < latest['MACD_DEA'] and prev['MACD_DIF'] >= prev['MACD_DEA']:
                sell_signals += 1
                signals.append({"factor": "MACD死叉", "signal": "卖出", "weight": 1})
            
            # 4. 布林带信号
            total_factors += 1
            if latest['close'] < latest['BOLL_lower']:
                buy_signals += 1
                signals.append({"factor": "触及布林带下轨", "signal": "买入", "weight": 1})
            elif latest['close'] > latest['BOLL_upper']:
                sell_signals += 1
                signals.append({"factor": "触及布林带上轨", "signal": "卖出", "weight": 1})
            
            # 5. 成交量信号
            total_factors += 1
            if latest['volume'] > latest['VOL_MA5'] * 1.5:
                if latest['close'] > latest['open']:
                    buy_signals += 1
                    signals.append({"factor": "放量上涨", "signal": "买入", "weight": 1})
                else:
                    sell_signals += 1
                    signals.append({"factor": "放量下跌", "signal": "卖出", "weight": 1})
            
            # 计算综合信号
            if total_factors > 0:
                net_signals = buy_signals - sell_signals
                confidence = abs(net_signals) / total_factors * 100
                
                if net_signals > 0:
                    action = "买入"
                    signal_type = "bullish"
                elif net_signals < 0:
                    action = "卖出"
                    signal_type = "bearish"
                else:
                    action = "持有"
                    signal_type = "neutral"
                
                # 判断信号强度
                if confidence > 60:
                    signal_strength = "强"
                elif confidence > 40:
                    signal_strength = "中"
                else:
                    signal_strength = "弱"
        
        elif strategy == "momentum":
            # 动量策略：跟随趋势
            momentum_5 = latest['MOMENTUM_5'] * 100 if not pd.isna(latest['MOMENTUM_5']) else 0
            momentum_10 = latest['MOMENTUM_10'] * 100 if not pd.isna(latest['MOMENTUM_10']) else 0
            
            if momentum_5 > 5 and momentum_10 > 10:
                action = "买入"
                signal_type = "bullish"
                confidence = 70
                signal_strength = "强"
                signals.append({"factor": "短期动量强劲", "signal": "买入", "weight": 1})
                signals.append({"factor": "中期动量向上", "signal": "买入", "weight": 1})
            
            elif momentum_5 < -5 and momentum_10 < -10:
                action = "卖出"
                signal_type = "bearish"
                confidence = 70
                signal_strength = "强"
                signals.append({"factor": "短期动量疲弱", "signal": "卖出", "weight": 1})
                signals.append({"factor": "中期动量向下", "signal": "卖出", "weight": 1})
            
            else:
                action = "持有"
                signal_type = "neutral"
                confidence = 50
                signal_strength = "弱"
                signals.append({"factor": "动量不明确", "signal": "持有", "weight": 1})
        
        elif strategy == "mean_reversion":
            # 均值回归策略：价格偏离均值时反向操作
            
            # 计算价格与均线的偏离度
            deviation_ma20 = (latest['close'] - latest['MA20']) / latest['MA20'] * 100
            deviation_boll = (latest['close'] - latest['BOLL_mid']) / latest['BOLL_mid'] * 100
            
            if deviation_ma20 < -10 or latest['close'] < latest['BOLL_lower']:
                action = "买入"
                signal_type = "bullish"
                confidence = 65
                signal_strength = "中"
                signals.append({"factor": "价格显著低于20日均线", "signal": "买入", "weight": 1})
                signals.append({"factor": "触及布林带下轨", "signal": "买入", "weight": 1})
            
            elif deviation_ma20 > 10 or latest['close'] > latest['BOLL_upper']:
                action = "卖出"
                signal_type = "bearish"
                confidence = 65
                signal_strength = "中"
                signals.append({"factor": "价格显著高于20日均线", "signal": "卖出", "weight": 1})
                signals.append({"factor": "触及布林带上轨", "signal": "卖出", "weight": 1})
            
            else:
                action = "持有"
                signal_type = "neutral"
                confidence = 50
                signal_strength = "弱"
                signals.append({"factor": "价格在合理区间", "signal": "持有", "weight": 1})
        
        else:
            return {
                "success": False,
                "error": f"不支持的策略: {strategy}，支持 multi_factor, momentum, mean_reversion"
            }
        
        # 准备返回结果
        result = {
            "success": True,
            "symbol": symbol,
            "strategy": strategy,
            "current_price": float(latest['close']),
            "signal_date": latest['date'].strftime('%Y-%m-%d'),
            "signal": {
                "action": action,
                "type": signal_type,
                "confidence": confidence,
                "strength": signal_strength,
                "signals": signals
            },
            "technical_indicators": {
                "MA5": float(latest['MA5']) if not pd.isna(latest['MA5']) else None,
                "MA10": float(latest['MA10']) if not pd.isna(latest['MA10']) else None,
                "MA20": float(latest['MA20']) if not pd.isna(latest['MA20']) else None,
                "RSI": float(latest['RSI']) if not pd.isna(latest['RSI']) else None,
                "MACD_DIF": float(latest['MACD_DIF']) if not pd.isna(latest['MACD_DIF']) else None,
                "MACD_hist": float(latest['MACD_hist']) if not pd.isna(latest['MACD_hist']) else None,
                "BOLL_upper": float(latest['BOLL_upper']) if not pd.isna(latest['BOLL_upper']) else None,
                "BOLL_lower": float(latest['BOLL_lower']) if not pd.isna(latest['BOLL_lower']) else None
            },
            "summary": f"{symbol} 交易信号: {action} (置信度: {confidence:.1f}%, 强度: {signal_strength})"
        }
        
        return result
        
    except Exception as e:
        return {
            "success": False,
            "error": f"生成交易信号失败: {str(e)}",
            "symbol": symbol,
            "strategy": strategy
        }