# GNews技能使用指南

## 📋 概述

GNews技能是一个基于GNews API的新闻获取工具，支持获取头条新闻、搜索新闻和保存新闻数据到文件。

## 🔧 安装与配置

### 1. 获取API Key
1. 访问 https://gnews.io/
2. 注册账号并登录
3. 在Dashboard中获取您的API Key

### 2. 配置环境变量
创建 `.env` 文件（参考 `.env.example`）：
```bash
GNEWS_API_KEY=your_actual_api_key_here
```

### 3. 验证配置
运行测试脚本：
```bash
python test_gnews_skill.py
```

## 🛠️ 可用工具

### 1. `get_gnews_headlines` - 获取头条新闻
**参数：**
- `country` (str): 国家代码，默认 'us'
- `category` (str): 新闻类别，默认 'general'
  - 可选值: general, business, technology, sports, health, science, entertainment
- `max_results` (int): 最大返回结果数，默认 10
- `language` (str): 语言代码，默认 'en'

**示例：**
```python
# 获取美国科技新闻
result = get_gnews_headlines(
    country="us",
    category="technology",
    max_results=5,
    language="en"
)
```

### 2. `search_gnews` - 搜索新闻
**参数：**
- `query` (str): 搜索关键词（必需）
- `language` (str): 语言代码，默认 'en'
- `country` (str): 国家代码，默认 'us'
- `max_results` (int): 最大返回结果数，默认 10
- `from_date` (str): 开始日期，格式 YYYY-MM-DD
- `to_date` (str): 结束日期，格式 YYYY-MM-DD
- `sort_by` (str): 排序方式，默认 'relevance'
  - 可选值: relevance, publishedAt

**示例：**
```python
# 搜索人工智能相关新闻
result = search_gnews(
    query="artificial intelligence",
    language="en",
    max_results=10,
    from_date="2024-01-01",
    sort_by="publishedAt"
)
```

### 3. `save_news_to_file` - 保存新闻数据
**参数：**
- `news_data` (dict): 新闻数据（从上述工具获取）
- `file_path` (str): 文件保存路径
- `format` (str): 保存格式，默认 'json'
  - 可选值: json, txt

**示例：**
```python
# 保存为JSON格式
save_news_to_file(
    news_data=result,
    file_path="news_data.json",
    format="json"
)

# 保存为文本格式
save_news_to_file(
    news_data=result,
    file_path="news_summary.txt",
    format="txt"
)
```

## 📊 数据格式

### 成功响应格式：
```json
{
  "success": true,
  "total_articles": 10,
  "articles": [
    {
      "title": "新闻标题",
      "description": "新闻描述",
      "content": "新闻内容",
      "url": "新闻链接",
      "image": "图片链接",
      "published_at": "发布时间",
      "source": {
        "name": "来源名称",
        "url": "来源链接"
      }
    }
  ],
  "request_info": {
    "country": "us",
    "category": "technology",
    "max_results": 10,
    "language": "en"
  }
}
```

### 错误响应格式：
```json
{
  "success": false,
  "error": "错误描述",
  "suggestion": "解决建议"
}
```

## 🌍 支持的国家和语言

### 国家代码：
- `us` - 美国
- `gb` - 英国
- `cn` - 中国
- `jp` - 日本
- `in` - 印度
- `au` - 澳大利亚
- `ca` - 加拿大
- 更多国家请参考GNews文档

### 语言代码：
- `en` - 英语
- `zh` - 中文
- `ja` - 日语
- `ko` - 韩语
- `fr` - 法语
- `de` - 德语
- `es` - 西班牙语
- 更多语言请参考GNews文档

## 🔍 使用示例

### 示例1：获取中文科技新闻
```python
result = get_gnews_headlines(
    country="cn",
    category="technology",
    language="zh",
    max_results=5
)
```

### 示例2：搜索特定日期范围的新闻
```python
result = search_gnews(
    query="bitcoin",
    from_date="2024-01-01",
    to_date="2024-01-31",
    sort_by="publishedAt",
    max_results=20
)
```

### 示例3：完整工作流程
```python
# 1. 搜索新闻
search_result = search_gnews(
    query="climate change",
    language="en",
    max_results=10
)

# 2. 检查结果
if search_result.get("success"):
    # 3. 保存为JSON
    save_news_to_file(
        news_data=search_result,
        file_path="climate_news.json",
        format="json"
    )
    
    # 4. 保存为文本摘要
    save_news_to_file(
        news_data=search_result,
        file_path="climate_news_summary.txt",
        format="txt"
    )
```

## ⚠️ 注意事项

1. **API限制**：GNews API有调用频率限制，请参考官方文档
2. **环境变量**：确保 `.env` 文件在项目根目录
3. **错误处理**：所有工具都包含完善的错误处理
4. **网络连接**：需要稳定的网络连接访问API
5. **数据格式**：API响应格式可能变更，请关注官方更新

## 🔗 相关链接

- [GNews官方网站](https://gnews.io/)
- [GNews API文档](https://docs.gnews.io/)
- [API Key获取](https://gnews.io/account)
- [国家代码列表](https://gnews.io/docs/v4#countries)
- [语言代码列表](https://gnews.io/docs/v4#languages)

## 🚀 高级用法

### 批量处理新闻
```python
# 获取多个类别的新闻
categories = ["technology", "business", "science"]
all_news = []

for category in categories:
    result = get_gnews_headlines(
        category=category,
        max_results=3
    )
    if result.get("success"):
        all_news.extend(result.get("articles", []))

print(f"总共获取了 {len(all_news)} 条新闻")
```

### 定时获取新闻
```python
import schedule
import time

def daily_news_update():
    result = get_gnews_headlines(
        category="general",
        max_results=5
    )
    if result.get("success"):
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_news_to_file(
            news_data=result,
            file_path=f"news_daily_{timestamp}.json"
        )

# 每天9点执行
schedule.every().day.at("09:00").do(daily_news_update)

while True:
    schedule.run_pending()
    time.sleep(60)
```

---

**📞 技术支持**
如有问题，请参考：
1. 检查API Key是否正确
2. 检查网络连接
3. 查看错误信息中的建议
4. 参考GNews官方文档