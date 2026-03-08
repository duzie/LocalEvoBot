"""
Tavily 搜索技能 - 增强版

替代旧的 tavily_skill，提供更强大的搜索能力
"""

import os
import json
from typing import List, Dict, Optional
from tavily import TavilyClient
from langchain_core.tools import tool
from web.backend.shared import shared
from datetime import datetime


def _error_payload(code: str, message: str, **fields) -> dict:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: dict = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _ok_payload(message: str = "", **fields) -> dict:
    payload: dict = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload


def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

@tool
def tavily_search(
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    days: int = 3,
    max_results: int = 5,
    include_answer: bool = True,
    include_raw_content: bool = False,
    include_domains: list = None
) -> str:
    """
    Tavily 智能搜索 - 为 AI Agent 优化
    
    Args:
        query: 搜索查询
        search_depth: basic（快速）或 advanced（深入）
        topic: general（通用）或 news（新闻）
        days: 搜索最近 N 天的内容（仅 news 有效）
        max_results: 最大返回结果数（1-10）
        include_answer: 是否包含 AI 生成的答案
        include_raw_content: 是否包含原始内容
        include_domains: 限定搜索特定域名
    
    Returns:
        格式化的搜索结果
    """
    tool_name = "tavily_search"
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _error_payload("missing_api_key", "未配置 TAVILY_API_KEY 环境变量", tool=tool_name)
    
    try:
        client = TavilyClient(api_key=api_key)
        
        response = client.search(
            query=query,
            search_depth=search_depth,
            topic=topic,
            days=days,
            max_results=max_results,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            include_domains=include_domains or []
        )
        
        result = []
        result.append(f"🔍 搜索结果：{query}\n")
        
        if include_answer and response.get("answer"):
            result.append(f"💡 AI 答案：{response['answer']}\n")
        
        result.append(f"## 找到 {len(response.get('results', []))} 个相关结果\n")
        
        for i, r in enumerate(response.get('results', []), 1):
            result.append(f"### {i}. {r.get('title', '无标题')}")
            result.append(f"**来源**: {r.get('url', '无链接')}")
            result.append(f"**相关性**: {r.get('score', 0):.2f}")
            result.append(f"**内容**: {r.get('content', '无摘要')}\n")
        
        message = "\n".join(result)
        _emit_event(tool_name, "search_completed", query=query, results=len(response.get('results', [])))
        return _ok_payload(message, query=query, results=len(response.get('results', [])))
    
    except Exception as e:
        return _error_payload("search_failed", f"搜索失败：{str(e)}", tool=tool_name, query=query)

@tool
def tavily_answer(
    query: str,
    search_depth: str = "basic"
) -> str:
    """
    Tavily 直接回答 - 获取 AI 生成的答案
    
    Args:
        query: 搜索查询
        search_depth: basic 或 advanced
    
    Returns:
        AI 生成的答案
    """
    tool_name = "tavily_answer"
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _error_payload("missing_api_key", "未配置 TAVILY_API_KEY", tool=tool_name)
    
    try:
        client = TavilyClient(api_key=api_key)
        
        response = client.qna_search(
            query=query,
            search_depth=search_depth
        )
        
        message = f"💡 {response.get('answer', '未找到答案')}"
        _emit_event(tool_name, "answer_completed", query=query)
        return _ok_payload(message, query=query)
    
    except Exception as e:
        return _error_payload("answer_failed", f"查询失败：{str(e)}", tool=tool_name, query=query)

@tool
def tavily_news_search(
    query: str,
    days: int = 7,
    max_results: int = 5
) -> str:
    """
    Tavily 新闻搜索
    
    Args:
        query: 搜索查询
        days: 搜索最近 N 天
        max_results: 最大结果数
    
    Returns:
        格式化的新闻搜索结果
    """
    tool_name = "tavily_news_search"
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _error_payload("missing_api_key", "未配置 TAVILY_API_KEY", tool=tool_name)
    
    try:
        client = TavilyClient(api_key=api_key)
        
        response = client.search(
            query=query,
            topic="news",
            days=days,
            max_results=max_results,
            include_answer=True
        )
        
        result = [f"📰 最新新闻：{query}\n"]
        
        if response.get("answer"):
            result.append(f"💡 摘要：{response['answer']}\n")
        
        for i, r in enumerate(response.get('results', []), 1):
            result.append(f"{i}. **{r.get('title')}**")
            result.append(f"   来源：{r.get('url')}")
            result.append(f"   内容：{r.get('content')}\n")
        
        message = "\n".join(result)
        _emit_event(tool_name, "news_search_completed", query=query, results=len(response.get('results', [])))
        return _ok_payload(message, query=query, results=len(response.get('results', [])))
    
    except Exception as e:
        return _error_payload("news_search_failed", f"新闻搜索失败：{str(e)}", tool=tool_name, query=query)
