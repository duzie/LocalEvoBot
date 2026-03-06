from langchain_core.tools import tool

from pathlib import Path
from typing import Dict, Any

def _get_size_category(file_size: int) -> str:
    """获取文件大小分类"""
    if file_size < 1024:  # < 1KB
        return "tiny"
    elif file_size < 1024 * 10:  # < 10KB
        return "very_small"
    elif file_size < 1024 * 100:  # < 100KB
        return "small"
    elif file_size < 1024 * 1024:  # < 1MB
        return "medium"
    elif file_size < 10 * 1024 * 1024:  # < 10MB
        return "large"
    elif file_size < 100 * 1024 * 1024:  # < 100MB
        return "very_large"
    else:  # >= 100MB
        return "huge"


def _guess_file_type(extension: str) -> str:
    """猜测文件类型"""
    ext = extension.lower().lstrip('.')
    
    code_extensions = ['py', 'js', 'ts', 'cs', 'java', 'cpp', 'c', 'h', 'hpp', 'php', 'rb', 'go', 'rs', 'swift']
    text_extensions = ['txt', 'md', 'rst', 'log', 'csv', 'tsv']
    structured_extensions = ['json', 'xml', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf']
    binary_extensions = ['exe', 'dll', 'so', 'bin', 'dat', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx']
    
    if ext in code_extensions:
        return "code"
    elif ext in text_extensions:
        return "text"
    elif ext in structured_extensions:
        return "structured_data"
    elif ext in binary_extensions:
        return "binary"
    else:
        return "unknown"


@tool
def optimize_file_reading(file_path: str, strategy: str = "adaptive") -> Dict[str, Any]:
    """优化文件读取参数建议
    
    Args:
        file_path: 文件路径
        strategy: 优化策略 adaptive/memory/speed
        
    Returns:
        包含文件信息与推荐读取策略的字典
    """
    path = Path(file_path)
    if not path.exists():
        return {"success": False, "error": f"文件不存在: {file_path}"}
    if not path.is_file():
        return {"success": False, "error": f"不是文件: {file_path}"}

    st = path.stat()
    file_size = st.st_size
    ext = path.suffix or ""

    normalized_strategy = (strategy or "adaptive").strip().lower()
    if normalized_strategy not in {"adaptive", "memory", "speed"}:
        normalized_strategy = "adaptive"

    size_category = _get_size_category(file_size)
    file_type = _guess_file_type(ext)

    if size_category in {"tiny", "very_small", "small"}:
        base_chunk = 16 * 1024
        max_chars = 20000
        preferred_method = "baseline"
    elif size_category in {"medium"}:
        base_chunk = 64 * 1024
        max_chars = 30000
        preferred_method = "buffered"
    elif size_category in {"large"}:
        base_chunk = 128 * 1024
        max_chars = 50000
        preferred_method = "chunked"
    elif size_category in {"very_large"}:
        base_chunk = 256 * 1024
        max_chars = 80000
        preferred_method = "chunked"
    else:
        base_chunk = 512 * 1024
        max_chars = 120000
        preferred_method = "chunked"

    if normalized_strategy == "memory":
        chunk_size = max(8 * 1024, int(base_chunk / 4))
        read_mode = "content" if size_category in {"large", "very_large", "huge"} else "full"
    elif normalized_strategy == "speed":
        chunk_size = min(2 * 1024 * 1024, int(base_chunk * 2))
        read_mode = "full" if size_category not in {"huge"} else "content"
    else:
        chunk_size = base_chunk
        read_mode = "full" if size_category in {"tiny", "very_small", "small", "medium"} else "content"

    suggestions = []
    if file_type == "binary":
        suggestions.append("疑似二进制文件，建议不要按文本方式完整读取")
    if size_category in {"very_large", "huge"}:
        suggestions.append("文件较大，优先使用分块读取或仅提取结构/摘要")
    if file_type in {"code", "structured_data"} and read_mode == "content":
        suggestions.append("可先用 analyze_file_structure 或 generate_file_summary 获取概览")

    return {
        "success": True,
        "file_info": {
            "path": str(path),
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "extension": ext,
            "size_category": size_category,
            "file_type": file_type,
        },
        "strategy": normalized_strategy,
        "recommended": {
            "read_mode": read_mode,
            "preferred_method": preferred_method,
            "chunk_size": int(chunk_size),
            "max_chars": int(max_chars),
        },
        "suggestions": suggestions,
    }


# 测试代码
if __name__ == "__main__":
    # 测试当前文件
    test_file = Path(__file__)
    result = optimize_file_reading(str(test_file), "adaptive")
    
    print("优化分析结果:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
