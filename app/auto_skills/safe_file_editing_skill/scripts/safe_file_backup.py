from langchain_core.tools import tool
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any
import json

@tool
def safe_file_backup(file_path: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    创建文件的安全备份
    
    Args:
        file_path: 需要备份的文件路径
        backup_dir: 备份目录，默认在文件同目录创建.bak文件
        
    Returns:
        包含备份信息的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "backup_path": None
            }
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        # 确定备份路径
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)
            filename = os.path.basename(file_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{os.path.splitext(filename)[0]}_{timestamp}.bak"
            backup_path = os.path.join(backup_dir, backup_filename)
        else:
            # 在同目录创建.bak文件
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{file_path}.{timestamp}.bak"
        
        # 创建备份
        shutil.copy2(file_path, backup_path)
        
        # 验证备份
        if os.path.exists(backup_path) and os.path.getsize(backup_path) == file_size:
            return {
                "success": True,
                "message": f"文件备份成功",
                "original_file": file_path,
                "backup_path": backup_path,
                "file_size": file_size,
                "modified_time": modified_time.isoformat(),
                "backup_time": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "error": "备份文件验证失败",
                "original_file": file_path,
                "backup_path": backup_path
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"备份过程中发生错误: {str(e)}",
            "original_file": file_path
        }