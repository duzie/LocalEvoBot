from langchain_core.tools import tool
import os
import json
from pathlib import Path
from app.skills.common import SkillException, ok_payload

@tool
def save_document(file_path: str, content: str = "", max_chars: int = 9000):
    """
    保存文档到指定路径
    
    Args:
        file_path: 文件保存路径
        content: (可选) 文档内容，默认为空字符串
    
    Returns:
        包含操作结果的字典
    """
    if content is None:
        content = ""
    # max_len = max(1000, int(max_chars or 9000))
    # if len(content) > max_len:
    #     raise SkillException(
    #         "content_too_large",
    #         "内容过大，禁止一次性写入",
    #         max_chars=max_len,
    #         content_length=len(content),
    #         suggestion="请分段写入（safe_file_merge/insert_text_at_line），并逐段校验文件大小"
    #     )
        
    # 确保目录存在
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    
    # 保存文件
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        raise SkillException("io_error", f"文档保存失败: {str(e)}")
    
    # 获取文件信息
    file_size = os.path.getsize(file_path)
    
    return ok_payload(
        "文档保存成功",
        file_path=file_path,
        file_size=file_size,
        file_size_human=f"{file_size} bytes",
        created_time=os.path.getctime(file_path),
        modified_time=os.path.getmtime(file_path)
    )
