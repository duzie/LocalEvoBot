from pathlib import Path
from typing import Dict
import re
from langchain_core.tools import tool

def _analyze_markdown_file(file_path: Path) -> Dict:
    """分析Markdown文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(50000)
        
        analysis = {
            "language": "Markdown",
            "headings": [],
            "code_blocks": [],
            "links": [],
            "images": []
        }
        
        lines = content.split('\n')
        
        # 分析标题
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        for match in heading_pattern.finditer(content):
            level = len(match.group(1))
            text = match.group(2).strip()
            analysis["headings"].append({"level": level, "text": text})
        
        # 分析代码块
        code_block_pattern = re.compile(r'^```(\w*)\n([\s\S]*?)\n```', re.MULTILINE)
        for match in code_block_pattern.finditer(content):
            language = match.group(1) or "unknown"
            code = match.group(2)
            analysis["code_blocks"].append({
                "language": language,
                "line_count": len(code.split('\n'))
            })
        
        # 分析链接
        link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)', re.MULTILINE)
        for match in link_pattern.finditer(content):
            text = match.group(1)
            url = match.group(2)
            analysis["links"].append({"text": text, "url": url})
        
        # 分析图片
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)', re.MULTILINE)
        for match in image_pattern.finditer(content):
            alt_text = match.group(1)
            url = match.group(2)
            analysis["images"].append({"alt": alt_text, "url": url})
        
        # 统计
        analysis["stats"] = {
            "total_lines": len(lines),
            "heading_count": len(analysis["headings"]),
            "code_block_count": len(analysis["code_blocks"]),
            "link_count": len(analysis["links"]),
            "image_count": len(analysis["images"])
        }
        
        return analysis
        
    except Exception as e:
        return {
            "error": str(e),
            "language": "Markdown",
            "headings": [],
            "code_blocks": [],
            "links": [],
            "images": [],
            "stats": {"total_lines": 0, "heading_count": 0, "code_block_count": 0, "link_count": 0, "image_count": 0}
        }

def _analyze_python_file(file_path: Path) -> Dict:
    """分析Python文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(50000)
        
        analysis = {
            "language": "Python",
            "imports": [],
            "classes": [],
            "functions": [],
            "docstrings": []
        }
        
        lines = content.split('\n')
        
        # 分析导入
        import_pattern = re.compile(r'^(import\s+[\w., ]+|from\s+[\w.]+)', re.MULTILINE)
        imports = import_pattern.findall(content)
        analysis["imports"] = [imp.strip() for imp in imports]
        
        # 分析类定义
        class_pattern = re.compile(r'^class\s+(\w+)', re.MULTILINE)
        classes = class_pattern.findall(content)
        analysis["classes"] = classes
        
        # 分析函数定义
        function_pattern = re.compile(r'^def\s+(\w+)', re.MULTILINE)
        functions = function_pattern.findall(content)
        analysis["functions"] = functions
        
        # 分析文档字符串
        docstring_pattern = re.compile(r'"""(.*?)"""', re.DOTALL)
        docstrings = docstring_pattern.findall(content)
        analysis["docstrings"] = [ds.strip() for ds in docstrings[:5]]  # 只取前5个
        
        # 统计
        analysis["stats"] = {
            "total_lines": len(lines),
            "import_count": len(analysis["imports"]),
            "class_count": len(analysis["classes"]),
            "function_count": len(analysis["functions"]),
            "docstring_count": len(analysis["docstrings"])
        }
        
        return analysis
        
    except Exception as e:
        return {
            "error": str(e),
            "language": "Python",
            "imports": [],
            "classes": [],
            "functions": [],
            "docstrings": [],
            "stats": {"total_lines": 0, "import_count": 0, "class_count": 0, "function_count": 0, "docstring_count": 0}
        }

def _analyze_json_file(file_path: Path) -> Dict:
    """分析JSON文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(50000)
        
        import json
        data = json.loads(content)
        
        analysis = {
            "language": "JSON",
            "structure": _analyze_json_structure(data),
            "size": len(content)
        }
        
        # 统计
        analysis["stats"] = {
            "total_chars": len(content),
            "is_valid": True
        }
        
        return analysis
        
    except Exception as e:
        return {
            "error": str(e),
            "language": "JSON",
            "structure": {},
            "size": 0,
            "stats": {"total_chars": 0, "is_valid": False}
        }

def _analyze_json_structure(data, depth=0, max_depth=3):
    """递归分析JSON结构"""
    if depth >= max_depth:
        return {"type": "truncated", "depth": depth}
    
    if isinstance(data, dict):
        result = {"type": "object", "keys": [], "children": {}}
        for key, value in data.items():
            result["keys"].append(key)
            result["children"][key] = _analyze_json_structure(value, depth + 1, max_depth)
        return result
    elif isinstance(data, list):
        if len(data) > 0:
            # 分析第一个元素的类型作为代表
            sample = _analyze_json_structure(data[0], depth + 1, max_depth)
            return {"type": "array", "length": len(data), "sample_type": sample}
        else:
            return {"type": "array", "length": 0, "sample_type": "empty"}
    elif isinstance(data, str):
        return {"type": "string", "length": len(data)}
    elif isinstance(data, (int, float)):
        return {"type": "number", "value": data}
    elif isinstance(data, bool):
        return {"type": "boolean", "value": data}
    elif data is None:
        return {"type": "null"}
    else:
        return {"type": "unknown"}

def _analyze_text_file(file_path: Path) -> Dict:
    """分析文本文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(50000)
        
        analysis = {
            "language": "Text",
            "lines": [],
            "paragraphs": []
        }
        
        lines = content.split('\n')
        analysis["lines"] = [line.strip() for line in lines[:50]]  # 只取前50行
        
        # 分析段落
        paragraphs = content.split('\n\n')
        analysis["paragraphs"] = [para.strip() for para in paragraphs[:10] if para.strip()]  # 只取前10个非空段落
        
        # 统计
        analysis["stats"] = {
            "total_lines": len(lines),
            "total_chars": len(content),
            "paragraph_count": len(analysis["paragraphs"]),
            "avg_line_length": sum(len(line) for line in lines) / max(len(lines), 1)
        }
        
        return analysis
        
    except Exception as e:
        return {
            "error": str(e),
            "language": "Text",
            "lines": [],
            "paragraphs": [],
            "stats": {"total_lines": 0, "total_chars": 0, "paragraph_count": 0, "avg_line_length": 0}
        }

@tool
def analyze_file_structure(file_path: str) -> Dict:
    """分析文件结构，支持多种文件类型
    
    Args:
        file_path: 文件路径
        
    Returns:
        包含文件结构分析的字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    
    # 根据文件扩展名选择分析器
    ext = path.suffix.lower()
    
    if ext == '.md':
        return _analyze_markdown_file(path)
    elif ext == '.py':
        return _analyze_python_file(path)
    elif ext == '.json':
        return _analyze_json_file(path)
    elif ext in ['.txt', '.log', '.csv', '.tsv']:
        return _analyze_text_file(path)
    else:
        # 默认使用文本分析
        return _analyze_text_file(path)
