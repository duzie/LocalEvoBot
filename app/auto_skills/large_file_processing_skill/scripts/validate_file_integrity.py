from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, List
from langchain.tools import tool


@tool
def validate_file_integrity(file_path: str, file_type: str = "cs") -> Dict[str, Any]:
    """
    验证文件完整性（检查语法、结构等）
    
    Args:
        file_path: 文件路径
        file_type: 文件类型：cs/js/py等
        
    Returns:
        包含验证结果的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # 基本统计
        lines = content.split('\n')
        total_lines = len(lines)
        total_chars = len(content)
        
        # 根据文件类型进行验证
        validation_results = {
            "basic_stats": {
                "file_path": file_path,
                "file_type": file_type,
                "total_lines": total_lines,
                "total_chars": total_chars,
                "file_size_bytes": os.path.getsize(file_path)
            },
            "checks": [],
            "issues": [],
            "warnings": []
        }
        
        # C#文件验证
        if file_type.lower() == "cs":
            # 检查大括号平衡
            open_braces = content.count('{')
            close_braces = content.count('}')
            if open_braces != close_braces:
                validation_results["issues"].append({
                    "type": "syntax_error",
                    "message": f"大括号不平衡: {{ {open_braces} 个, }} {close_braces} 个",
                    "severity": "high"
                })
            
            # 检查分号
            semicolons = content.count(';')
            validation_results["checks"].append({
                "check": "semicolon_count",
                "value": semicolons,
                "status": "ok"
            })
            
            # 检查类定义
            class_pattern = r'(?:public\s+|private\s+|protected\s+|internal\s+|sealed\s+|abstract\s+)*class\s+(\w+)'
            classes = re.findall(class_pattern, content)
            validation_results["checks"].append({
                "check": "class_definitions",
                "value": len(classes),
                "classes": classes,
                "status": "ok" if classes else "warning"
            })
            
            # 检查方法定义
            method_pattern = r'(?:public\s+|private\s+|protected\s+|internal\s+|static\s+|virtual\s+|override\s+|abstract\s+)*\w+\s+\w+\s*\([^)]*\)\s*{'
            methods = re.findall(method_pattern, content)
            validation_results["checks"].append({
                "check": "method_definitions",
                "value": len(methods),
                "status": "ok"
            })
            
            # 检查using语句
            using_pattern = r'using\s+[^;]+;'
            usings = re.findall(using_pattern, content)
            validation_results["checks"].append({
                "check": "using_statements",
                "value": len(usings),
                "usings": usings[:10],  # 只显示前10个
                "status": "ok"
            })
            
            # 检查空行比例
            empty_lines = sum(1 for line in lines if line.strip() == '')
            if total_lines > 0:
                empty_line_ratio = empty_lines / total_lines
                if empty_line_ratio > 0.4:
                    validation_results["warnings"].append({
                        "type": "format_warning",
                        "message": f"空行比例过高: {empty_line_ratio:.1%}",
                        "suggestion": "考虑减少空行以提高可读性"
                    })
        
        # Python文件验证
        elif file_type.lower() == "py":
            # 1. 严格语法检查 (AST Parse)
            import ast
            try:
                ast.parse(content, filename=file_path)
            except SyntaxError as e:
                validation_results["issues"].append({
                    "type": "syntax_error",
                    "message": f"Python语法错误: {e.msg}",
                    "line": e.lineno,
                    "offset": e.offset,
                    "text": e.text,
                    "severity": "critical"
                })

            # 2. 检查缩进（简单的制表符/空格检查）
            tab_lines = sum(1 for line in lines if line.startswith('\t'))
            space_lines = sum(1 for line in lines if line.startswith(' '))
            
            if tab_lines > 0 and space_lines > 0:
                validation_results["warnings"].append({
                    "type": "format_warning",
                    "message": "混合使用制表符和空格进行缩进",
                    "suggestion": "统一使用空格或制表符"
                })
            
            # 3. 检查函数定义
            function_pattern = r'def\s+\w+\s*\([^)]*\)\s*:'
            functions = re.findall(function_pattern, content)
            validation_results["checks"].append({
                "check": "function_definitions",
                "value": len(functions),
                "status": "ok"
            })
            
            # 4. 检查类定义
            class_pattern = r'class\s+\w+\s*\(?[^:]*\)?\s*:'
            classes = re.findall(class_pattern, content)
            validation_results["checks"].append({
                "check": "class_definitions",
                "value": len(classes),
                "classes": [c.split()[1].split('(')[0] for c in classes],
                "status": "ok" if classes else "warning"
            })
        
        # JavaScript文件验证
        elif file_type.lower() in ["js", "javascript"]:
            # 检查函数定义
            function_pattern = r'function\s+\w+\s*\([^)]*\)\s*{'
            functions = re.findall(function_pattern, content)
            validation_results["checks"].append({
                "check": "function_definitions",
                "value": len(functions),
                "status": "ok"
            })
            
            # 检查变量声明
            var_pattern = r'(?:var|let|const)\s+\w+\s*='
            variables = re.findall(var_pattern, content)
            validation_results["checks"].append({
                "check": "variable_declarations",
                "value": len(variables),
                "status": "ok"
            })
        
        # 通用检查
        # 检查行长度
        long_lines = []
        for i, line in enumerate(lines, 1):
            if len(line) > 120:  # 超过120字符的行
                long_lines.append({
                    "line": i,
                    "length": len(line),
                    "preview": line[:50] + "..." if len(line) > 50 else line
                })
        
        if long_lines:
            validation_results["warnings"].append({
                "type": "format_warning",
                "message": f"发现 {len(long_lines)} 行超过120字符",
                "long_lines": long_lines[:5],  # 只显示前5行
                "suggestion": "考虑拆分长行以提高可读性"
            })
        
        # 检查文件编码（简单检查）
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read()
            encoding_ok = True
        except UnicodeDecodeError:
            encoding_ok = False
            validation_results["issues"].append({
                "type": "encoding_error",
                "message": "UTF-8解码失败",
                "severity": "medium"
            })
        
        # 总体评估
        has_issues = len(validation_results["issues"]) > 0
        has_warnings = len(validation_results["warnings"]) > 0
        
        validation_results["summary"] = {
            "status": "failed" if has_issues else ("warning" if has_warnings else "passed"),
            "total_checks": len(validation_results["checks"]),
            "issues_count": len(validation_results["issues"]),
            "warnings_count": len(validation_results["warnings"]),
            "message": f"验证完成: {total_lines} 行, {total_chars} 字符"
        }
        
        return {
            "success": True,
            "validation": validation_results
        }
        
    except Exception as e:
        return {"success": False, "error": f"验证文件失败: {str(e)}"}