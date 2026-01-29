from langchain_core.tools import tool
import os
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

@tool
def search_gnews(
    query: str,
    language: Optional[str] = None,
    country: Optional[str] = None,
    max_results: int = 10,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    sort_by: str = "relevance"
) -> Dict[str, Any]:
    """
    搜索GNews新闻
    
    Args:
        query: 搜索关键词
        language: 语言代码，例如 'en', 'zh', 'ja'，默认为环境变量GNEWS_DEFAULT_LANGUAGE或'en'
        country: 国家代码，例如 'us', 'cn', 'jp'，默认为环境变量GNEWS_DEFAULT_COUNTRY或'us'
        max_results: 最大返回结果数，默认为环境变量GNEWS_DEFAULT_MAX_RESULTS或10
        from_date: 开始日期，格式为YYYY-MM-DD
        to_date: 结束日期，格式为YYYY-MM-DD
        sort_by: 排序方式：'relevance'（相关度）或 'publishedAt'（发布时间），默认为 'relevance'
    
    Returns:
        包含搜索结果的字典
    """
    
    # 每次调用都重新加载环境变量，确保获取最新值
    load_dotenv(override=True)
    
    # 从环境变量获取API Key
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "GNEWS_API_KEY环境变量未设置",
            "suggestion": "请设置环境变量GNEWS_API_KEY，或直接在代码中提供API Key"
        }
    
    # 从环境变量获取默认值
    default_country = os.getenv("GNEWS_DEFAULT_COUNTRY", "us")
    default_language = os.getenv("GNEWS_DEFAULT_LANGUAGE", "en")
    default_max_results = int(os.getenv("GNEWS_DEFAULT_MAX_RESULTS", "10"))
    
    # 使用参数值或环境变量默认值
    country = country if country is not None else default_country
    language = language if language is not None else default_language
    max_results = max_results if max_results != 10 else default_max_results
    
    # 构建API URL
    base_url = "https://gnews.io/api/v4/search"
    
    # 准备请求参数
    params = {
        "token": api_key,
        "q": query,
        "lang": language,
        "country": country,
        "max": max_results,
        "sortby": sort_by
    }
    
    # 添加日期范围参数
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date
    
    try:
        # 发送请求
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        
        # 检查API返回的错误
        if "errors" in data:
            return {
                "success": False,
                "error": f"API返回错误: {data['errors']}",
                "data": data
            }
        
        # 格式化返回数据
        result = {
            "success": True,
            "query": query,
            "total_articles": data.get("totalArticles", 0),
            "articles": []
        }
        
        # 提取文章信息
        for article in data.get("articles", []):
            article_info = {
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "content": article.get("content", ""),
                "url": article.get("url", ""),
                "image": article.get("image", ""),
                "published_at": article.get("publishedAt", ""),
                "source": {
                    "name": article.get("source", {}).get("name", ""),
                    "url": article.get("source", {}).get("url", "")
                }
            }
            result["articles"].append(article_info)
        
        # 添加请求信息
        result["request_info"] = {
            "query": query,
            "language": language,
            "country": country,
            "max_results": max_results,
            "from_date": from_date,
            "to_date": to_date,
            "sort_by": sort_by,
            "source": "environment_variables" if country == default_country and language == default_language else "explicit_parameters",
            "env_default_country": default_country,
            "env_default_language": default_language
        }
        
        return result
        
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": f"请求失败: {str(e)}",
            "suggestion": "请检查网络连接或API Key是否正确"
        }
    except ValueError as e:
        return {
            "success": False,
            "error": f"JSON解析失败: {str(e)}",
            "suggestion": "API响应格式可能已更改"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"未知错误: {str(e)}",
            "suggestion": "请检查代码逻辑"
        }