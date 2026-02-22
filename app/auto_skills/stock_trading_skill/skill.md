# Skill

## Name
stock_trading_skill

## Version
1.1.0  # 更新版本号

## Description
股票交易技能，包含技术分析、策略回测和交易执行功能（已修复回测工具，使用 collect_stock_data 替代 get_stock_data）

## Entry
app.auto_skills.stock_trading_skill.scripts

## Tools
- calculate_technical_indicators
- backtest_strategy
- get_market_status
- analyze_stock_fundamentals
- generate_trading_signals

## Platforms
- Windows

## References
- references/usage.md

## 更新说明
- 删除 get_stock_data 工具（不可用）
- 修复 backtest_strategy 工具，使用 collect_stock_data 获取数据
- 版本升级到 1.1.0