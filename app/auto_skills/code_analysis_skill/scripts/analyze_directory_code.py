from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, List, Optional
from .analyze_code_file import analyze_code_file

@tool
def analyze_directory_code(directory_path: Optional[str] = None, 
                          file_extensions: List[str] = None) -> Dict[str, Any]:
    """
    分析目录下的所有代码文件
    
    Args:
        directory_path: 目录路径
        file_extensions: 要分析的文件扩展名
        
    Returns:
        包含分析结果的字典
    """
    try:
        if directory_path is None:
            directory_path = os.getcwd()
        
        if not os.path.exists(directory_path):
            return {"success": False, "error": f"目录不存在: {directory_path}"}
        
        if file_extensions is None:
            file_extensions = ['.cs', '.aspx', '.ashx', '.js', '.html', '.htm']
        
        # 收集所有代码文件
        code_files = []
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                file_ext = os.path.splitext(file)[1].lower()
                if file_ext in file_extensions:
                    full_path = os.path.join(root, file)
                    code_files.append(full_path)
        
        # 分析每个文件
        file_analyses = []
        total_files = len(code_files)
        
        for i, file_path in enumerate(code_files, 1):
            try:
                print(f"分析文件 {i}/{total_files}: {os.path.basename(file_path)}")
                analysis = analyze_code_file(file_path)
                if analysis.get("success"):
                    file_analyses.append(analysis)
            except Exception as e:
                print(f"分析文件失败 {file_path}: {str(e)}")
        
        # 汇总统计
        summary = {
            "success": True,
            "directory_path": directory_path,
            "total_files_found": total_files,
            "total_files_analyzed": len(file_analyses),
            "file_types": {},
            "api_endpoints": [],
            "classes": [],
            "methods": [],
            "files_by_type": {}
        }
        
        # 按类型统计
        for analysis in file_analyses:
            file_type = analysis.get("file_type", "unknown")
            
            # 统计文件类型
            if file_type not in summary["file_types"]:
                summary["file_types"][file_type] = 0
            summary["file_types"][file_type] += 1
            
            # 按类型分组文件
            if file_type not in summary["files_by_type"]:
                summary["files_by_type"][file_type] = []
            summary["files_by_type"][file_type].append({
                "file_name": analysis.get("file_name"),
                "file_path": analysis.get("file_path"),
                "summary": analysis.get("summary", "")
            })
            
            # 收集API端点
            endpoints = analysis.get("api_endpoints", [])
            if endpoints:
                summary["api_endpoints"].extend(endpoints)
            
            # 收集类
            classes = analysis.get("classes", [])
            if classes:
                summary["classes"].extend(classes)
            
            # 收集方法
            methods = analysis.get("methods", [])
            if methods:
                summary["methods"].extend(methods)
        
        # 去重
        summary["api_endpoints"] = list(set(summary["api_endpoints"]))
        summary["classes"] = list(set(summary["classes"]))
        summary["methods"] = list(set(summary["methods"]))
        
        # 生成总体摘要
        summary["overall_summary"] = _generate_overall_summary(summary)
        
        # 添加详细分析结果
        summary["detailed_analyses"] = file_analyses
        
        return summary
        
    except Exception as e:
        return {"success": False, "error": str(e), "directory_path": directory_path}

def _generate_overall_summary(summary: Dict[str, Any]) -> str:
    """生成总体摘要"""
    parts = []
    
    parts.append(f"共找到 {summary['total_files_found']} 个代码文件")
    parts.append(f"成功分析 {summary['total_files_analyzed']} 个文件")
    
    if summary["file_types"]:
        type_parts = []
        for file_type, count in summary["file_types"].items():
            type_parts.append(f"{file_type}: {count}")
        parts.append(f"文件类型分布: {', '.join(type_parts)}")
    
    if summary["api_endpoints"]:
        parts.append(f"发现 {len(summary['api_endpoints'])} 个API端点")
    
    if summary["classes"]:
        parts.append(f"发现 {len(summary['classes'])} 个类")
    
    if summary["methods"]:
        parts.append(f"发现 {len(summary['methods'])} 个方法")
    
    return "; ".join(parts)