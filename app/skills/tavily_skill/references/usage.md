# Tavily Search Skill 使用说明

## 功能概述

Tavily 搜索技能提供基于 Tavily API 的智能网页搜索功能，专为 AI Agent 优化，支持通用搜索、直接问答和新闻搜索。

## 工具列表

### 搜索功能
- `tavily_search`: 智能搜索，返回格式化的搜索结果
- `tavily_answer`: 直接问答，获取 AI 生成的答案
- `tavily_news_search`: 新闻搜索，获取最新资讯

## 使用示例

### 智能搜索
```python
tavily_search(
    query="Python 异步编程最佳实践",
    search_depth="advanced",
    max_results=5,
    include_answer=True
)
```

### 直接问答
```python
tavily_answer(
    query="什么是量子计算",
    search_depth="advanced"
)
```

### 新闻搜索
```python
tavily_news_search(
    query="人工智能最新进展",
    days=7,
    max_results=5
)
```

## 参数说明

### tavily_search 参数
- `query`: 搜索查询（必需）
- `search_depth`: "basic"（快速）或 "advanced"（深入），默认 "basic"
- `topic`: "general"（通用）或 "news"（新闻），默认 "general"
- `days`: 搜索最近 N 天的内容（仅 news 有效），默认 3
- `max_results`: 最大返回结果数（1-10），默认 5
- `include_answer`: 是否包含 AI 生成的答案，默认 True
- `include_raw_content`: 是否包含原始内容，默认 False
- `include_domains`: 限定搜索特定域名，默认 None

### tavily_answer 参数
- `query`: 搜索查询（必需）
- `search_depth`: "basic" 或 "advanced"，默认 "basic"

### tavily_news_search 参数
- `query`: 搜索查询（必需）
- `days`: 搜索最近 N 天，默认 7
- `max_results`: 最大结果数，默认 5

## 输出格式

### tavily_search 输出
- 搜索查询
- AI 生成的答案（如果启用）
- 搜索结果列表，每个结果包含：
  - 标题
  - 来源 URL
  - 相关性评分
  - 内容摘要

### tavily_answer 输出
- AI 生成的直接答案

### tavily_news_search 输出
- 搜索查询
- AI 生成的摘要（如果有）
- 新闻列表，每条新闻包含：
  - 标题
  - 来源 URL
  - 内容摘要

## 配置要求

在使用此技能前，需要配置环境变量：
```bash
TAVILY_API_KEY=your_api_key_here
```

获取 API Key：
1. 访问 https://tavily.com/
2. 注册账号
3. 在控制台获取 API Key

## 使用建议

1. **快速搜索**：使用 `search_depth="basic"` 获取快速结果
2. **深度搜索**：使用 `search_depth="advanced"` 获取更全面的结果
3. **获取答案**：使用 `tavily_answer` 快速获取 AI 生成的答案
4. **新闻资讯**：使用 `tavily_news_search` 获取最新新闻
5. **限定范围**：使用 `include_domains` 参数限定搜索特定网站
6. **控制结果**：调整 `max_results` 参数控制返回结果数量

## 注意事项

1. 需要有效的 TAVILY_API_KEY 环境变量
2. 搜索结果可能因网络状况而延迟
3. 新闻搜索的 days 参数仅对 topic="news" 有效
4. 建议根据实际需求调整 search_depth 和 max_results 参数