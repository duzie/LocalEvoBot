from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, Optional
from .safe_file_backup import safe_file_backup

@tool
def merge_classes_into_file(target_file: str, class_content: str, insert_position: str = "end") -> Dict[str, Any]:
    """
    将类合并到目标文件中
    
    Args:
        target_file: 目标文件路径
        class_content: 要合并的类内容
        insert_position: 插入位置：after_last_class/beginning/end
        
    Returns:
        包含合并结果的字典
    """
    try:
        # 先创建备份
        backup_result = safe_file_backup(target_file)
        if not backup_result.get("success", False):
            return {
                "success": False,
                "error": f"备份失败: {backup_result.get('error', '未知错误')}",
                "backup_result": backup_result
            }
        
        # 读取目标文件内容（如果文件存在）
        original_content = ""
        file_exists = os.path.exists(target_file)
        
        if file_exists:
            with open(target_file, 'r', encoding='utf-8') as f:
                original_content = f.read()
        
        # 确定插入位置
        if insert_position == "beginning":
            # 在文件开头插入（在using语句之后）
            if file_exists:
                # 查找第一个非using语句的位置
                lines = original_content.split('\n')
                insert_index = 0
                for i, line in enumerate(lines):
                    if not line.strip().startswith('using ') and line.strip():
                        insert_index = i
                        break
                
                # 在指定位置插入
                new_lines = lines[:insert_index] + [''] + [class_content] + [''] + lines[insert_index:]
                new_content = '\n'.join(new_lines)
            else:
                new_content = class_content
                
        elif insert_position == "after_last_class":
            if not file_exists:
                new_content = class_content
            else:
                # 查找最后一个类的结束位置
                # 匹配类定义
                class_pattern = r'(public\s+|internal\s+|protected\s+|private\s+|abstract\s+|sealed\s+|static\s+)*class\s+\w+\b'
                class_matches = list(re.finditer(class_pattern, original_content))
                
                if class_matches:
                    # 找到最后一个类
                    last_class_match = class_matches[-1]
                    start_pos = last_class_match.start()
                    
                    # 查找这个类的结束位置
                    brace_count = 0
                    in_class = False
                    end_pos = start_pos
                    
                    for i in range(start_pos, len(original_content)):
                        char = original_content[i]
                        
                        if char == '{':
                            brace_count += 1
                            in_class = True
                        elif char == '}':
                            brace_count -= 1
                            
                            if in_class and brace_count == 0:
                                end_pos = i + 1  # 包含结束大括号
                                break
                    
                    # 在最后一个类之后插入
                    new_content = original_content[:end_pos] + '\n\n' + class_content + '\n' + original_content[end_pos:]
                else:
                    # 没有找到类，在文件末尾插入
                    new_content = original_content + '\n\n' + class_content
                    
        else:  # "end" 或默认
            # 在文件末尾插入
            if file_exists:
                # 确保末尾有换行
                if original_content and not original_content.endswith('\n'):
                    original_content += '\n'
                new_content = original_content + '\n' + class_content + '\n'
            else:
                new_content = class_content
        
        # 写入文件
        os.makedirs(os.path.dirname(target_file), exist_ok=True)
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 验证写入
        with open(target_file, 'r', encoding='utf-8') as f:
            written_content = f.read()
        
        # 检查类是否成功插入
        class_name_match = re.search(r'class\s+(\w+)', class_content)
        class_name = class_name_match.group(1) if class_name_match else "未知类"
        
        class_inserted = class_name in written_content if class_name != "未知类" else class_content in written_content
        
        return {
            "success": True,
            "message": f"类合并成功",
            "target_file": target_file,
            "class_name": class_name,
            "insert_position": insert_position,
            "file_existed": file_exists,
            "original_size": len(original_content) if file_exists else 0,
            "new_size": len(written_content),
            "class_inserted": class_inserted,
            "backup_path": backup_result.get("backup_path"),
            "operation": "merge"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"合并过程中发生错误: {str(e)}",
            "target_file": target_file,
            "backup_result": backup_result if 'backup_result' in locals() else None
        }