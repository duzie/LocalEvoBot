from langchain_core.tools import tool
import re
from typing import Dict, Any, List, Optional

@tool
def extract_api_endpoints(code_content: str, file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    从代码中提取API接口端点
    
    Args:
        code_content: 代码内容
        file_type: 文件类型
        
    Returns:
        包含API端点信息的字典
    """
    try:
        endpoints = []
        
        # 根据文件类型使用不同的提取策略
        if file_type in ['cs', 'ashx']:
            # C#和ASHX文件中的API端点
            patterns = [
                # ErrorCodeHandler.ashx模式
                r'ErrorCodeHandler\.ashx\?methodName=([\w]+)',
                r'["\']ErrorCodeHandler\.ashx\?methodName=([\w]+)["\']',
                r'["\']ErrorCodeHandler\.ashx[^"\']*["\']',
                
                # 通用ASHX模式
                r'\.ashx\?(?:methodName|action)=([\w]+)',
                r'["\'][^"\']*\.ashx\?[^"\']*["\']',
                
                # WebMethod特性
                r'\[WebMethod\][^\n]*\n[^\n]*\s+(\w+)\s*\(',
                
                # AJAX调用中的URL
                r'url\s*[:=]\s*["\']([^"\']+\.ashx[^"\']*)["\']',
                r'["\'](ErrorCodeHandler\.ashx[^"\']*)["\']'
            ]
        
        elif file_type in ['aspx', 'html']:
            # ASPX和HTML文件中的API端点
            patterns = [
                r'ErrorCodeHandler\.ashx\?methodName=([\w]+)',
                r'src=["\'][^"\']*\.ashx[^"\']*["\']',
                r'href=["\'][^"\']*\.ashx[^"\']*["\']',
                r'action=["\'][^"\']*\.ashx[^"\']*["\']',
                r'["\']ErrorCodeHandler\.ashx[^"\']*["\']'
            ]
        
        elif file_type == 'js':
            # JavaScript文件中的API端点
            patterns = [
                r'ErrorCodeHandler\.ashx\?methodName=([\w]+)',
                r'["\']ErrorCodeHandler\.ashx[^"\']*["\']',
                r'url\s*[:=]\s*["\']([^"\']+\.ashx[^"\']*)["\']',
                r'\$\.(?:ajax|get|post|getJSON)\s*\(\s*{[^}]*url\s*:\s*["\']([^"\']+\.ashx[^"\']*)["\']',
                r'fetch\s*\(\s*["\']([^"\']+\.ashx[^"\']*)["\']'
            ]
        
        else:
            # 通用模式
            patterns = [
                r'ErrorCodeHandler\.ashx\?methodName=([\w]+)',
                r'["\']ErrorCodeHandler\.ashx[^"\']*["\']',
                r'\.ashx\?[^"\']*',
                r'url\s*[:=]\s*["\'][^"\']*\.ashx[^"\']*["\']'
            ]
        
        # 应用所有模式
        all_endpoints = []
        for pattern in patterns:
            matches = re.findall(pattern, code_content, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # 如果匹配结果是元组，取第一个非空元素
                    for item in match:
                        if item:
                            all_endpoints.append(item.strip())
                            break
                elif match:
                    all_endpoints.append(match.strip())
        
        # 清理和规范化端点
        cleaned_endpoints = []
        for endpoint in all_endpoints:
            # 移除引号
            endpoint = endpoint.strip('"\'')
            
            # 如果是完整的URL，提取方法名
            if 'ErrorCodeHandler.ashx?methodName=' in endpoint:
                method_match = re.search(r'methodName=([\w]+)', endpoint)
                if method_match:
                    cleaned_endpoints.append(method_match.group(1))
                else:
                    cleaned_endpoints.append(endpoint)
            elif '.ashx?' in endpoint:
                # 提取方法名或整个端点
                method_match = re.search(r'\?([^&]+)', endpoint)
                if method_match:
                    param = method_match.group(1)
                    if '=' in param:
                        key, value = param.split('=', 1)
                        if key.lower() in ['methodname', 'action']:
                            cleaned_endpoints.append(value)
                        else:
                            cleaned_endpoints.append(endpoint)
                    else:
                        cleaned_endpoints.append(endpoint)
                else:
                    cleaned_endpoints.append(endpoint)
            else:
                cleaned_endpoints.append(endpoint)
        
        # 去重和排序
        endpoints = sorted(list(set(cleaned_endpoints)))
        
        # 分类端点
        categorized = {
            "errorcodehandler_methods": [],
            "ashx_endpoints": [],
            "other_endpoints": []
        }
        
        for endpoint in endpoints:
            if endpoint.startswith('ErrorCodeHandler.ashx'):
                categorized["errorcodehandler_methods"].append(endpoint)
            elif '.ashx' in endpoint:
                categorized["ashx_endpoints"].append(endpoint)
            else:
                categorized["other_endpoints"].append(endpoint)
        
        result = {
            "success": True,
            "total_endpoints": len(endpoints),
            "endpoints": endpoints,
            "categorized": categorized,
            "file_type": file_type
        }
        
        # 特别关注RelDishOrTypeToDeptAccountingCenter
        if any('RelDishOrTypeToDeptAccountingCenter' in ep for ep in endpoints):
            result["has_target_method"] = True
            result["target_method"] = "RelDishOrTypeToDeptAccountingCenter"
        else:
            result["has_target_method"] = False
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "code_length": len(code_content)}