"""智能切块器（针对技术经验文档优化）"""

from typing import List
import re


def smart_chunk_experience(
    content: str,
    system_name: str,
    tags: List[str] = None,
    chunk_size: int = 400,
    chunk_overlap: int = 80
) -> List[str]:
    """智能切分经验内容"""
    if len(content) <= chunk_size:
        return [content]
    
    chunks = []
    current_pos = 0
    
    while current_pos < len(content):
        window_end = min(current_pos + chunk_size, len(content))
        window = content[current_pos:window_end]
        
        split_point = None
        
        # 1. 代码块边界
        code_block_match = re.search(r'\n```\s*$', window)
        if code_block_match:
            split_point = current_pos + code_block_match.end()
        
        # 2. 段落边界
        if split_point is None:
            paragraph_match = re.search(r'\n\n', window)
            if paragraph_match:
                split_point = current_pos + paragraph_match.end()
        
        # 3. 句子边界
        if split_point is None:
            sentence_match = re.search(r'[。！？.!?]\s*', window)
            if sentence_match:
                split_point = current_pos + sentence_match.end()
        
        # 4. 强制切分
        if split_point is None:
            split_point = window_end
        
        chunk = content[current_pos:split_point].strip()
        if chunk:
            chunks.append(chunk)
        
        current_pos = split_point - chunk_overlap
        if current_pos <= 0:
            current_pos = split_point
    
    return chunks
