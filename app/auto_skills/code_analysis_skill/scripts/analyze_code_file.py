from langchain_core.tools import tool
import os
import ast
import re
from typing import Dict, Any, List, Optional, Union

@tool
def analyze_code_file(file_path: str, file_type: Optional[str] = None) -> Dict[str, Any]:
    """
    分析代码文件，提取关键信息（类、方法、API接口等）
    
    Args:
        file_path: 代码文件路径
        file_type: 文件类型：py, cs, aspx, ashx, js等
        
    Returns:
        包含分析结果的字典
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        # 如果未指定文件类型，从扩展名推断
        if file_type is None:
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.py':
                file_type = 'py'
            elif ext == '.cs':
                file_type = 'cs'
            elif ext == '.aspx':
                file_type = 'aspx'
            elif ext == '.ashx':
                file_type = 'ashx'
            elif ext == '.js':
                file_type = 'js'
            elif ext == '.html' or ext == '.htm':
                file_type = 'html'
            else:
                file_type = 'unknown'
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        result = {
            "success": True,
            "file_path": file_path,
            "file_type": file_type,
            "file_name": os.path.basename(file_path),
            "file_size": os.path.getsize(file_path),
            "classes": [],
            "methods": [],
            "api_endpoints": [],
            "imports": [],
            "global_variables": [],
            "comments": [],
            "summary": ""
        }
        
        # 根据文件类型进行不同分析
        if file_type == 'py':
            result.update(_analyze_python_file(content))
        elif file_type == 'cs':
            result.update(_analyze_csharp_file(content))
        elif file_type == 'aspx':
            result.update(_analyze_aspx_file(content))
        elif file_type == 'ashx':
            result.update(_analyze_ashx_file(content))
        elif file_type == 'js':
            result.update(_analyze_javascript_file(content))
        elif file_type == 'html':
            result.update(_analyze_html_file(content))
        
        # 提取API端点
        api_endpoints = _extract_api_endpoints_from_content(content, file_type)
        if api_endpoints:
            # 如果已有api_endpoints (如从Python装饰器提取的)，则合并
            existing_endpoints = set(result.get("api_endpoints", []))
            for ep in api_endpoints:
                if ep not in existing_endpoints:
                    result["api_endpoints"].append(ep)
        
        # 生成摘要
        result["summary"] = _generate_summary(result)
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "file_path": file_path}

def _analyze_python_file(content: str) -> Dict[str, Any]:
    """
    使用 AST 分析 Python 文件
    """
    result = {
        "classes": [],
        "methods": [], # 顶层函数
        "imports": [],
        "global_variables": [],
        "api_endpoints": [] # 特别提取 FastAPI/Flask 路由
    }
    
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return result # 解析失败返回空结果
        
    # 辅助函数：提取函数信息
    def extract_func_info(node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> str:
        args = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                # 简单尝试获取类型注解的源码表示
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except:
                    pass
            args.append(arg_str)
        
        # 处理 kwargs, varargs
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
            
        returns = ""
        if node.returns:
            try:
                returns = f" -> {ast.unparse(node.returns)}"
            except:
                pass
                
        decorators = [f"@{ast.unparse(d)}" for d in node.decorator_list]
        decorator_str = " ".join(decorators) + " " if decorators else ""
        
        return f"{decorator_str}def {node.name}({', '.join(args)}){returns}"

    # 遍历节点
    for node in ast.iter_fields(tree):
        # 处理 Imports
        # ast.iter_fields 返回的是字段名和值的元组，我们需要遍历 tree.body
        pass

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            try:
                result["imports"].append(ast.unparse(node))
            except:
                pass
                
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["methods"].append(extract_func_info(node))
            
            # 尝试提取 API 路由 (FastAPI/Flask)
            for decorator in node.decorator_list:
                try:
                    dec_src = ast.unparse(decorator)
                    # 简单匹配常见的路由模式
                    if any(x in dec_src for x in ['.get', '.post', '.put', '.delete', '.route', 'router.']):
                        result["api_endpoints"].append(f"{dec_src} -> {node.name}")
                except:
                    pass
                    
        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                try:
                    bases.append(ast.unparse(base))
                except:
                    pass
            base_str = f"({', '.join(bases)})" if bases else ""
            
            class_info = f"class {node.name}{base_str}"
            methods = []
            
            # 提取类方法
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    methods.append(extract_func_info(item))
            
            if methods:
                class_info += ":\n    " + "\n    ".join(methods)
                
            result["classes"].append(class_info)
            
        elif isinstance(node, ast.Assign):
            # 提取全局变量赋值
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result["global_variables"].append(target.id)
        elif isinstance(node, ast.AnnAssign):
             if isinstance(node.target, ast.Name):
                result["global_variables"].append(node.target.id)
                
    return result

def _analyze_csharp_file(content: str) -> Dict[str, Any]:
    """分析C#文件"""
    result = {
        "classes": [],
        "methods": [],
        "imports": [],
        "comments": []
    }
    
    # 提取using语句
    using_pattern = r'using\s+([\w\.]+)(?:\s*=\s*[\w\.]+)?\s*;'
    result["imports"] = re.findall(using_pattern, content)
    
    # 提取类定义
    class_pattern = r'(?:public|private|internal|protected)?\s*(?:abstract|sealed)?\s*class\s+(\w+)'
    result["classes"] = re.findall(class_pattern, content)
    
    # 提取方法定义
    method_pattern = r'(?:public|private|internal|protected)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]]+\s+)?(\w+)\s*\([^)]*\)'
    result["methods"] = re.findall(method_pattern, content)
    
    # 提取XML注释
    xml_comment_pattern = r'///\s*(.+)'
    result["comments"] = re.findall(xml_comment_pattern, content)
    
    return result

def _analyze_aspx_file(content: str) -> Dict[str, Any]:
    """分析ASPX文件"""
    result = {
        "controls": [],
        "script_blocks": [],
        "code_behind": ""
    }
    
    # 提取控件
    control_pattern = r'<asp:(\w+)[^>]*\s+ID="(\w+)"'
    controls = re.findall(control_pattern, content)
    result["controls"] = [f"{control_type}: {control_id}" for control_type, control_id in controls]
    
    # 提取脚本块
    script_pattern = r'<script[^>]*>([\s\S]*?)</script>'
    script_blocks = re.findall(script_pattern, content)
    result["script_blocks"] = [block.strip() for block in script_blocks if block.strip()]
    
    # 提取CodeBehind
    codebehind_pattern = r'CodeBehind="([^"]+)"'
    codebehind_match = re.search(codebehind_pattern, content)
    if codebehind_match:
        result["code_behind"] = codebehind_match.group(1)
    
    return result

def _analyze_ashx_file(content: str) -> Dict[str, Any]:
    """分析ASHX文件"""
    result = {
        "handler_class": "",
        "methods": [],
        "process_request": False
    }
    
    # 提取Handler类
    class_pattern = r'class\s+(\w+)\s*:\s*IHttpHandler'
    class_match = re.search(class_pattern, content)
    if class_match:
        result["handler_class"] = class_match.group(1)
    
    # 检查ProcessRequest方法
    if 'ProcessRequest' in content:
        result["process_request"] = True
    
    # 提取方法
    method_pattern = r'(?:public|private|internal|protected)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]]+\s+)?(\w+)\s*\([^)]*\)'
    result["methods"] = re.findall(method_pattern, content)
    
    return result

def _analyze_javascript_file(content: str) -> Dict[str, Any]:
    """分析JavaScript文件"""
    result = {
        "functions": [],
        "variables": [],
        "ajax_calls": [],
        "comments": []
    }
    
    # 提取函数定义
    function_pattern = r'function\s+(\w+)\s*\([^)]*\)'
    result["functions"] = re.findall(function_pattern, content)
    
    # 提取变量声明
    var_pattern = r'(?:var|let|const)\s+(\w+)\s*='
    result["variables"] = re.findall(var_pattern, content)
    
    # 提取AJAX调用
    ajax_patterns = [
        r'\$\.(?:ajax|get|post|getJSON)\s*\([^)]*\)',
        r'fetch\s*\([^)]*\)',
        r'XMLHttpRequest'
    ]
    
    ajax_calls = []
    for pattern in ajax_patterns:
        matches = re.findall(pattern, content, re.DOTALL)
        ajax_calls.extend(matches)
    
    result["ajax_calls"] = ajax_calls
    
    # 提取注释
    comment_pattern = r'//\s*(.+)'
    result["comments"] = re.findall(comment_pattern, content)
    
    return result

def _analyze_html_file(content: str) -> Dict[str, Any]:
    """分析HTML文件"""
    result = {
        "title": "",
        "forms": [],
        "scripts": [],
        "links": []
    }
    
    # 提取标题
    title_pattern = r'<title>([^<]+)</title>'
    title_match = re.search(title_pattern, content)
    if title_match:
        result["title"] = title_match.group(1).strip()
    
    # 提取表单
    form_pattern = r'<form[^>]*>'
    result["forms"] = re.findall(form_pattern, content)
    
    # 提取脚本引用
    script_pattern = r'<script[^>]*src="([^"]+)"'
    result["scripts"] = re.findall(script_pattern, content)
    
    # 提取链接
    link_pattern = r'<a[^>]*href="([^"]+)"'
    result["links"] = re.findall(link_pattern, content)
    
    return result

def _extract_api_endpoints_from_content(content: str, file_type: str) -> List[str]:
    """从内容中提取API端点"""
    endpoints = []
    
    # 通用API端点模式
    patterns = [
        r'ErrorCodeHandler\.ashx\?methodName=([\w]+)',
        r'api/([\w/]+)',
        r'\.ashx\?([\w]+)=',
        r'url\s*[:=]\s*["\']([^"\']+\.ashx[^"\']*)["\']',
        r'["\'](ErrorCodeHandler\.ashx[^"\']*)["\']'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        endpoints.extend(matches)
    
    return list(set(endpoints))  # 去重

def _generate_summary(analysis_result: Dict[str, Any]) -> str:
    """生成分析摘要"""
    summary_parts = []
    
    if analysis_result.get("classes"):
        summary_parts.append(f"包含 {len(analysis_result['classes'])} 个类")
    
    if analysis_result.get("methods"):
        summary_parts.append(f"包含 {len(analysis_result['methods'])} 个方法")
    
    if analysis_result.get("api_endpoints"):
        summary_parts.append(f"包含 {len(analysis_result['api_endpoints'])} 个API端点")
    
    if analysis_result.get("controls"):
        summary_parts.append(f"包含 {len(analysis_result['controls'])} 个控件")
    
    if analysis_result.get("functions"):
        summary_parts.append(f"包含 {len(analysis_result['functions'])} 个函数")
    
    return "; ".join(summary_parts) if summary_parts else "无显著特征"