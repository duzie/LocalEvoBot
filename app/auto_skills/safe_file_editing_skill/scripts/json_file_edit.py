from langchain_core.tools import tool
import os
import json
import shutil
from typing import Dict, Any, List

@tool
def json_file_edit(
    file_path: str,
    updates: Dict[str, Any],
    create_backup: bool = True
) -> Dict[str, Any]:
    """
    对 JSON 文件进行结构化修改（非正则替换）。
    支持嵌套键更新（使用点号分隔，如 "a.b.c"）。
    
    Args:
        file_path: JSON 文件路径
        updates: 要更新的键值对字典。值可以是任何 JSON 支持的类型。
                 如果值为 null (None)，则删除该键。
                 键支持点号分隔路径，如 "server.port" 将更新 {"server": {"port": ...}}
        create_backup: 是否创建备份
    """
    try:
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
            
        # 读取文件
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON 解析失败: {e}"}
            
        # 创建备份
        if create_backup:
            shutil.copy2(file_path, file_path + ".bak")
            
        # 应用更新
        modified_keys = []
        
        for key_path, value in updates.items():
            keys = key_path.split('.')
            current = data
            
            # 遍历到倒数第二个键
            for i, key in enumerate(keys[:-1]):
                if key not in current:
                    current[key] = {}
                current = current[key]
                if not isinstance(current, dict):
                    return {"success": False, "error": f"路径冲突: '{'.'.join(keys[:i+1])}' 不是字典"}
            
            last_key = keys[-1]
            
            if value is None:
                # 删除键
                if last_key in current:
                    del current[last_key]
                    modified_keys.append(f"deleted: {key_path}")
            else:
                # 更新/新增键
                current[last_key] = value
                modified_keys.append(f"updated: {key_path}")
                
        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return {
            "success": True,
            "message": "JSON 文件更新成功",
            "modified_keys": modified_keys
        }
        
    except Exception as e:
        return {"success": False, "error": f"执行出错: {str(e)}"}
