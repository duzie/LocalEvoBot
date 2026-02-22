from langchain_core.tools import tool
import os
import re
from typing import Dict, Any, Optional
from langchain.tools import tool


@tool
def extract_and_merge_class(source_file: str, target_file: str, class_name: str, 
                           insert_position: str = "end") -> Dict[str, Any]:
    """
    从源文件提取类并安全合并到目标文件
    
    Args:
        source_file: 源文件路径
        target_file: 目标文件路径
        class_name: 要提取的类名
        insert_position: 插入位置，默认"end"
        
    Returns:
        包含操作结果的字典
    """
    try:
        # 检查源文件是否存在
        if not os.path.exists(source_file):
            return {"success": False, "error": f"源文件不存在: {source_file}"}
        
        # 读取源文件内容
        with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
            source_content = f.read()
        
        # 提取指定类
        # C#类模式：public class ClassName { ... }
        class_pattern = rf'(public\s+class\s+{re.escape(class_name)}\s*{{.*?}})(?=\s*(?:public\s+class|$))'
        
        # 使用多行模式匹配
        match = re.search(class_pattern, source_content, re.DOTALL | re.MULTILINE)
        
        if not match:
            # 尝试其他可能的类定义格式
            alt_patterns = [
                rf'class\s+{re.escape(class_name)}\s*{{.*?}}(?=\s*(?:class|$))',
                rf'public\s+partial\s+class\s+{re.escape(class_name)}\s*{{.*?}}(?=\s*(?:public|class|$))',
                rf'sealed\s+class\s+{re.escape(class_name)}\s*{{.*?}}(?=\s*(?:sealed|class|$))'
            ]
            
            for pattern in alt_patterns:
                match = re.search(pattern, source_content, re.DOTALL | re.MULTILINE)
                if match:
                    break
        
        if not match:
            return {
                "success": False, 
                "error": f"在源文件中未找到类: {class_name}",
                "suggestion": "请检查类名是否正确，或类定义格式是否标准"
            }
        
        class_content = match.group(1)
        
        # 提取相关的using语句
        using_pattern = r'using\s+[^;]+;'
        all_usings = re.findall(using_pattern, source_content)
        
        # 去重并排序
        unique_usings = sorted(set(all_usings))
        
        # 构建完整内容（包含必要的using语句）
        full_content = ""
        if unique_usings:
            full_content = "\n".join(unique_usings) + "\n\n"
        full_content += class_content
        
        # 使用safe_file_merge工具合并到目标文件
        # 这里需要导入safe_file_merge，但由于工具隔离，我们直接调用逻辑
        # 简化实现：直接调用safe_file_merge的逻辑
        
        # 检查目标文件是否存在
        if not os.path.exists(target_file):
            # 如果文件不存在，直接创建
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(full_content)
            
            return {
                "success": True,
                "action": "created_new_file_with_class",
                "source_file": source_file,
                "target_file": target_file,
                "class_name": class_name,
                "class_size": len(class_content),
                "total_size": len(full_content),
                "message": f"目标文件不存在，已创建新文件并添加类 {class_name}"
            }
        
        # 读取目标文件内容
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            target_content = f.read()
        
        # 检查目标文件中是否已存在该类
        if re.search(rf'class\s+{re.escape(class_name)}\b', target_content):
            return {
                "success": False,
                "error": f"目标文件中已存在类: {class_name}",
                "suggestion": "请先删除或重命名目标文件中的同名类"
            }
        
        # 根据插入位置合并
        if insert_position == "beginning":
            merged_content = full_content + "\n\n" + target_content
        elif insert_position == "end":
            merged_content = target_content + "\n\n" + full_content
        elif insert_position == "after_last_class":
            # 查找最后一个类定义的结束位置
            lines = target_content.split('\n')
            last_class_end = len(lines)
            
            # 查找最后一个"}"的位置
            for i in range(len(lines) - 1, -1, -1):
                if lines[i].strip() == "}":
                    last_class_end = i + 1
                    break
            
            # 在最后一个类之后插入
            before = '\n'.join(lines[:last_class_end])
            after = '\n'.join(lines[last_class_end:])
            merged_content = before + "\n\n" + full_content + "\n" + after
        else:
            return {
                "success": False,
                "error": f"不支持的插入位置: {insert_position}"
            }
        
        # 创建备份
        backup_file = target_file + ".bak"
        import shutil
        shutil.copy2(target_file, backup_file)
        
        # 写入合并后的内容
        with open(target_file, 'w', encoding='utf-8') as f:
            f.write(merged_content)
        
        return {
            "success": True,
            "action": "extracted_and_merged",
            "source_file": source_file,
            "target_file": target_file,
            "class_name": class_name,
            "class_size": len(class_content),
            "total_size": len(merged_content),
            "backup_file": backup_file,
            "insert_position": insert_position,
            "message": f"成功从 {source_file} 提取类 {class_name} 并合并到 {target_file}"
        }
        
    except Exception as e:
        return {"success": False, "error": f"提取合并类失败: {str(e)}"}