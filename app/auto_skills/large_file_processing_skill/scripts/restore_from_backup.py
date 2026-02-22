from langchain_core.tools import tool
import os
import shutil
from typing import Dict, Any, List
from langchain.tools import tool


@tool
def restore_from_backup(file_path: str, backup_suffix: str = ".bak") -> Dict[str, Any]:
    """
    从备份恢复文件
    
    Args:
        file_path: 原始文件路径
        backup_suffix: 备份文件后缀，默认".bak"
        
    Returns:
        包含恢复结果的字典
    """
    try:
        backup_file = file_path + backup_suffix
        
        # 检查备份文件是否存在
        if not os.path.exists(backup_file):
            # 尝试其他可能的备份文件
            possible_backups = [
                file_path + ".backup",
                file_path + "_backup",
                file_path + ".old",
                os.path.join(os.path.dirname(file_path), "backup", os.path.basename(file_path)),
                os.path.join(os.path.dirname(file_path), os.path.basename(file_path) + backup_suffix)
            ]
            
            found_backup = None
            for backup in possible_backups:
                if os.path.exists(backup):
                    found_backup = backup
                    break
            
            if not found_backup:
                return {
                    "success": False,
                    "error": f"未找到备份文件。尝试了: {backup_file} 和其他常见备份位置",
                    "suggestion": "请手动指定备份文件路径，或从版本控制系统恢复"
                }
            
            backup_file = found_backup
        
        # 检查原始文件是否存在
        original_exists = os.path.exists(file_path)
        
        if original_exists:
            # 创建当前文件的备份（以防万一）
            current_backup = file_path + ".current_before_restore"
            shutil.copy2(file_path, current_backup)
        
        # 从备份恢复
        shutil.copy2(backup_file, file_path)
        
        # 获取文件信息
        backup_size = os.path.getsize(backup_file)
        if original_exists:
            original_size = os.path.getsize(current_backup)
        else:
            original_size = 0
        
        result = {
            "success": True,
            "action": "restored_from_backup",
            "original_file": file_path,
            "backup_file": backup_file,
            "backup_size": backup_size,
            "original_existed": original_exists,
            "message": f"成功从备份恢复文件: {backup_file} -> {file_path}"
        }
        
        if original_exists:
            result["current_backup"] = current_backup
            result["original_size"] = original_size
            result["size_change"] = backup_size - original_size
        
        # 验证恢复后的文件
        if os.path.exists(file_path):
            restored_size = os.path.getsize(file_path)
            if restored_size == backup_size:
                result["verification"] = "passed"
                result["verified_size"] = restored_size
            else:
                result["verification"] = "warning"
                result["verified_size"] = restored_size
                result["warning"] = f"恢复后文件大小 ({restored_size}) 与备份大小 ({backup_size}) 不一致"
        
        return result
        
    except PermissionError as e:
        return {
            "success": False,
            "error": f"权限错误: {str(e)}",
            "suggestion": "请检查文件是否被其他程序占用，或尝试以管理员权限运行"
        }
    except Exception as e:
        return {"success": False, "error": f"恢复文件失败: {str(e)}"}