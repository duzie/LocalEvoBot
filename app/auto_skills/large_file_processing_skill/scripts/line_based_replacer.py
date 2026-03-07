from langchain_core.tools import tool
import os
import shutil
from typing import Dict, Any


@tool
def replace_lines(
    file_path: str,
    new_content: str,
    start_line: int,
    end_line: int = 0,
    backup_suffix: str = ".bak",
    ensure_present: bool = True,
    skip_if_present: bool = True
) -> Dict[str, Any]:
    """
    按行号替换内容 - 最简单可靠的方案
    
    Args:
        file_path: 目标文件路径
        new_content: 新内容
        start_line: 起始行号（从1开始）
        end_line: 结束行号（从1开始），如果等于start_line则只替换该行
        backup_suffix: 备份文件后缀
        ensure_present: 写入后校验内容是否存在
        skip_if_present: 内容已存在则跳过
    
    Returns:
        操作结果字典
    """
    try:
        # 基础验证
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}
        if not new_content:
            return {"success": False, "error": "new_content 不能为空"}
        if start_line < 1:
            return {"success": False, "error": f"start_line 必须 >= 1, 当前值: {start_line}"}
        
        encoding = "utf-8"
        
        # 读取文件获取总行数
        total_lines = 0
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            lines = f.readlines()
            total_lines = len(lines)
        
        # 校验行号范围
        if start_line > total_lines:
            return {
                "success": False,
                "error": f"start_line ({start_line}) 超出文件范围 (1-{total_lines})"
            }
        
        # 默认 end_line 等于 start_line（只替换一行）
        if end_line < 1:
            end_line = start_line
        
        # 确保 start_line <= end_line
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        
        # 校验 end_line
        if end_line > total_lines:
            end_line = total_lines
        
        # 内容已存在则跳过
        if skip_if_present and new_content in "".join(lines):
            return {
                "success": True,
                "message": "内容已存在，已跳过",
                "file_path": file_path,
                "skipped": True
            }
        
        # 创建备份
        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)
        
        # 创建临时文件
        tmp_file = file_path + ".tmp"
        inserted = False
        
        with open(tmp_file, "w", encoding=encoding) as dst:
            for i, line in enumerate(lines, 1):
                if i < start_line:
                    dst.write(line)
                elif i == start_line:
                    # 写入新内容
                    dst.write(new_content)
                    if not new_content.endswith("\n"):
                        dst.write("\n")
                    inserted = True
                    # 跳过中间行
                    if start_line != end_line:
                        continue
                elif i <= end_line:
                    # 跳过被替换的行
                    continue
                else:
                    dst.write(line)
        
        # 校验结果
        if ensure_present:
            with open(file_path, "r", encoding=encoding, errors="ignore") as f:
                content = f.read()
                if new_content not in content:
                    shutil.copy2(backup_file, file_path)
                    if os.path.exists(tmp_file):
                        os.remove(tmp_file)
                    return {
                        "success": False,
                        "error": "内容校验失败，已回滚",
                        "backup_file": backup_file
                    }
        
        # 替换文件
        os.replace(tmp_file, file_path)
        
        # 返回结果
        original_size = os.path.getsize(backup_file)
        new_size = os.path.getsize(file_path)
        
        return {
            "success": True,
            "message": "已按行号替换内容",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": original_size,
            "new_size": new_size,
            "replaced_range": [start_line, end_line],
            "total_lines": total_lines
        }
        
    except Exception as e:
        return {"success": False, "error": f"替换失败: {str(e)}"}


@tool
def insert_lines(
    file_path: str,
    new_content: str,
    line_number: int,
    backup_suffix: str = ".bak",
    ensure_present: bool = True,
    skip_if_present: bool = True
) -> Dict[str, Any]:
    """
    在指定行号前插入内容 - 最简单可靠的方案
    
    Args:
        file_path: 目标文件路径
        new_content: 要插入的新内容
        line_number: 插入位置的行号（从1开始，新内容会插入到该行之前）
        backup_suffix: 备份文件后缀
        ensure_present: 写入后校验内容是否存在
        skip_if_present: 内容已存在则跳过
    
    Returns:
        操作结果字典
    """
    try:
        # 基础验证
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}
        if not new_content:
            return {"success": False, "error": "new_content 不能为空"}
        if line_number < 1:
            return {"success": False, "error": f"line_number 必须 >= 1, 当前值: {line_number}"}
        
        encoding = "utf-8"
        
        # 读取文件
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 校验行号
        if line_number > total_lines + 1:
            return {
                "success": False,
                "error": f"line_number ({line_number}) 超出文件范围 (1-{total_lines + 1})"
            }
        
        # 内容已存在则跳过
        if skip_if_present and new_content in "".join(lines):
            return {
                "success": True,
                "message": "内容已存在，已跳过",
                "file_path": file_path,
                "skipped": True
            }
        
        # 创建备份
        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)
        
        # 创建临时文件
        tmp_file = file_path + ".tmp"
        inserted = False
        
        with open(tmp_file, "w", encoding=encoding) as dst:
            for i, line in enumerate(lines, 1):
                if i == line_number:
                    # 插入新内容
                    dst.write(new_content)
                    if not new_content.endswith("\n"):
                        dst.write("\n")
                    inserted = True
                
                dst.write(line)
            
            # 如果 line_number 超出范围，在末尾插入
            if line_number > total_lines:
                dst.write(new_content)
                if not new_content.endswith("\n"):
                    dst.write("\n")
                inserted = True
        
        # 校验结果
        if ensure_present:
            with open(file_path, "r", encoding=encoding, errors="ignore") as f:
                content = f.read()
                if new_content not in content:
                    shutil.copy2(backup_file, file_path)
                    if os.path.exists(tmp_file):
                        os.remove(tmp_file)
                    return {
                        "success": False,
                        "error": "内容校验失败，已回滚",
                        "backup_file": backup_file
                    }
        
        # 替换文件
        os.replace(tmp_file, file_path)
        
        # 返回结果
        original_size = os.path.getsize(backup_file)
        new_size = os.path.getsize(file_path)
        
        return {
            "success": True,
            "message": "已插入内容",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": original_size,
            "new_size": new_size,
            "inserted_at": line_number,
            "total_lines": total_lines
        }
        
    except Exception as e:
        return {"success": False, "error": f"插入失败: {str(e)}"}


@tool
def delete_lines(
    file_path: str,
    start_line: int,
    end_line: int = 0,
    backup_suffix: str = ".bak",
    ensure_removed: bool = True
) -> Dict[str, Any]:
    """
    删除指定行号范围的内容 - 最简单可靠的方案
    
    Args:
        file_path: 目标文件路径
        start_line: 起始行号（从1开始）
        end_line: 结束行号（从1开始），如果等于start_line则只删除该行
        backup_suffix: 备份文件后缀
        ensure_removed: 删除后校验内容是否已移除
    
    Returns:
        操作结果字典
    """
    try:
        # 基础验证
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}
        if start_line < 1:
            return {"success": False, "error": f"start_line 必须 >= 1, 当前值: {start_line}"}
        
        encoding = "utf-8"
        
        # 读取文件
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # 校验行号
        if start_line > total_lines:
            return {
                "success": False,
                "error": f"start_line ({start_line}) 超出文件范围 (1-{total_lines})"
            }
        
        # 默认 end_line 等于 start_line
        if end_line < 1:
            end_line = start_line
        
        # 确保 start_line <= end_line
        if start_line > end_line:
            start_line, end_line = end_line, start_line
        
        # 校验 end_line
        if end_line > total_lines:
            end_line = total_lines
        
        # 创建备份
        backup_file = file_path + backup_suffix
        shutil.copy2(file_path, backup_file)
        
        # 创建临时文件
        tmp_file = file_path + ".tmp"
        deleted = False
        deleted_count = 0
        
        with open(tmp_file, "w", encoding=encoding) as dst:
            for i, line in enumerate(lines, 1):
                if i >= start_line and i <= end_line:
                    deleted = True
                    deleted_count += 1
                    continue
                dst.write(line)
        
        # 校验结果
        if ensure_removed and not deleted:
            shutil.copy2(backup_file, file_path)
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
            return {
                "success": False,
                "error": "删除操作未执行，已回滚"
            }
        
        # 替换文件
        os.replace(tmp_file, file_path)
        
        # 返回结果
        original_size = os.path.getsize(backup_file)
        new_size = os.path.getsize(file_path)
        
        return {
            "success": True,
            "message": f"已删除 {deleted_count} 行内容",
            "file_path": file_path,
            "backup_file": backup_file,
            "original_size": original_size,
            "new_size": new_size,
            "deleted_range": [start_line, end_line],
            "deleted_count": deleted_count,
            "total_lines": total_lines
        }
        
    except Exception as e:
        return {"success": False, "error": f"删除失败: {str(e)}"}


@tool
def get_line_content(
    file_path: str,
    line_number: int,
    context_lines: int = 0
) -> Dict[str, Any]:
    """
    获取指定行号的内容 - 用于确认行号
    
    Args:
        file_path: 目标文件路径
        line_number: 要获取的行号（从1开始）
        context_lines: 上下文行数（前后各多少行）
    
    Returns:
        包含行内容的字典
    """
    try:
        if not file_path:
            return {"success": False, "error": "file_path 不能为空"}
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        if not os.path.isfile(file_path):
            return {"success": False, "error": f"路径不是文件: {file_path}"}
        if line_number < 1:
            return {"success": False, "error": f"line_number 必须 >= 1, 当前值: {line_number}"}
        
        encoding = "utf-8"
        
        with open(file_path, "r", encoding=encoding, errors="ignore") as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        if line_number > total_lines:
            return {
                "success": False,
                "error": f"line_number ({line_number}) 超出文件范围 (1-{total_lines})"
            }
        
        # 计算上下文范围
        start = max(0, line_number - 1 - context_lines)
        end = min(total_lines, line_number + context_lines)
        
        # 提取内容
        context_lines_list = []
        for i in range(start, end):
            line_num = i + 1
            marker = " <--" if line_num == line_number else ""
            context_lines_list.append(f"{line_num:6d}: {lines[i].rstrip()}{marker}")
        
        return {
            "success": True,
            "file_path": file_path,
            "line_number": line_number,
            "total_lines": total_lines,
            "content": lines[line_number - 1].rstrip(),
            "context": "\n".join(context_lines_list)
        }
        
    except Exception as e:
        return {"success": False, "error": f"获取行内容失败: {str(e)}"}
