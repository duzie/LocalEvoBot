from langchain_core.tools import tool
import json
import os
from typing import Dict, Any
from datetime import datetime

@tool
def save_news_to_file(
    news_data: Dict[str, Any],
    file_path: str,
    format: str = "json"
) -> Dict[str, Any]:
    """
    将新闻数据保存到文件
    
    Args:
        news_data: 新闻数据
        file_path: 文件保存路径
        format: 保存格式：'json' 或 'txt'，默认为 'json'
    
    Returns:
        包含操作结果的字典
    """
    
    try:
        # 确保目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
        
        # 根据格式保存文件
        if format.lower() == "json":
            # 保存为JSON格式
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(news_data, f, ensure_ascii=False, indent=2)
            
            return {
                "success": True,
                "message": f"新闻数据已保存为JSON文件: {file_path}",
                "file_path": file_path,
                "format": "json",
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            
        elif format.lower() == "txt":
            # 保存为文本格式
            with open(file_path, 'w', encoding='utf-8') as f:
                # 写入基本信息
                if "success" in news_data and news_data["success"]:
                    f.write("=== GNews 新闻数据 ===\n\n")
                    
                    # 写入请求信息
                    if "request_info" in news_data:
                        f.write("请求信息:\n")
                        for key, value in news_data["request_info"].items():
                            if value:
                                f.write(f"  {key}: {value}\n")
                        f.write("\n")
                    
                    # 写入统计信息
                    f.write(f"总文章数: {news_data.get('total_articles', 0)}\n")
                    if "query" in news_data:
                        f.write(f"搜索关键词: {news_data['query']}\n")
                    f.write(f"获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    
                    # 写入文章内容
                    if "articles" in news_data and news_data["articles"]:
                        f.write("=== 文章列表 ===\n\n")
                        for i, article in enumerate(news_data["articles"], 1):
                            f.write(f"文章 {i}:\n")
                            f.write(f"标题: {article.get('title', 'N/A')}\n")
                            f.write(f"描述: {article.get('description', 'N/A')}\n")
                            f.write(f"发布时间: {article.get('published_at', 'N/A')}\n")
                            f.write(f"来源: {article.get('source', {}).get('name', 'N/A')}\n")
                            f.write(f"链接: {article.get('url', 'N/A')}\n")
                            
                            # 如果有内容，写入内容
                            content = article.get('content', '')
                            if content and len(content) > 100:
                                f.write(f"内容摘要: {content[:200]}...\n")
                            elif content:
                                f.write(f"内容: {content}\n")
                            
                            f.write("\n" + "-" * 50 + "\n\n")
                    else:
                        f.write("未找到文章\n")
                else:
                    f.write("新闻获取失败\n")
                    if "error" in news_data:
                        f.write(f"错误信息: {news_data['error']}\n")
                    if "suggestion" in news_data:
                        f.write(f"建议: {news_data['suggestion']}\n")
            
            return {
                "success": True,
                "message": f"新闻数据已保存为文本文件: {file_path}",
                "file_path": file_path,
                "format": "txt",
                "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
            }
            
        else:
            return {
                "success": False,
                "error": f"不支持的格式: {format}",
                "suggestion": "请使用 'json' 或 'txt' 格式"
            }
            
    except PermissionError as e:
        return {
            "success": False,
            "error": f"权限错误: {str(e)}",
            "suggestion": "请检查文件路径是否有写入权限"
        }
    except IOError as e:
        return {
            "success": False,
            "error": f"IO错误: {str(e)}",
            "suggestion": "请检查文件路径是否正确"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"保存失败: {str(e)}",
            "suggestion": "请检查数据格式和文件路径"
        }