# Skill

## Name
stock_unified_skill

## Version
1.0.0

## Description
统一股票数据技能，使用腾讯财经API获取实时和历史数据，支持缓存功能。基于股票摸鱼小软件项目的API实现。

## Features
- **实时行情获取**：使用腾讯财经API获取实时股票数据
- **历史数据获取**：使用腾讯财经API获取历史K线数据
- **股票搜索**：使用新浪财经API搜索股票代码和名称
- **智能缓存**：支持历史数据缓存，减少API调用
- **缓存管理**：提供缓存清理和信息查看功能

## Entry
app.auto_skills.stock_unified_skill.scripts

## Tools

### 1. get_stock_realtime
获取股票实时行情数据（腾讯财经API）

**参数：**
- `symbol`: 股票代码，如"000001"、"600519"
- `use_cache`: 是否使用缓存（5秒内有效），默认True
- `fallback_source`: 备用数据源："sina"（新浪财经），默认"sina"

**返回数据：**
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

### 2. get_stock_history
获取股票历史数据（腾讯财经API），支持缓存

**参数：**
- `symbol`: 股票代码
- `period`: 数据周期："day"（日线）、"week"（周线）、"month"（月线），默认"day"
- `start_date`: 开始日期，格式"YYYY-MM-DD"，默认"2023-01-01"
- `end_date`: 结束日期，格式"YYYY-MM-DD"，默认今天
- `cache_dir`: 缓存目录路径，默认"app/data/stock_cache"
- `cache_days`: 缓存有效期（天），默认7
- `force_refresh`: 是否强制刷新缓存，默认False

**缓存策略：**
1. 先检查缓存文件是否存在且未过期
2. 检查缓存数据的时间范围是否满足需求
3. 如果不满足，调用API获取并与缓存合并后覆盖缓存

### 3. search_stock
搜索股票代码和名称（新浪财经API）

**参数：**
- `name`: 股票名称或拼音缩写，如"平安银行"、"PAYH"、"pinganyinhang"
- `max_results`: 最大返回结果数，默认10

**返回数据：**
- query: 搜索关键词
- count: 结果数量
- results: 搜索结果列表
  - symbol: 股票代码
  - name: 股票名称
  - pinyin: 拼音缩写
  - full_pinyin: 完整拼音
  - market: 市场（sh/sz/bj）
  - display: 显示文本

### 4. clear_stock_cache
清理股票缓存文件

**参数：**
- `symbol`: 股票代码，为空则清理所有缓存
- `cache_dir`: 缓存目录路径，默认"app/data/stock_cache"
- `max_age_days`: 最大缓存天数，默认30

**清理条件：**
1. 文件修改时间超过指定天数
2. 缓存元数据中的过期时间已过
3. JSON文件损坏无法读取

### 5. get_stock_cache_info
获取股票缓存信息

**参数：**
- `cache_dir`: 缓存目录路径，默认"app/data/stock_cache"

**返回信息：**
- 缓存文件列表及详细信息
- 文件大小统计
- 数据时间范围
- 缓存过期状态
- 按股票代码分组统计

## Data Sources

### 主要数据源
- **腾讯财经API**：实时行情和历史数据
  - 实时数据：`https://qt.gtimg.cn/q={prefix}{code}`
  - 历史数据：`https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},{period},,,320,qfq`
  - 特点：免费、稳定

### 备用数据源
- **新浪财经API**：股票搜索和备用实时数据
  - 搜索API：`https://suggest3.sinajs.cn/suggest/?name=suggestion&type=111&key={keyword}`
  - 实时数据：`https://hq.sinajs.cn/list={prefix}{code}`
  - 编码：GBK
  - 特点：免费、稳定

## Platforms
- Windows
- Linux
- macOS

## Dependencies
- requests>=2.31.0
- pandas>=2.0.0 (可选，用于数据分析)

## Usage Examples

### 获取实时行情
```python
# 获取平安银行实时行情
data = get_stock_realtime("000001")
print(f"当前价: {data['current']}, 涨跌幅: {data['change_percent']}%")

# 获取贵州茅台实时行情（不使用缓存）
data = get_stock_realtime("600519", use_cache=False)
```

### 获取历史数据
```python
# 获取平安银行2024年日线数据（使用缓存）
history = get_stock_history("000001", start_date="2024-01-01", end_date="2024-12-31")
print(f"获取到 {history['data_count']} 条历史数据")

# 获取贵州茅台周线数据（强制刷新缓存）
history = get_stock_history("600519", period="week", force_refresh=True)
```

### 搜索股票
```python
# 搜索"平安银行"
results = search_stock("平安银行")
for stock in results['results']:
    print(f"{stock['name']} ({stock['symbol']})")

# 搜索拼音缩写
results = search_stock("PAYH")
```

### 管理缓存
```python
# 查看缓存信息
cache_info = get_stock_cache_info()
print(f"缓存文件总数: {cache_info['statistics']['total_files']}")

# 清理过期缓存
clear_result = clear_stock_cache(max_age_days=30)
print(f"清理了 {len(clear_result['cleaned_files'])} 个文件")

# 清理特定股票的缓存
clear_result = clear_stock_cache(symbol="000001")
```

## References
- references/usage.md
