from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, Optional, List

@tool
def extract_code_class(file_path: str, class_name: str, include_dependencies: bool = True) -> Dict[str, Any]:
    """
    从代码文件中提取指定类
    
    Args:
        file_path: 源文件路径
        class_name: 要提取的类名
        include_dependencies: 是否包含依赖的using语句
        
    Returns:
        包含提取结果的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "class_content": None
            }
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取using语句（如果需要）
        using_statements = []
        if include_dependencies:
            using_pattern = r'^using\s+[^;]+;'
            using_statements = re.findall(using_pattern, content, re.MULTILINE)
            # 去重
            using_statements = list(dict.fromkeys(using_statements))
        
        # 查找类定义
        # 匹配类定义，包括可能的修饰符如 public、internal、abstract等
        class_pattern = rf'(public\s+|internal\s+|protected\s+|private\s+|abstract\s+|sealed\s+|static\s+)*class\s+{class_name}\b'
        class_match = re.search(class_pattern, content)
        
        if not class_match:
            return {
                "success": False,
                "error": f"未找到类: {class_name}",
                "class_content": None,
                "file_content_preview": content[:500] if len(content) > 500 else content
            }
        
        # 找到类定义的开始位置
        start_pos = class_match.start()
        
        # 查找类的结束位置（匹配大括号）
        brace_count = 0
        in_class = False
        end_pos = start_pos
        
        for i in range(start_pos, len(content)):
            char = content[i]
            
            if char == '{':
                brace_count += 1
                in_class = True
            elif char == '}':
                brace_count -= 1
                
                if in_class and brace_count == 0:
                    end_pos = i + 1  # 包含结束大括号
                    break
        
        if not in_class or brace_count != 0:
            return {
                "success": False,
                "error": f"类 {class_name} 的大括号不匹配",
                "class_content": content[start_pos:start_pos + 1000],
                "file_content_preview": content[:500] if len(content) > 500 else content
            }
        
        # 提取类内容
        class_content = content[start_pos:end_pos]
        
        # 构建完整内容
        full_content = ""
        if using_statements:
            full_content = "\n".join(using_statements) + "\n\n"
        full_content += class_content
        
        # 提取类的命名空间（如果存在）
        namespace_pattern = r'namespace\s+([^\s{]+)'
        namespace_match = re.search(namespace_pattern, content[:start_pos])
        namespace = namespace_match.group(1) if namespace_match else None
        
        # 提取类的方法和属性数量
        method_count = len(re.findall(r'public\s+\w+\s+\w+\s*\(', class_content))
        property_count = len(re.findall(r'public\s+\w+\s+\w+\s*\{', class_content))
        
        return {
            "success": True,
            "message": f"成功提取类: {class_name}",
            "class_name": class_name,
            "class_content": class_content,
            "full_content": full_content,
            "namespace": namespace,
            "using_statements": using_statements,
            "method_count": method_count,
            "property_count": property_count,
            "start_position": start_pos,
            "end_position": end_pos,
            "length": len(class_content)
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"提取过程中发生错误: {str(e)}",
            "class_content": None
        }