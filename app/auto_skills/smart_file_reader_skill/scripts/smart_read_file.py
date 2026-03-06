from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
import json
import chardet
from langchain_core.tools import tool

def _extract_python_structure(file_path: Path, max_chars: int, is_large_file: bool) -> str:
    """提取Python文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(min(10000, max_chars))
    except:
        try:
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read(min(10000, max_chars))
        except:
            return f"[无法读取Python文件]"
    
    structure_lines = ["Python文件结构:"]
    
    # 提取导入
    import_pattern = re.compile(r'^(import\s+[\w., ]+|from\s+[\w.]+)', re.MULTILINE)
    imports = import_pattern.findall(content)
    if imports:
        structure_lines.append("\n导入:")
        for imp in imports[:10]:
            structure_lines.append(f"  {imp}")
        if len(imports) > 10:
            structure_lines.append(f"  ... 还有 {len(imports)-10} 个导入")
    
    # 提取类定义
    class_pattern = re.compile(r'^class\s+(\w+)', re.MULTILINE)
    classes = class_pattern.findall(content)
    if classes:
        structure_lines.append("\n类定义:")
        for cls in classes[:10]:
            structure_lines.append(f"  class {cls}")
        if len(classes) > 10:
            structure_lines.append(f"  ... 还有 {len(classes)-10} 个类")
    
    # 提取函数定义
    function_pattern = re.compile(r'^def\s+(\w+)', re.MULTILINE)
    functions = function_pattern.findall(content)
    if functions:
        structure_lines.append("\n函数定义:")
        for func in functions[:10]:
            structure_lines.append(f"  def {func}()")
        if len(functions) > 10:
            structure_lines.append(f"  ... 还有 {len(functions)-10} 个函数")
    
    # 提取主要文档字符串
    docstring_pattern = re.compile(r'"""(.*?)"""', re.DOTALL)
    docstrings = docstring_pattern.findall(content)
    if docstrings:
        structure_lines.append("\n主要文档字符串:")
        for i, doc in enumerate(docstrings[:3]):
            doc_clean = doc.strip().replace('\n', ' ')
            if len(doc_clean) > 100:
                doc_clean = doc_clean[:100] + "..."
            structure_lines.append(f"  [{i+1}] {doc_clean}")
    
    return '\n'.join(structure_lines)

def _extract_markdown_structure(file_path: Path, max_chars: int, is_large_file: bool) -> str:
    """提取Markdown文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(min(15000, max_chars))
    except:
        try:
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read(min(15000, max_chars))
        except:
            return f"[无法读取Markdown文件]"
    
    structure_lines = ["Markdown文件结构:"]
    
    # 提取标题
    heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
    headings = []
    for match in heading_pattern.finditer(content):
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append((level, text))
    
    if headings:
        structure_lines.append("\n标题结构:")
        for level, text in headings[:15]:
            indent = "  " * (level - 1)
            structure_lines.append(f"{indent}{'#' * level} {text}")
        if len(headings) > 15:
            structure_lines.append(f"  ... 还有 {len(headings)-15} 个标题")
    
    # 提取代码块
    code_block_pattern = re.compile(r'^```(\w*)\n([\s\S]*?)\n```', re.MULTILINE)
    code_blocks = list(code_block_pattern.finditer(content))
    
    if code_blocks:
        structure_lines.append(f"\n代码块: {len(code_blocks)} 个")
        for i, match in enumerate(code_blocks[:3]):
            language = match.group(1) or "plain"
            code_preview = match.group(2)[:100].replace('\n', ' ')
            if len(match.group(2)) > 100:
                code_preview += "..."
            structure_lines.append(f"  [{i+1}] {language}: {code_preview}")
    
    # 提取链接
    link_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)', re.MULTILINE)
    links = list(link_pattern.finditer(content))
    
    if links:
        structure_lines.append(f"\n链接: {len(links)} 个")
        for i, match in enumerate(links[:5]):
            text = match.group(1)
            url = match.group(2)
            structure_lines.append(f"  [{i+1}] {text} -> {url}")
    
    return '\n'.join(structure_lines)

def _extract_json_structure(file_path: Path, max_chars: int, is_large_file: bool) -> str:
    """提取JSON文件结构"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(min(20000, max_chars))
    except:
        try:
            with open(file_path, 'r', encoding='gbk', errors='ignore') as f:
                content = f.read(min(20000, max_chars))
        except:
            return f"[无法读取JSON文件]"
    
    structure_lines = ["JSON文件结构:"]
    
    try:
        data = json.loads(content)
        
        if isinstance(data, dict):
            structure_lines.append("类型: 对象 (字典)")
            keys = list(data.keys())
            structure_lines.append(f"键数量: {len(keys)}")
            
            if keys:
                structure_lines.append("\n主要键:")
                for key in keys[:10]:
                    value = data[key]
                    value_type = type(value).__name__
                    
                    if isinstance(value, dict):
                        structure_lines.append(f"  {key}: 对象 (包含 {len(value)} 个键)")
                    elif isinstance(value, list):
                        structure_lines.append(f"  {key}: 数组 (长度 {len(value)})")
                    elif isinstance(value, str):
                        if len(value) > 50:
                            preview = value[:50] + "..."
                        else:
                            preview = value
                        structure_lines.append(f"  {key}: 字符串 = \"{preview}\"")
                    else:
                        structure_lines.append(f"  {key}: {value_type} = {value}")
                
                if len(keys) > 10:
                    structure_lines.append(f"  ... 还有 {len(keys)-10} 个键")
        
        elif isinstance(data, list):
            structure_lines.append("类型: 数组")
            structure_lines.append(f"长度: {len(data)}")
            
            if len(data) > 0:
                first_item = data[0]
                first_type = type(first_item).__name__
                structure_lines.append(f"元素类型: {first_type}")
                
                if isinstance(first_item, dict):
                    structure_lines.append("数组元素结构 (第一个):")
                    keys = list(first_item.keys())[:5]
                    for key in keys:
                        value = first_item[key]
                        value_type = type(value).__name__
                        structure_lines.append(f"  {key}: {value_type}")
        
        else:
            structure_lines.append(f"类型: {type(data).__name__}")
            structure_lines.append(f"值: {data}")
    
    except json.JSONDecodeError as e:
        structure_lines.append(f"JSON解析错误: {e}")
        structure_lines.append("\n原始内容预览:")
        preview = content[:500]
        if len(content) > 500:
            preview += "..."
        structure_lines.append(preview)
    
    return '\n'.join(structure_lines)

def _extract_text_structure(file_path: Path, max_chars: int, is_large_file: bool) -> str:
    """提取文本文件结构"""
    try:
        # 尝试检测编码
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            encoding = result['encoding'] or 'utf-8'
        
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            content = f.read(min(10000, max_chars))
    except:
        return f"[无法读取文本文件]"
    
    structure_lines = ["文本文件结构:"]
    
    lines = content.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    structure_lines.append(f"总行数: {len(lines)}")
    structure_lines.append(f"非空行数: {len(non_empty_lines)}")
    
    if non_empty_lines:
        structure_lines.append("\n内容预览:")
        
        # 显示前10行非空内容
        for i, line in enumerate(non_empty_lines[:10]):
            if len(line) > 100:
                line = line[:100] + "..."
            structure_lines.append(f"  [{i+1}] {line}")
        
        if len(non_empty_lines) > 10:
            structure_lines.append(f"  ... 还有 {len(non_empty_lines)-10} 行")
    
    # 分析内容特征
    features = []
    
    # 检查是否看起来像日志文件
    log_patterns = [
        r'\d{4}-\d{2}-\d{2}',
        r'\d{2}:\d{2}:\d{2}',
        r'\[(INFO|ERROR|WARN|DEBUG)\]',
        r'ERROR|Exception|Traceback'
    ]
    
    log_matches = 0
    for pattern in log_patterns:
        if re.search(pattern, content):
            log_matches += 1
    
    if log_matches >= 2:
        features.append("日志文件特征")
    
    # 检查是否包含大量数字（可能是数据文件）
    numbers = re.findall(r'\b\d+\b', content)
    if len(numbers) > 50:
        features.append("包含大量数字")
    
    # 检查是否包含URL
    urls = re.findall(r'https?://[^\s]+', content)
    if urls:
        features.append(f"包含 {len(urls)} 个URL")
    
    # 检查是否包含电子邮件
    emails = re.findall(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', content)
    if emails:
        features.append(f"包含 {len(emails)} 个电子邮件")
    
    if features:
        structure_lines.append(f"\n特征分析: {', '.join(features)}")
    
    return '\n'.join(structure_lines)

def _detect_file_type(file_path: Path) -> Tuple[str, str]:
    """检测文件类型和编码"""
    # 根据扩展名判断类型
    ext = file_path.suffix.lower()
    
    type_map = {
        '.py': 'python',
        '.md': 'markdown',
        '.json': 'json',
        '.txt': 'text',
        '.log': 'text',
        '.csv': 'text',
        '.tsv': 'text',
        '.yml': 'text',
        '.yaml': 'text',
        '.xml': 'text',
        '.html': 'text',
        '.htm': 'text',
        '.js': 'text',
        '.css': 'text',
        '.java': 'text',
        '.cpp': 'text',
        '.c': 'text',
        '.h': 'text',
        '.cs': 'text',
        '.php': 'text',
        '.rb': 'text',
        '.go': 'text',
        '.rs': 'text',
        '.swift': 'text',
        '.kt': 'text',
        '.sql': 'text',
        '.sh': 'text',
        '.bat': 'text',
        '.ps1': 'text'
    }
    
    file_type = type_map.get(ext, 'binary')
    
    # 检测编码
    encoding = 'utf-8'
    try:
        with open(file_path, 'rb') as f:
            raw_data = f.read(10000)
            result = chardet.detect(raw_data)
            if result['encoding']:
                encoding = result['encoding']
    except:
        pass
    
    return file_type, encoding

@tool
def smart_read_file(
    file_path: str,
    max_chars: int = 10000,
    include_structure: bool = True,
    detect_encoding: bool = True
) -> Dict:
    """智能读取文件，自动处理大文件和不同编码
    
    Args:
        file_path: 文件路径
        max_chars: 最大读取字符数（默认10000）
        include_structure: 是否包含文件结构分析（默认True）
        detect_encoding: 是否自动检测编码（默认True）
        
    Returns:
        包含文件内容和元数据的字典
    """
    path = Path(file_path)
    
    if not path.exists():
        return {"error": f"文件不存在: {file_path}"}
    
    if not path.is_file():
        return {"error": f"不是文件: {file_path}"}
    
    # 获取文件信息
    file_size = path.stat().st_size
    is_large_file = file_size > 1024 * 1024  # 大于1MB视为大文件
    
    # 检测文件类型和编码
    file_type, detected_encoding = _detect_file_type(path)
    
    # 读取内容
    content = ""
    encoding_used = "utf-8"
    
    try:
        if detect_encoding and detected_encoding:
            # 使用检测到的编码
            try:
                with open(file_path, 'r', encoding=detected_encoding, errors='ignore') as f:
                    content = f.read(min(max_chars, file_size))
                encoding_used = detected_encoding
            except:
                # 回退到utf-8
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read(min(max_chars, file_size))
        else:
            # 使用utf-8
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(min(max_chars, file_size))
    except Exception as e:
        return {
            "error": f"读取文件失败: {str(e)}",
            "file_info": {
                "path": str(path),
                "name": path.name,
                "size_bytes": file_size,
                "is_large_file": is_large_file,
                "type": file_type
            }
        }
    
    # 提取结构信息
    structure = ""
    if include_structure:
        if file_type == 'python':
            structure = _extract_python_structure(path, max_chars, is_large_file)
        elif file_type == 'markdown':
            structure = _extract_markdown_structure(path, max_chars, is_large_file)
        elif file_type == 'json':
            structure = _extract_json_structure(path, max_chars, is_large_file)
        elif file_type == 'text':
            structure = _extract_text_structure(path, max_chars, is_large_file)
        else:
            structure = f"文件类型: {file_type}\n不支持详细结构分析"
    
    # 构建结果
    result = {
        "file_info": {
            "path": str(path),
            "name": path.name,
            "size_bytes": file_size,
            "size_human": _format_file_size(file_size),
            "is_large_file": is_large_file,
            "type": file_type,
            "encoding": encoding_used,
            "extension": path.suffix.lower()
        },
        "content": {
            "text": content,
            "length": len(content),
            "truncated": len(content) < file_size,
            "original_size": file_size
        },
        "success": True
    }
    
    if include_structure and structure:
        result["structure"] = structure
    
    return result

def _format_file_size(size_bytes: int) -> str:
    """格式化文件大小"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
