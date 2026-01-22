from langchain_core.tools import tool
import os
import shutil
import glob

@tool
def file_organize(source_dir: str, target_dir: str, file_extension: str):
    """
    整理文件：将源文件夹中指定后缀名的文件移动到目标文件夹。
    
    Args:
        source_dir: 源文件夹路径 (例如 "Desktop")
        target_dir: 目标文件夹路径 (例如 "D:/screenshots")
        file_extension: 文件后缀名，不带点 (例如 "png", "txt")
    """
    if source_dir.lower() == "desktop" or source_dir.lower() == "桌面":
        source_dir = os.path.join(os.path.expanduser("~"), "Desktop")
    
    if not os.path.exists(source_dir):
        return f"错误: 源目录不存在 {source_dir}"

    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
        except Exception as e:
            return f"错误: 无法创建目标目录 {target_dir}: {e}"
            
    try:
        pattern = os.path.join(source_dir, f"*.{file_extension}")
        files = glob.glob(pattern)
        
        if not files:
            return f"在 {source_dir} 未找到 .{file_extension} 文件。"
            
        moved_count = 0
        for file_path in files:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(target_dir, file_name)
            shutil.move(file_path, dest_path)
            moved_count += 1
            
        return f"成功整理完成。已将 {moved_count} 个 .{file_extension} 文件从 {source_dir} 移动到 {target_dir}。"
        
    except Exception as e:
        return f"文件整理失败: {e}"
