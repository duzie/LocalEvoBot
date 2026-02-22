from langchain_core.tools import tool
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import json

@tool
def calculate_technical_indicators(stock_data: Dict[str, Any], 
                                  indicators: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    计算技术指标
    
    Args:
        stock_data: 股票数据字典（来自get_stock_data）
        indicators: 要计算的指标列表，如 ['MA', 'MACD', 'RSI', 'KDJ', 'BOLL']
    
    Returns:
        包含技术指标计算结果的字典
    """
    try:
        # 默认指标列表
        if indicators is None:
            indicators = ['MA', 'MACD', 'RSI', 'KDJ', 'BOLL']
        
        # 将数据转换为DataFrame
        if 'data' not in stock_data:
            return {
                "success": False,
                "error": "股票数据格式错误，缺少'data'字段"
            }
        
        df = pd.DataFrame(stock_data['data'])
        
        # 确保必要的列存在
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return {
                "success": False,
                "error": f"数据缺少必要列: {missing_columns}"
            }
        
        # 确保数据类型正确
        df['date'] = pd.to_datetime(df['date'])
        df['close'] = pd.to_numeric(df['close'], errors='coerce')
        df['open'] = pd.to_numeric(df['open'], errors='coerce')
        df['high'] = pd.to_numeric(df['high'], errors='coerce')
        df['low'] = pd.to_numeric(df['low'], errors='coerce')
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce')
        
        # 按日期排序
        df = df.sort_values('date').reset_index(drop=True)
        
        results = {
            "success": True,
            "symbol": stock_data.get('symbol', 'unknown'),
            "indicators_calculated": [],
            "signals": {},
            "data_with_indicators": []
        }
        
        # 计算移动平均线 (MA)
        if 'MA' in indicators:
            # 计算不同周期的移动平均线
            ma_periods = [5, 10, 20, 30, 60]
            for period in ma_periods:
                column_name = f'MA{period}'
                df[column_name] = df['close'].rolling(window=period, min_periods=1).mean()
                results["indicators_calculated"].append(column_name)
            
            # 生成均线交叉信号
            if len(df) > 20:
                df['MA5_MA10_cross'] = np.where(df['MA5'] > df['MA10'], 1, -1)
                df['MA5_MA10_signal'] = np.where(
                    (df['MA5_MA10_cross'] == 1) & (df['MA5_MA10_cross'].shift(1) == -1), 
                    'golden_cross',  # 金叉
                    np.where(
                        (df['MA5_MA10_cross'] == -1) & (df['MA5_MA10_cross'].shift(1) == 1),
                        'death_cross',  # 死叉
                        'hold'
                    )
                )
                results["signals"]["ma_cross"] = df[['date', 'MA5_MA10_signal']].to_dict('records')
        
        # 计算MACD
        if 'MACD' in indicators and len(df) >= 26:
            # 计算短期EMA (12日)
            ema_short = df['close'].ewm(span=12, adjust=False).mean()
            # 计算长期EMA (26日)
            ema_long = df['close'].ewm(span=26, adjust=False).mean()
            # 计算DIF
            df['MACD_DIF'] = ema_short - ema_long
            # 计算DEA (DIF的9日EMA)
            df['MACD_DEA'] = df['MACD_DIF'].ewm(span=9, adjust=False).mean()
            # 计算MACD柱状图
            df['MACD_hist'] = df['MACD_DIF'] - df['MACD_DEA']
            
            results["indicators_calculated"].extend(['MACD_DIF', 'MACD_DEA', 'MACD_hist'])
            
            # 生成MACD信号
            df['MACD_signal'] = np.where(
                (df['MACD_DIF'] > df['MACD_DEA']) & (df['MACD_DIF'].shift(1) <= df['MACD_DEA'].shift(1)),
                'buy',
                np.where(
                    (df['MACD_DIF'] < df['MACD_DEA']) & (df['MACD_DIF'].shift(1) >= df['MACD_DEA'].shift(1)),
                    'sell',
                    'hold'
                )
            )
            results["signals"]["macd"] = df[['date', 'MACD_signal']].to_dict('records')
        
        # 计算RSI
        if 'RSI' in indicators and len(df) >= 14:
            # 计算价格变化
            delta = df['close'].diff()
            
            # 计算上涨和下跌
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            
            # 计算RSI
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            results["indicators_calculated"].append('RSI')
            
            # 生成RSI信号
            df['RSI_signal'] = np.where(
                df['RSI'] < 30,
                'oversold_buy',
                np.where(
                    df['RSI'] > 70,
                    'overbought_sell',
                    'hold'
                )
            )
            results["signals"]["rsi"] = df[['date', 'RSI_signal']].to_dict('records')
        
        # 计算KDJ
        if 'KDJ' in indicators and len(df) >= 9:
            # 计算最近9日的最低最低价和最高最高价
            low_min = df['low'].rolling(window=9, min_periods=1).min()
            high_max = df['high'].rolling(window=9, min_periods=1).max()
            
            # 计算RSV
            rsv = 100 * (df['close'] - low_min) / (high_max - low_min)
            rsv = rsv.fillna(50)  # 处理除零情况
            
            # 计算K值 (RSV的3日EMA)
            df['K'] = rsv.ewm(alpha=1/3, adjust=False).mean()
            # 计算D值 (K值的3日EMA)
            df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean()
            # 计算J值
            df['J'] = 3 * df['K'] - 2 * df['D']
            
            results["indicators_calculated"].extend(['K', 'D', 'J'])
            
            # 生成KDJ信号
            df['KDJ_signal'] = np.where(
                (df['K'] < 20) & (df['D'] < 20) & (df['J'] < 20),
                'oversold_buy',
                np.where(
                    (df['K'] > 80) & (df['D'] > 80) & (df['J'] > 80),
                    'overbought_sell',
                    'hold'
                )
            )
            results["signals"]["kdj"] = df[['date', 'KDJ_signal']].to_dict('records')
        
        # 计算布林带 (BOLL)
        if 'BOLL' in indicators and len(df) >= 20:
            # 计算中轨 (20日移动平均线)
            df['BOLL_mid'] = df['close'].rolling(window=20, min_periods=1).mean()
            # 计算标准差
            std = df['close'].rolling(window=20, min_periods=1).std()
            # 计算上轨和下轨
            df['BOLL_upper'] = df['BOLL_mid'] + 2 * std
            df['BOLL_lower'] = df['BOLL_mid'] - 2 * std
            
            results["indicators_calculated"].extend(['BOLL_mid', 'BOLL_upper', 'BOLL_lower'])
            
            # 生成布林带信号
            df['BOLL_signal'] = np.where(
                df['close'] < df['BOLL_lower'],
                'lower_band_buy',
                np.where(
                    df['close'] > df['BOLL_upper'],
                    'upper_band_sell',
                    'hold'
                )
            )
            results["signals"]["boll"] = df[['date', 'BOLL_signal']].to_dict('records')
        
        # 计算成交量指标
        if 'volume' in df.columns:
            # 计算成交量移动平均
            df['VOL_MA5'] = df['volume'].rolling(window=5, min_periods=1).mean()
            df['VOL_MA10'] = df['volume'].rolling(window=10, min_periods=1).mean()
            results["indicators_calculated"].extend(['VOL_MA5', 'VOL_MA10'])
        
        # 准备返回数据（只包含最近100条记录，避免数据过大）
        recent_data = df.tail(100).copy()
        
        # 转换日期为字符串格式
        recent_data['date'] = recent_data['date'].dt.strftime('%Y-%m-%d')
        
        # 转换为字典列表
        results["data_with_indicators"] = recent_data.to_dict('records')
        
        # 计算综合信号
        if results["signals"]:
            # 简单的信号汇总
            latest_signals = {}
            for signal_type, signal_data in results["signals"].items():
                if signal_data:
                    latest_signal = signal_data[-1]  # 获取最新信号
                    latest_signals[signal_type] = latest_signal
            
            results["latest_signals"] = latest_signals
        
        results["message"] = f"成功计算 {len(results['indicators_calculated'])} 个技术指标"
        
        return results
        
    except Exception as e:
        return {
            "success": False,
            "error": f"计算技术指标失败: {str(e)}",
            "indicators_requested": indicators
        }