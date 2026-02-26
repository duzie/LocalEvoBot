from langchain_core.tools import tool
import os
import shutil
from typing import Dict, Any


@tool
def truncate_incomplete_tail(file_path: str, backup_suffix: str = ".bak", ensure_newline: bool = True) -> Dict[str, Any]:
    """
    截断文件末尾的未完整行，避免半行导致编译错误。
    """
    try:
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}

        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        if not content:
            return {
                "success": True,
                "message": "文件为空，无需截断",
                "file_path": file_path,
                "backup_file": backup_file,
                "truncated": False,
                "original_size": 0,
                "new_size": 0
            }

        if content.endswith("\n"):
            return {
                "success": True,
                "message": "末尾已完整，无需截断",
                "file_path": file_path,
                "backup_file": backup_file,
                "truncated": False,
                "original_size": len(content),
                "new_size": len(content)
            }

        last_newline = content.rfind("\n")
        if last_newline == -1:
            return {
                "success": False,
                "error": "未找到换行，无法安全截断",
                "file_path": file_path,
                "backup_file": backup_file
            }

        new_content = content[:last_newline + 1] if ensure_newline else content[:last_newline]
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return {
            "success": True,
            "message": "已截断未完整末尾行",
            "file_path": file_path,
            "backup_file": backup_file,
            "truncated": True,
            "original_size": len(content),
            "new_size": len(new_content)
        }
    except Exception as e:
        return {"success": False, "error": f"截断失败: {str(e)}"}
