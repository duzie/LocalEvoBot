from langchain_core.tools import tool
import json
import requests
from typing import Dict, Any, Optional

@tool
def send_http_request(
    method: str = "GET",
    url: str = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    发送HTTP请求
    
    Args:
        method: HTTP方法：GET、POST、PUT、DELETE等
        url: 请求URL
        headers: 请求头
        data: 请求数据（JSON）
        params: URL参数
        
    Returns:
        包含响应信息的字典
    """
    try:
        if not url:
            return {"success": False, "error": "URL不能为空"}
        
        # 设置默认headers
        if headers is None:
            headers = {}
        
        # 如果data存在且不是字符串，转换为JSON
        json_data = None
        if data is not None:
            if not isinstance(data, str):
                json_data = json.dumps(data)
                if "Content-Type" not in headers:
                    headers["Content-Type"] = "application/json"
            else:
                json_data = data
        
        # 发送请求
        response = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=json_data,
            params=params,
            timeout=30
        )
        
        # 尝试解析JSON响应
        try:
            response_data = response.json()
        except:
            response_data = response.text
        
        result = {
            "success": True,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "data": response_data,
            "url": response.url
        }
        
        # 如果状态码不是2xx，添加错误信息
        if not 200 <= response.status_code < 300:
            result["success"] = False
            result["error"] = f"HTTP {response.status_code}"
        
        return result
        
    except requests.exceptions.Timeout:
        return {"success": False, "error": "请求超时"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "连接错误"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"请求异常: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {str(e)}"}