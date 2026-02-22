from langchain_core.tools import tool
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json
import sys
import os

# 添加父目录到路径，以便导入 collect_stock_data
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

def clean_data_for_serialization(data: Any) -> Any:
    """
    清理数据以便序列化，将numpy/pandas类型转换为Python原生类型
    """
    if isinstance(data, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(data)
    elif isinstance(data, (np.floating, np.float64, np.float32, np.float16)):
        if np.isnan(data) or np.isinf(data):
            return None
        return float(data)
    elif isinstance(data, np.ndarray):
        return [clean_data_for_serialization(item) for item in data.tolist()]
    elif isinstance(data, pd.Series):
        return [clean_data_for_serialization(item) for item in data.tolist()]
    elif isinstance(data, pd.DataFrame):
        return data.to_dict(orient="records")
    elif isinstance(data, pd.Timestamp):
        return data.strftime("%Y-%m-%d")
    elif isinstance(data, pd.Timedelta):
        return str(data)
    elif isinstance(data, dict):
        return {key: clean_data_for_serialization(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [clean_data_for_serialization(item) for item in data]
    elif isinstance(data, (str, int, float, bool)) or data is None:
        return data
    else:
        try:
            return str(data)
        except:
            return None

@tool
def backtest_strategy(symbol: str, strategy_name: str = "ma_crossover", 
                      start_date: str = "2024-01-01", end_date: Optional[str] = None,
                      initial_cash: float = 100000.0) -> Dict[str, Any]:
    """
    回测交易策略（修复版）- 使用 collect_stock_data 替代 get_stock_data
    
    Args:
        symbol: 股票代码，如 '000001'
        strategy_name: 策略名称：ma_crossover（均线交叉）、rsi_oversold（RSI超卖）、macd_divergence（MACD背离）
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD，默认今天
        initial_cash: 初始资金
    
    Returns:
        包含回测结果的字典
    """
    try:
        # 设置结束日期
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        print(f"开始回测: {symbol}, 策略: {strategy_name}, 时间: {start_date} 到 {end_date}")
        
        # 动态导入 collect_stock_data
        try:
            from app.auto_skills.stock_data_collection_skill.scripts.collect_stock_data import collect_stock_data
        except ImportError:
            print("尝试直接调用 collect_stock_data 工具...")
            return {
                "success": False,
                "error": "无法导入 collect_stock_data，请确保 stock_data_collection_skill 已正确加载"
            }
        
        # 使用 collect_stock_data 获取数据
        stock_data_result = collect_stock_data.invoke({
            "symbol": symbol,
            "name": "",
            "start_date": start_date,
            "end_date": end_date,
            "data_source": "baostock"
        })
        
        if not stock_data_result.get("success", False):
            return {
                "success": False,
                "error": f"获取股票数据失败: {stock_data_result.get('error', '未知错误')}"
            }
        
        # 提取数据
        stock_df = pd.DataFrame(stock_data_result.get("data", []))
        
        if stock_df.empty:
            return {
                "success": False,
                "error": f"未找到股票 {symbol} 的数据"
            }
        
        # 确保数据列名正确
        required_columns = ['date', 'open', 'close', 'high', 'low', 'volume']
        for col in required_columns:
            if col not in stock_df.columns:
                if col == 'date' and '日期' in stock_df.columns:
                    stock_df.rename(columns={'日期': 'date'}, inplace=True)
                elif col == 'open' and '开盘' in stock_df.columns:
                    stock_df.rename(columns={'开盘': 'open'}, inplace=True)
                elif col == 'close' and '收盘' in stock_df.columns:
                    stock_df.rename(columns={'收盘': 'close'}, inplace=True)
                elif col == 'high' and '最高' in stock_df.columns:
                    stock_df.rename(columns={'最高': 'high'}, inplace=True)
                elif col == 'low' and '最低' in stock_df.columns:
                    stock_df.rename(columns={'最低': 'low'}, inplace=True)
                elif col == 'volume' and '成交量' in stock_df.columns:
                    stock_df.rename(columns={'成交量': 'volume'}, inplace=True)
        
        # 按日期排序
        stock_df['date'] = pd.to_datetime(stock_df['date'])
        stock_df = stock_df.sort_values('date').reset_index(drop=True)
        
        # 计算技术指标
        stock_df = calculate_technical_indicators_for_backtest(stock_df)
        
        # 根据策略生成交易信号
        signals = generate_trading_signals(stock_df, strategy_name)
        
        # 执行回测
        results = execute_backtest(stock_df, signals, initial_cash)
        
        # 计算性能指标
        performance = calculate_performance_metrics(results, initial_cash)
        
        # 获取最终价值并确保是标量值
        final_value = results["portfolio_value"]["portfolio_value"].iloc[-1]
        if isinstance(final_value, (pd.Series, np.ndarray)):
            final_value = float(final_value.iloc[0]) if hasattr(final_value, 'iloc') else float(final_value[0])
        
        # 清理交易记录
        trades_data = []
        if not results["trades"].empty:
            trades_df = results["trades"].copy()
            if 'date' in trades_df.columns:
                trades_df['date'] = trades_df['date'].apply(
                    lambda x: x.strftime("%Y-%m-%d") if isinstance(x, pd.Timestamp) else str(x)
                )
            trades_data = clean_data_for_serialization(trades_df)
        
        # 创建结果字典
        result_dict = {
            "success": True,
            "symbol": symbol,
            "strategy": strategy_name,
            "period": f"{start_date} 到 {end_date}",
            "initial_cash": float(initial_cash),
            "final_value": float(final_value),
            "total_return": float(performance.get("total_return", 0.0)),
            "annual_return": float(performance.get("annual_return", 0.0)),
            "max_drawdown": float(performance.get("max_drawdown", 0.0)),
            "sharpe_ratio": float(performance.get("sharpe_ratio", 0.0)),
            "win_rate": float(performance.get("win_rate", 0.0)),
            "total_trades": int(performance.get("total_trades", 0)),
            "winning_trades": int(performance.get("winning_trades", 0)),
            "losing_trades": int(performance.get("losing_trades", 0)),
            "avg_win": float(performance.get("avg_win", 0.0)),
            "avg_loss": float(performance.get("avg_loss", 0.0)),
            "profit_factor": float(performance.get("profit_factor", 0.0)),
            "trades": trades_data,
            "summary": f"策略 {strategy_name} 在 {symbol} 上的回测结果：总收益 {performance.get('total_return', 0.0):.2%}，年化收益 {performance.get('annual_return', 0.0):.2%}，最大回撤 {performance.get('max_drawdown', 0.0):.2%}，夏普比率 {performance.get('sharpe_ratio', 0.0):.2f}"
        }
        
        # 清理整个结果字典
        return clean_data_for_serialization(result_dict)
        
    except Exception as e:
        return {
            "success": False,
            "error": f"回测过程中发生错误: {str(e)}"
        }

def calculate_technical_indicators_for_backtest(df: pd.DataFrame) -> pd.DataFrame:
    """计算回测所需的技术指标"""
    df['MA5'] = df['close'].rolling(window=5).mean()
    df['MA10'] = df['close'].rolling(window=10).mean()
    df['MA20'] = df['close'].rolling(window=20).mean()
    df['MA30'] = df['close'].rolling(window=30).mean()
    df['MA60'] = df['close'].rolling(window=60).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    return df

def generate_trading_signals(df: pd.DataFrame, strategy_name: str) -> pd.DataFrame:
    """根据策略生成交易信号"""
    df = df.copy()
    df['signal'] = 0
    
    if strategy_name == "ma_crossover":
        df['ma_signal'] = 0
        df.loc[df['MA5'] > df['MA20'], 'ma_signal'] = 1
        df.loc[df['MA5'] < df['MA20'], 'ma_signal'] = -1
        df['signal'] = df['ma_signal'].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    
    elif strategy_name == "rsi_oversold":
        df.loc[df['RSI'] < 30, 'signal'] = 1
        df.loc[df['RSI'] > 70, 'signal'] = -1
    
    elif strategy_name == "macd_divergence":
        df['macd_signal'] = 0
        df.loc[df['MACD'] > df['MACD_Signal'], 'macd_signal'] = 1
        df.loc[df['MACD'] < df['MACD_Signal'], 'macd_signal'] = -1
        df['signal'] = df['macd_signal'].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    
    return df

def execute_backtest(df: pd.DataFrame, signals: pd.DataFrame, initial_cash: float) -> Dict[str, Any]:
    """执行回测逻辑"""
    cash = initial_cash
    position = 0
    trades = []
    portfolio_values = []
    
    for i in range(len(df)):
        date = df.iloc[i]['date']
        price = df.iloc[i]['close']
        signal = signals.iloc[i]['signal'] if i < len(signals) else 0
        
        current_value = cash + position * price
        
        portfolio_values.append({
            'date': date,
            'portfolio_value': current_value,
            'cash': cash,
            'position': position,
            'position_value': position * price
        })
        
        if signal == 1 and cash > price:
            shares_to_buy = 100
            cost = shares_to_buy * price
            if cost <= cash:
                cash -= cost
                position += shares_to_buy
                trades.append({
                    'date': date,
                    'type': 'BUY',
                    'price': price,
                    'shares': shares_to_buy,
                    'cost': cost,
                    'cash_after': cash,
                    'position_after': position
                })
        
        elif signal == -1 and position > 0:
            proceeds = position * price
            cash += proceeds
            trades.append({
                'date': date,
                'type': 'SELL',
                'price': price,
                'shares': position,
                'proceeds': proceeds,
                'cash_after': cash,
                'position_after': 0
            })
            position = 0
    
    if position > 0:
        last_price = df.iloc[-1]['close']
        proceeds = position * last_price
        cash += proceeds
        trades.append({
            'date': df.iloc[-1]['date'],
            'type': 'SELL',
            'price': last_price,
            'shares': position,
            'proceeds': proceeds,
            'cash_after': cash,
            'position_after': 0
        })
        position = 0
    
    trades_df = pd.DataFrame(trades) if trades else pd.DataFrame()
    portfolio_df = pd.DataFrame(portfolio_values)
    
    if not trades_df.empty and 'date' in trades_df.columns:
        trades_df['date'] = pd.to_datetime(trades_df['date'])
    
    if not portfolio_df.empty and 'date' in portfolio_df.columns:
        portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
    
    return {
        'trades': trades_df,
        'portfolio_value': portfolio_df,
        'final_cash': cash,
        'final_position': position
    }

def calculate_performance_metrics(results: Dict[str, Any], initial_cash: float) -> Dict[str, Any]:
    """计算性能指标"""
    trades_df = results['trades']
    portfolio_df = results['portfolio_value']
    
    if trades_df.empty or portfolio_df.empty:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "win_rate": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0
        }
    
    final_value = portfolio_df['portfolio_value'].iloc[-1]
    total_return = (final_value - initial_cash) / initial_cash
    
    days = (portfolio_df['date'].iloc[-1] - portfolio_df['date'].iloc[0]).days
    if days > 0:
        annual_return = (1 + total_return) ** (365 / days) - 1
    else:
        annual_return = 0.0
    
    portfolio_df['peak'] = portfolio_df['portfolio_value'].cummax()
    portfolio_df['drawdown'] = (portfolio_df['portfolio_value'] - portfolio_df['peak']) / portfolio_df['peak']
    max_drawdown = portfolio_df['drawdown'].min()
    
    daily_returns = portfolio_df['portfolio_value'].pct_change().dropna()
    if len(daily_returns) > 0 and daily_returns.std() > 0:
        sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
    else:
        sharpe_ratio = 0.0
    
    if not trades_df.empty:
        buy_trades = trades_df[trades_df['type'] == 'BUY']
        sell_trades = trades_df[trades_df['type'] == 'SELL']
        
        trades_with_pnl = []
        for i in range(0, len(trades_df), 2):
            if i + 1 < len(trades_df):
                buy = trades_df.iloc[i]
                sell = trades_df.iloc[i + 1]
                if buy['type'] == 'BUY' and sell['type'] == 'SELL':
                    pnl = sell['proceeds'] - buy['cost']
                    trades_with_pnl.append({
                        'buy_date': buy['date'],
                        'sell_date': sell['date'],
                        'pnl': pnl,
                        'return_pct': pnl / buy['cost'] if buy['cost'] > 0 else 0
                    })
        
        if trades_with_pnl:
            pnl_df = pd.DataFrame(trades_with_pnl)
            winning_trades = pnl_df[pnl_df['pnl'] > 0]
            losing_trades = pnl_df[pnl_df['pnl'] <= 0]
            
            win_rate = len(winning_trades) / len(pnl_df) if len(pnl_df) > 0 else 0
            avg_win = winning_trades['pnl'].mean() if not winning_trades.empty else 0
            avg_loss = losing_trades['pnl'].mean() if not losing_trades.empty else 0
            
            total_profit = winning_trades['pnl'].sum() if not winning_trades.empty else 0
            total_loss = abs(losing_trades['pnl'].sum()) if not losing_trades.empty else 0
            profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        else:
            win_rate = avg_win = avg_loss = profit_factor = 0
            winning_trades = losing_trades = pd.DataFrame()
    else:
        win_rate = avg_win = avg_loss = profit_factor = 0
        winning_trades = losing_trades = pd.DataFrame()
    
    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "max_drawdown": float(max_drawdown),
        "sharpe_ratio": float(sharpe_ratio),
        "win_rate": float(win_rate),
        "total_trades": len(trades_with_pnl) if 'trades_with_pnl' in locals() and trades_with_pnl else 0,
        "winning_trades": len(winning_trades) if 'winning_trades' in locals() and not winning_trades.empty else 0,
        "losing_trades": len(losing_trades) if 'losing_trades' in locals() and not losing_trades.empty else 0,
        "avg_win": float(avg_win),
        "avg_loss": float(avg_loss),
        "profit_factor": float(profit_factor) if profit_factor != float('inf') else 0.0
    }