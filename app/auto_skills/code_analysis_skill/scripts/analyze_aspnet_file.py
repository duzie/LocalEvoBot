from langchain_core.tools import tool
import os
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import xml.etree.ElementTree as ET

@tool
def analyze_aspnet_file(file_path: str, app_code_path: str, output_dir: str) -> Dict:
    """
    分析ASP.NET文件，提取API调用和方法引用
    
    Args:
        file_path: ASP.NET文件路径（.aspx, .aspx.cs等）
        app_code_path: App_Code目录路径
        output_dir: 文档输出目录
        
    Returns:
        包含分析结果的字典
    """
    try:
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        # 读取目标文件
        if not os.path.exists(file_path):
            return {"error": f"文件不存在: {file_path}"}
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 分析文件类型
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 提取API调用
        api_calls = extract_api_calls(content, file_ext)
        
        # 在App_Code中查找对应的API实现
        api_implementations = find_api_implementations(api_calls, app_code_path)
        
        # 生成文档
        doc_content = generate_documentation(file_path, content, api_calls, api_implementations)
        
        # 保存文档
        output_file = save_documentation(output_dir, file_path, doc_content)
        
        return {
            "success": True,
            "file_path": file_path,
            "file_type": file_ext,
            "api_calls_count": len(api_calls),
            "api_implementations_found": len(api_implementations),
            "output_file": output_file,
            "api_calls": api_calls,
            "api_implementations": api_implementations,
            "documentation_path": output_file
        }
        
    except Exception as e:
        return {"error": f"分析失败: {str(e)}"}

def extract_api_calls(content: str, file_ext: str) -> List[Dict]:
    """
    从文件内容中提取API调用
    
    Args:
        content: 文件内容
        file_ext: 文件扩展名
        
    Returns:
        API调用列表
    """
    api_calls = []
    
    # 根据文件类型使用不同的提取策略
    if file_ext == '.aspx':
        # 提取ASPX中的服务器端代码块
        api_calls.extend(extract_from_aspx(content))
    elif file_ext == '.cs':
        # 提取C#代码中的方法调用
        api_calls.extend(extract_from_csharp(content))
    elif file_ext == '.aspx.cs':
        # 提取代码隐藏文件中的方法调用
        api_calls.extend(extract_from_csharp(content))
    
    return api_calls

def extract_from_aspx(content: str) -> List[Dict]:
    """从ASPX文件中提取API调用"""
    api_calls = []
    
    # 提取服务器端代码块 <% ... %>
    server_blocks = re.findall(r'<%\s*(.*?)\s*%>', content, re.DOTALL)
    for block in server_blocks:
        # 从代码块中提取方法调用
        calls = extract_method_calls_from_csharp(block)
        api_calls.extend(calls)
    
    # 提取服务器控件事件
    server_events = re.findall(r'On(\w+)="([^"]+)"', content)
    for event_name, handler_name in server_events:
        api_calls.append({
            "type": "server_event",
            "event": event_name,
            "handler": handler_name,
            "location": "ASPX标记"
        })
    
    # 提取数据绑定表达式 <%# ... %>
    data_bindings = re.findall(r'<%#\s*(.*?)\s*%>', content, re.DOTALL)
    for binding in data_bindings:
        # 从绑定表达式中提取方法调用
        calls = extract_method_calls_from_csharp(binding)
        for call in calls:
            call["context"] = "数据绑定表达式"
        api_calls.extend(calls)
    
    return api_calls

def extract_from_csharp(content: str) -> List[Dict]:
    """从C#代码中提取API调用"""
    api_calls = []
    
    # 提取方法调用
    calls = extract_method_calls_from_csharp(content)
    api_calls.extend(calls)
    
    # 提取属性访问
    properties = re.findall(r'(\w+)\.(\w+)\s*[=;]', content)
    for obj_name, prop_name in properties:
        api_calls.append({
            "type": "property_access",
            "object": obj_name,
            "property": prop_name,
            "location": "C#代码"
        })
    
    # 提取事件订阅
    events = re.findall(r'(\w+)\.(\w+)\s*\+=\s*new\s+\w+\((.*?)\)', content)
    for obj_name, event_name, handler in events:
        api_calls.append({
            "type": "event_subscription",
            "object": obj_name,
            "event": event_name,
            "handler": handler,
            "location": "C#代码"
        })
    
    return api_calls

def extract_method_calls_from_csharp(code: str) -> List[Dict]:
    """从C#代码中提取方法调用"""
    calls = []
    
    # 匹配方法调用模式：对象.方法(参数)
    method_pattern = r'(\w+(?:\.\w+)*)\.(\w+)\s*\((.*?)\)'
    matches = re.findall(method_pattern, code)
    
    for full_obj, method_name, params_str in matches:
        # 解析参数
        params = []
        if params_str.strip():
            # 简单分割参数（不处理嵌套括号）
            param_parts = split_params(params_str)
            params = [p.strip() for p in param_parts if p.strip()]
        
        calls.append({
            "type": "method_call",
            "object": full_obj,
            "method": method_name,
            "parameters": params,
            "full_call": f"{full_obj}.{method_name}({params_str})",
            "location": "C#代码"
        })
    
    # 匹配静态方法调用：类名.方法(参数)
    static_pattern = r'(\w+(?:\.\w+)+)\.(\w+)\s*\((.*?)\)'
    static_matches = re.findall(static_pattern, code)
    
    for class_name, method_name, params_str in static_matches:
        params = []
        if params_str.strip():
            param_parts = split_params(params_str)
            params = [p.strip() for p in param_parts if p.strip()]
        
        calls.append({
            "type": "static_method_call",
            "class": class_name,
            "method": method_name,
            "parameters": params,
            "full_call": f"{class_name}.{method_name}({params_str})",
            "location": "C#代码"
        })
    
    return calls

def split_params(params_str: str) -> List[str]:
    """分割参数字符串，处理嵌套括号"""
    params = []
    current = ""
    paren_depth = 0
    bracket_depth = 0
    
    for char in params_str:
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
        elif char == '[':
            bracket_depth += 1
        elif char == ']':
            bracket_depth -= 1
        elif char == ',' and paren_depth == 0 and bracket_depth == 0:
            params.append(current.strip())
            current = ""
            continue
        
        current += char
    
    if current.strip():
        params.append(current.strip())
    
    return params

def find_api_implementations(api_calls: List[Dict], app_code_path: str) -> List[Dict]:
    """
    在App_Code目录中查找API实现
    
    Args:
        api_calls: API调用列表
        app_code_path: App_Code目录路径
        
    Returns:
        API实现信息列表
    """
    implementations = []
    
    if not os.path.exists(app_code_path):
        return implementations
    
    # 收集所有需要查找的方法名
    method_names = set()
    for call in api_calls:
        if "method" in call:
            method_names.add(call["method"])
    
    # 搜索App_Code目录中的所有C#文件
    for root, dirs, files in os.walk(app_code_path):
        for file in files:
            if file.endswith('.cs'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
                    
                    # 在文件中查找方法定义
                    for method_name in method_names:
                        # 查找方法定义：public/protected/private 返回类型 方法名(参数)
                        pattern = rf'(public|protected|private|internal)\s+\w+\s+{method_name}\s*\((.*?)\)'
                        matches = re.findall(pattern, file_content, re.DOTALL)
                        
                        for access_modifier, params in matches:
                            # 提取方法所在的类
                            class_pattern = r'class\s+(\w+)'
                            class_match = re.search(class_pattern, file_content[:file_content.find(method_name)])
                            class_name = class_match.group(1) if class_match else "Unknown"
                            
                            implementations.append({
                                "method_name": method_name,
                                "class_name": class_name,
                                "file_path": file_path,
                                "access_modifier": access_modifier,
                                "parameters": params.strip(),
                                "full_path": f"{class_name}.{method_name}"
                            })
                            
                except Exception as e:
                    continue
    
    return implementations

def generate_documentation(file_path: str, content: str, api_calls: List[Dict], api_implementations: List[Dict]) -> str:
    """
    生成文档内容
    
    Args:
        file_path: 分析的文件路径
        content: 文件内容
        api_calls: API调用列表
        api_implementations: API实现列表
        
    Returns:
        文档内容字符串
    """
    doc = []
    
    # 文档头部
    doc.append("# ASP.NET文件分析文档")
    doc.append("")
    doc.append(f"## 分析文件: `{file_path}`")
    doc.append(f"## 分析时间: {get_current_time()}")
    doc.append("")
    
    # 文件基本信息
    doc.append("## 文件基本信息")
    doc.append(f"- **文件路径**: {file_path}")
    doc.append(f"- **文件大小**: {len(content)} 字节")
    doc.append(f"- **API调用总数**: {len(api_calls)}")
    doc.append(f"- **找到的实现**: {len(api_implementations)}")
    doc.append("")
    
    # API调用详情
    doc.append("## API调用详情")
    if api_calls:
        doc.append("### 方法调用")
        method_calls = [c for c in api_calls if c["type"] in ["method_call", "static_method_call"]]
        for call in method_calls:
            doc.append(f"#### {call['full_call']}")
            doc.append(f"- **类型**: {call['type']}")
            if "object" in call:
                doc.append(f"- **对象**: {call['object']}")
            if "class" in call:
                doc.append(f"- **类**: {call['class']}")
            doc.append(f"- **方法**: {call['method']}")
            if call['parameters']:
                doc.append(f"- **参数**: {', '.join(call['parameters'])}")
            doc.append(f"- **位置**: {call['location']}")
            doc.append("")
        
        doc.append("### 服务器事件")
        events = [c for c in api_calls if c["type"] == "server_event"]
        for event in events:
            doc.append(f"- **事件**: {event['event']}")
            doc.append(f"  - **处理程序**: {event['handler']}")
            doc.append(f"  - **位置**: {event['location']}")
            doc.append("")
        
        doc.append("### 属性访问")
        properties = [c for c in api_calls if c["type"] == "property_access"]
        for prop in properties:
            doc.append(f"- **对象**: {prop['object']}.{prop['property']}")
            doc.append(f"  - **位置**: {prop['location']}")
            doc.append("")
    else:
        doc.append("未找到API调用")
        doc.append("")
    
    # API实现详情
    doc.append("## API实现详情")
    if api_implementations:
        # 按类分组
        implementations_by_class = {}
        for impl in api_implementations:
            class_name = impl["class_name"]
            if class_name not in implementations_by_class:
                implementations_by_class[class_name] = []
            implementations_by_class[class_name].append(impl)
        
        for class_name, impls in implementations_by_class.items():
            doc.append(f"### 类: {class_name}")
            for impl in impls:
                doc.append(f"#### {impl['method_name']}")
                doc.append(f"- **访问修饰符**: {impl['access_modifier']}")
                doc.append(f"- **参数**: {impl['parameters']}")
                doc.append(f"- **文件**: {impl['file_path']}")
                doc.append(f"- **完整路径**: {impl['full_path']}")
                doc.append("")
    else:
        doc.append("未在App_Code中找到对应的API实现")
        doc.append("")
    
    # 文件内容预览
    doc.append("## 文件内容预览")
    doc.append("```aspx")
    # 只显示前200行
    lines = content.split('\n')
    preview_lines = lines[:200] if len(lines) > 200 else lines
    doc.append('\n'.join(preview_lines))
    if len(lines) > 200:
        doc.append(f"\n... 还有 {len(lines) - 200} 行未显示")
    doc.append("```")
    
    return '\n'.join(doc)

def get_current_time() -> str:
    """获取当前时间字符串"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def save_documentation(output_dir: str, original_file_path: str, doc_content: str) -> str:
    """
    保存文档到文件
    
    Args:
        output_dir: 输出目录
        original_file_path: 原始文件路径
        doc_content: 文档内容
        
    Returns:
        保存的文件路径
    """
    # 基于原始文件名生成文档文件名
    original_filename = os.path.basename(original_file_path)
    doc_filename = f"{os.path.splitext(original_filename)[0]}_analysis.md"
    output_file = os.path.join(output_dir, doc_filename)
    
    # 确保目录存在
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # 保存文档
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(doc_content)
    
    return output_file