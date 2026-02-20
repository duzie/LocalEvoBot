from langchain_core.tools import tool
import os
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import json
from datetime import datetime
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
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
def get_gnews_headlines(
    country: Optional[str] = None,
    category: str = "general",
    max_results: int = 10,
    language: Optional[str] = None
) -> Dict[str, Any]:
    """
    获取GNews头条新闻
    
    Args:
        country: 国家代码，例如 'us', 'cn', 'jp'，默认为环境变量GNEWS_DEFAULT_COUNTRY或'us'
        category: 新闻类别，例如 'general', 'business', 'technology', 'sports', 'health', 'science', 'entertainment'
        max_results: 最大返回结果数，默认为环境变量GNEWS_DEFAULT_MAX_RESULTS或10
        language: 语言代码，例如 'en', 'zh', 'ja'，默认为环境变量GNEWS_DEFAULT_LANGUAGE或'en'
    
    Returns:
        包含新闻数据的字典
    """
    
    tool_name = "get_gnews_headlines"
    # 每次调用都重新加载环境变量，确保获取最新值
    load_dotenv(override=True)
    
    # 从环境变量获取API Key
    api_key = os.getenv("GNEWS_API_KEY")
    if not api_key:
        return _error_payload("missing_api_key", "GNEWS_API_KEY环境变量未设置", tool=tool_name)
    
    # 从环境变量获取默认值
    default_country = os.getenv("GNEWS_DEFAULT_COUNTRY", "us")
    default_language = os.getenv("GNEWS_DEFAULT_LANGUAGE", "en")
    default_max_results = int(os.getenv("GNEWS_DEFAULT_MAX_RESULTS", "10"))
    
    # 使用参数值或环境变量默认值
    country = country if country is not None else default_country
    language = language if language is not None else default_language
    max_results = max_results if max_results != 10 else default_max_results
    
    # 构建API URL
    base_url = "https://gnews.io/api/v4/top-headlines"
    
    # 准备请求参数
    params = {
        "token": api_key,
        "country": country,
        "category": category,
        "max": max_results,
        "lang": language
    }
    
    try:
        # 发送请求
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        
        # 检查API返回的错误
        if "errors" in data:
            return _error_payload("api_error", f"API返回错误: {data['errors']}", tool=tool_name, data=data)
        
        if "articles" not in data:
            return _error_payload("no_articles", "No articles found", tool=tool_name, data=data)

        # 敏感词过滤列表 (针对国内LLM风控)
        SENSITIVE_KEYWORDS = ['黎智英', '法轮功', '六四', '天安门事件', '达赖喇嘛']

        # 格式化返回数据
        result = _ok_payload(
            "获取头条完成",
            total_articles=data.get("totalArticles", 0),
            articles=[]
        )

        # 提取文章信息
        for article in data.get("articles", []):
            title = article.get("title", "")
            description = article.get("description", "")
            
            # 检查敏感词
            is_sensitive = False
            for keyword in SENSITIVE_KEYWORDS:
                if keyword in title or (description and keyword in description):
                    is_sensitive = True
                    break
            
            if is_sensitive:
                continue

            # 为了防止国内LLM触发"Content Exists Risk"风控，移除content字段，并截断description
            if description and len(description) > 200:
                description = description[:197] + "..."

            article_info = {
                "title": title,
                "description": description,
                # "content": article.get("content", ""), # 移除content以降低风控风险
                "url": article.get("url", ""),
                "image": article.get("image", ""),
                "published_at": article.get("publishedAt", ""),
                "source": {
                    "name": article.get("source", {}).get("name", ""),
                    "url": article.get("source", {}).get("url", "")
                }
            }
            result["articles"].append(article_info)
        
        # 添加详细的请求信息用于调试
        result["request_info"] = {
            "country": country,
            "category": category,
            "max_results": max_results,
            "language": language,
            "source": "environment_variables" if country == default_country and language == default_language else "explicit_parameters",
            "env_default_country": default_country,
            "env_default_language": default_language,
            "env_default_max_results": default_max_results,
            "input_country": "None" if country is None else country,
            "input_language": "None" if language is None else language,
            "used_default_country": country == default_country,
            "used_default_language": language == default_language
        }
        
        _emit_event(tool_name, "headlines", total=len(result.get("articles") or []))
        return result
        
    except requests.exceptions.RequestException as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("request_failed", f"请求失败: {str(e)}", tool=tool_name)
    except ValueError as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("json_parse_failed", f"JSON解析失败: {str(e)}", tool=tool_name)
    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("unknown_error", f"未知错误: {str(e)}", tool=tool_name)
