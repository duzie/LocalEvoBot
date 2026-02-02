from langchain_core.tools import tool
import requests
import time
from urllib.parse import urlparse

@tool
def validate_image_url(url, check_content_type=True):
    """
    验证图片URL是否可访问
    
    Args:
        url: 图片URL
        check_content_type: 是否检查Content-Type
    
    Returns:
        包含验证结果的字典
    """
    try:
        # 基本URL验证
        parsed_url = urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            return {
                "valid": False,
                "message": "URL格式无效",
                "url": url,
                "error": "缺少协议或域名"
            }
        
        # 设置请求头
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
        }
        
        start_time = time.time()
        
        try:
            # 发送HEAD请求（更快，不下载内容）
            response = requests.head(url, headers=headers, timeout=5, allow_redirects=True)
            elapsed_time = time.time() - start_time
            
            # 检查状态码
            if response.status_code == 200:
                # 检查Content-Type
                content_type = response.headers.get('Content-Type', '')
                content_length = response.headers.get('Content-Length')
                
                is_image = False
                image_type = None
                
                if check_content_type:
                    if content_type.startswith('image/'):
                        is_image = True
                        image_type = content_type.split('/')[-1].split(';')[0]
                    else:
                        # 检查常见图片扩展名
                        path_lower = parsed_url.path.lower()
                        if any(path_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']):
                            is_image = True
                            image_type = path_lower.split('.')[-1]
                
                result = {
                    "valid": True,
                    "message": "URL可访问",
                    "url": url,
                    "status_code": response.status_code,
                    "content_type": content_type,
                    "content_length": content_length,
                    "is_image": is_image,
                    "image_type": image_type,
                    "response_time": round(elapsed_time, 3),
                    "final_url": response.url  # 处理重定向后的最终URL
                }
                
                if not is_image and check_content_type:
                    result["warning"] = "URL可能不是图片文件"
                    
                return result
                
            elif response.status_code == 403:
                return {
                    "valid": False,
                    "message": "访问被拒绝 (403)",
                    "url": url,
                    "status_code": 403,
                    "error": "403 Forbidden",
                    "response_time": round(elapsed_time, 3)
                }
                
            elif response.status_code == 404:
                return {
                    "valid": False,
                    "message": "资源不存在 (404)",
                    "url": url,
                    "status_code": 404,
                    "error": "404 Not Found",
                    "response_time": round(elapsed_time, 3)
                }
                
            else:
                return {
                    "valid": False,
                    "message": f"HTTP错误 {response.status_code}",
                    "url": url,
                    "status_code": response.status_code,
                    "error": f"HTTP {response.status_code}",
                    "response_time": round(elapsed_time, 3)
                }
                
        except requests.exceptions.Timeout:
            return {
                "valid": False,
                "message": "请求超时",
                "url": url,
                "error": "Timeout",
                "response_time": 5.0
            }
            
        except requests.exceptions.ConnectionError:
            return {
                "valid": False,
                "message": "连接失败",
                "url": url,
                "error": "ConnectionError"
            }
            
        except requests.exceptions.TooManyRedirects:
            return {
                "valid": False,
                "message": "重定向过多",
                "url": url,
                "error": "TooManyRedirects"
            }
            
        except requests.exceptions.RequestException as e:
            return {
                "valid": False,
                "message": f"请求异常: {str(e)}",
                "url": url,
                "error": str(e)
            }
            
    except Exception as e:
        return {
            "valid": False,
            "message": f"验证过程中发生异常",
            "url": url,
            "error": str(e)
        }