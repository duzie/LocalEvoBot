from langchain_core.tools import tool
import os
import requests
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv


@tool
def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "basic",
    include_answer: bool = False,
    include_raw_content: bool = False,
    include_images: bool = False,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    topic: Optional[str] = None,
    time_range: Optional[str] = None
) -> Dict[str, Any]:
    """
    使用 Tavily API 搜索网页内容

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数
        search_depth: 搜索深度，basic 或 advanced
        include_answer: 是否返回答案摘要
        include_raw_content: 是否返回原始内容
        include_images: 是否返回图片结果
        include_domains: 仅包含的域名列表
        exclude_domains: 排除的域名列表
        topic: 主题分类
        time_range: 时间范围筛选
    """
    load_dotenv(override=True)
    api_key = os.getenv("TAVILY_API_KEY") or os.getenv("tavily_api_key")
    if not api_key:
        return {
            "success": False,
            "error": "TAVILY_API_KEY 环境变量未设置",
            "suggestion": "请在 .env 中设置 TAVILY_API_KEY 或 tavily_api_key"
        }

    payload: Dict[str, Any] = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": include_answer,
        "include_raw_content": include_raw_content,
        "include_images": include_images
    }
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains
    if topic:
        payload["topic"] = topic
    if time_range:
        payload["time_range"] = time_range

    try:
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return {
            "success": True,
            "query": query,
            "data": data
        }
    except requests.RequestException as e:
        return {
            "success": False,
            "error": f"请求失败: {str(e)}",
            "suggestion": "请检查网络连接或 API Key 是否正确"
        }
    except ValueError as e:
        return {
            "success": False,
            "error": f"JSON 解析失败: {str(e)}"
        }
