from langchain_core.tools import tool
import os
import requests
import time
from pathlib import Path
from urllib.parse import urlparse
import mimetypes

@tool
def download_image(url, save_path=None, timeout=10, retry_times=2, headers=None):
    """
    从URL下载图片到本地
    
    Args:
        url: 图片URL
        save_path: 保存路径，如果为None则保存到临时目录
        timeout: 下载超时时间（秒）
        retry_times: 重试次数
        headers: 自定义请求头，用于绕过访问限制
    
    Returns:
        包含操作结果的字典
    """
    try:
        # 设置默认请求头，模拟浏览器访问
        if headers is None:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/'
            }
        
        # 如果未指定保存路径，使用临时目录
        if save_path is None:
            temp_dir = Path(os.environ.get('TEMP', '.'))
            # 从URL提取文件名
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            if not filename or '.' not in filename:
                filename = f"image_{int(time.time())}.jpg"
            save_path = str(temp_dir / filename)
        
        # 确保目录存在
        save_dir = os.path.dirname(save_path)
        if save_dir and not os.path.exists(save_dir):
            os.makedirs(save_dir, exist_ok=True)
        
        # 重试机制
        last_error = None
        for attempt in range(retry_times + 1):
            try:
                response = requests.get(url, headers=headers, timeout=timeout, stream=True)
                
                # 检查响应状态
                if response.status_code == 200:
                    # 检查Content-Type是否为图片
                    content_type = response.headers.get('Content-Type', '')
                    if not content_type.startswith('image/'):
                        # 尝试从URL扩展名判断
                        ext = os.path.splitext(save_path)[1].lower()
                        if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                            # 如果扩展名是图片格式，继续下载
                            pass
                        else:
                            # 尝试从Content-Type推断扩展名
                            if 'jpeg' in content_type or 'jpg' in content_type:
                                save_path = save_path.rsplit('.', 1)[0] + '.jpg'
                            elif 'png' in content_type:
                                save_path = save_path.rsplit('.', 1)[0] + '.png'
                            elif 'gif' in content_type:
                                save_path = save_path.rsplit('.', 1)[0] + '.gif'
                            elif 'webp' in content_type:
                                save_path = save_path.rsplit('.', 1)[0] + '.webp'
                            else:
                                # 默认使用.jpg
                                save_path = save_path.rsplit('.', 1)[0] + '.jpg'
                    
                    # 下载图片
                    with open(save_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                    
                    # 验证文件大小
                    file_size = os.path.getsize(save_path)
                    if file_size == 0:
                        os.remove(save_path)
                        raise ValueError("下载的文件大小为0")
                    
                    return {
                        "success": True,
                        "message": "图片下载成功",
                        "file_path": save_path,
                        "file_size": file_size,
                        "content_type": content_type,
                        "url": url,
                        "attempts": attempt + 1
                    }
                    
                elif response.status_code == 403:
                    # 尝试使用不同的Referer
                    if attempt < retry_times:
                        headers['Referer'] = 'https://www.bing.com/'
                        time.sleep(1)
                        continue
                    else:
                        return {
                            "success": False,
                            "message": f"访问被拒绝 (403)，URL: {url}",
                            "error": "403 Forbidden",
                            "url": url
                        }
                        
                elif response.status_code == 404:
                    return {
                        "success": False,
                        "message": f"图片不存在 (404)，URL: {url}",
                        "error": "404 Not Found",
                        "url": url
                    }
                    
                else:
                    if attempt < retry_times:
                        time.sleep(1)
                        continue
                    else:
                        return {
                            "success": False,
                            "message": f"HTTP错误 {response.status_code}，URL: {url}",
                            "error": f"HTTP {response.status_code}",
                            "url": url
                        }
                        
            except requests.exceptions.Timeout as e:
                last_error = str(e)
                if attempt < retry_times:
                    time.sleep(2)
                    continue
                else:
                    return {
                        "success": False,
                        "message": f"下载超时，URL: {url}",
                        "error": last_error,
                        "url": url
                    }
                    
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                if attempt < retry_times:
                    time.sleep(1)
                    continue
                else:
                    return {
                        "success": False,
                        "message": f"网络请求失败，URL: {url}",
                        "error": last_error,
                        "url": url
                    }
                    
            except Exception as e:
                last_error = str(e)
                if attempt < retry_times:
                    time.sleep(1)
                    continue
                else:
                    return {
                        "success": False,
                        "message": f"下载失败，URL: {url}",
                        "error": last_error,
                        "url": url
                    }
        
        return {
            "success": False,
            "message": f"下载失败，重试{retry_times}次后仍然失败，URL: {url}",
            "error": last_error,
            "url": url
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"下载过程中发生异常，URL: {url}",
            "error": str(e),
            "url": url
        }