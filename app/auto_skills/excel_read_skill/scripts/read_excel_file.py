from langchain_core.tools import tool
import pandas as pd
import os
from typing import Dict, List, Any, Optional
import json


@tool
def read_excel_file(
    file_path: str,
    sheet_name: Optional[str] = None,
    max_rows: int = 50,
    include_header: bool = True
) -> Dict[str, Any]:
    """
    读取Excel文件内容，返回工作表名称和数据
    
    Args:
        file_path: Excel文件路径
        sheet_name: 工作表名称，如果不指定则读取第一个工作表
        max_rows: 最大读取行数
        include_header: 是否包含表头
        
    Returns:
        包含文件信息和数据的字典
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"文件不存在: {file_path}",
                "file_path": file_path
            }
        
        # 获取文件信息
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 读取Excel文件
        if sheet_name:
            # 读取指定工作表
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, nrows=max_rows)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"读取工作表 '{sheet_name}' 失败: {str(e)}",
                    "file_path": file_path,
                    "available_sheets": get_excel_sheets(file_path)
                }
        else:
            # 读取第一个工作表
            try:
                df = pd.read_excel(file_path, nrows=max_rows)
                # 获取工作表名称
                xls = pd.ExcelFile(file_path)
                sheet_name = xls.sheet_names[0]
            except Exception as e:
                return {
                    "success": False,
                    "error": f"读取Excel文件失败: {str(e)}",
                    "file_path": file_path
                }
        
        # 获取所有工作表名称
        all_sheets = get_excel_sheets(file_path)
        
        # 处理数据
        if include_header:
            # 包含表头，转换为列表格式
            data = df.to_dict(orient='records')
            headers = list(df.columns)
        else:
            # 不包含表头，只返回数据值
            data = df.values.tolist()
            headers = []
        
        # 获取数据统计信息
        shape = df.shape
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}
        
        # 获取前几行数据预览
        preview_rows = min(5, len(data))
        preview = data[:preview_rows] if data else []
        
        return {
            "success": True,
            "file_path": file_path,
            "file_size": file_size,
            "file_extension": file_ext,
            "sheet_name": sheet_name,
            "all_sheets": all_sheets,
            "total_rows": shape[0],
            "total_columns": shape[1],
            "headers": headers,
            "data_types": dtypes,
            "data_preview": preview,
            "total_data_rows": len(data),
            "max_rows_read": max_rows,
            "data": data if len(data) <= 20 else data[:20]  # 限制返回的数据量
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"读取Excel文件时发生错误: {str(e)}",
            "file_path": file_path
        }


def get_excel_sheets(file_path: str) -> List[str]:
    """获取Excel文件中的所有工作表名称"""
    try:
        xls = pd.ExcelFile(file_path)
        return xls.sheet_names
    except:
        return []


if __name__ == "__main__":
    # 测试代码
    result = read_excel_file("test.xlsx")
    print(json.dumps(result, ensure_ascii=False, indent=2))