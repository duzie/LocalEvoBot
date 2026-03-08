"""
validate_web_file - 自动识别文件类型并校验

根据文件扩展名自动调用对应的校验工具。
"""

from langchain_core.tools import tool
import os
from typing import Dict, Any


@tool
def validate_web_file(file_path: str) -> Dict[str, Any]:
    """
    自动识别 Web 文件类型并校验
    
    Args:
        file_path: 文件路径
    
    Returns:
        {
            "success": True/False,
            "file_type": "html" | "js" | "css",
            "message": "校验结果",
            "errors": [...]
        }
    """
    tool_name = "validate_web_file"
    
    try:
        # 1. 检查文件
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在：{file_path}"
            }
        
        # 2. 识别文件类型
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext in ['.html', '.htm', '.xhtml']:
            # HTML 文件
            from .validate_html import validate_html
            return validate_html.invoke({"file_path": file_path})
        
        elif ext in ['.js', '.jsx', '.mjs', '.cjs']:
            # JavaScript 文件
            from .validate_js import validate_js
            return validate_js.invoke({"file_path": file_path})
        
        elif ext in ['.css', '.scss', '.sass', '.less']:
            # CSS 文件
            from .validate_css import validate_css
            return validate_css.invoke({"file_path": file_path})
        
        else:
            return {
                "success": False,
                "error": f"不支持的文件类型：{ext}",
                "supported_types": [".html", ".htm", ".js", ".jsx", ".css", ".scss"]
            }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"校验失败：{e}"
        }


@tool
def validate_web_project(project_path: str) -> Dict[str, Any]:
    """
    校验整个 Web 项目
    
    Args:
        project_path: 项目目录路径
    
    Returns:
        {
            "success": True/False,
            "total_files": 总文件数，
            "passed_files": 通过数，
            "failed_files": 失败数，
            "results": [
                {
                    "file": "文件路径",
                    "type": "html" | "js" | "css",
                    "success": True/False,
                    "errors": [...]
                }
            ]
        }
    """
    tool_name = "validate_web_project"
    
    try:
        if not os.path.exists(project_path):
            return {
                "success": False,
                "error": f"目录不存在：{project_path}"
            }
        
        if not os.path.isdir(project_path):
            return {
                "success": False,
                "error": f"不是目录：{project_path}"
            }
        
        # 收集所有 Web 文件
        web_extensions = ['.html', '.htm', '.js', '.jsx', '.mjs', '.cjs', '.css', '.scss']
        web_files = []
        
        for root, dirs, files in os.walk(project_path):
            # 跳过 node_modules 等目录
            skip_dirs = ['node_modules', '.git', 'dist', 'build', '__pycache__']
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in web_extensions:
                    web_files.append(os.path.join(root, file))
        
        # 校验每个文件
        results = []
        passed = 0
        failed = 0
        
        for file_path in web_files:
            result = validate_web_file.invoke({"file_path": file_path})
            
            results.append({
                "file": file_path,
                "type": os.path.splitext(file_path)[1][1:],  # 去掉点
                "success": result.get("success", False),
                "errors": result.get("errors", [])
            })
            
            if result.get("success"):
                passed += 1
            else:
                failed += 1
        
        return {
            "success": failed == 0,
            "total_files": len(web_files),
            "passed_files": passed,
            "failed_files": failed,
            "results": results,
            "message": f"校验完成：{passed} 通过，{failed} 失败"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"校验失败：{e}"
        }
