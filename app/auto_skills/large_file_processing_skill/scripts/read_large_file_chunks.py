import os
from typing import Dict, Any
from langchain.tools import tool


@tool
def read_large_file_chunks(
    file_path: str,
    chunk_size: int = 12000,
    encoding: str = "utf-8",
    start_chunk: int = 0,
    max_chunks: int = 3,
) -> Dict[str, Any]:
    """
    分块读取大文件，避免上下文溢出
    
    Args:
        file_path: 文件路径
        chunk_size: 每块最大字符数，默认12000
        encoding: 文件编码，默认utf-8
        start_chunk: 起始块索引（从0开始）
        max_chunks: 最多返回多少块（避免上下文溢出）
        
    Returns:
        包含文件信息和分块内容的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        # 获取文件大小
        file_size = os.path.getsize(file_path)
        
        safe_chunk_size = max(256, int(chunk_size or 12000))
        safe_chunk_size = min(safe_chunk_size, 20000)
        safe_start = max(0, int(start_chunk or 0))
        safe_max = max(1, min(int(max_chunks or 3), 8))

        total_chars = 0
        total_chunks = 0
        chunks = []
        start_index = safe_start
        end_index = safe_start + safe_max

        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            while True:
                chunk = f.read(safe_chunk_size)
                if not chunk:
                    break
                chunk_len = len(chunk)
                start_char = total_chars
                end_char = total_chars + chunk_len

                if start_index <= total_chunks < end_index:
                    chunks.append({
                        "chunk_index": total_chunks,
                        "start_char": start_char,
                        "end_char": end_char,
                        "content": chunk,
                        "size_chars": chunk_len,
                    })

                total_chunks += 1
                total_chars += chunk_len
        
        return {
            "success": True,
            "file_path": file_path,
            "file_size_bytes": file_size,
            "total_chars": total_chars,
            "chunk_size": safe_chunk_size,
            "start_chunk": safe_start,
            "max_chunks": safe_max,
            "returned_chunks": len(chunks),
            "total_chunks": total_chunks,
            "chunks": chunks,
            "summary": f"文件大小: {file_size} 字节, {total_chars} 字符, 共 {total_chunks} 块；本次返回 {len(chunks)} 块（{safe_start}-{min(end_index - 1, max(total_chunks - 1, 0))}）"
        }
        
    except Exception as e:
        return {"success": False, "error": f"读取文件失败: {str(e)}"}
