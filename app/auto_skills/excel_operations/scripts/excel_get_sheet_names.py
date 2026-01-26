import openpyxl
import os
from typing import List

def excel_get_sheet_names(file_path: str) -> List[str]:
    """
    获取Excel文件中所有工作表的名称
    
    Args:
        file_path: Excel文件路径 (.xlsx 或 .xls)
        
    Returns:
        工作表名称列表
        
    Raises:
        FileNotFoundError: 当文件不存在时
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Excel文件不存在: {file_path}")
        
        # 加载工作簿
        workbook = openpyxl.load_workbook(file_path, read_only=True)
        
        # 获取所有工作表名称
        sheet_names = workbook.sheetnames
        
        # 关闭工作簿
        workbook.close()
        
        return sheet_names
        
    except Exception as e:
        raise Exception(f"获取Excel工作表名称失败: {str(e)}")