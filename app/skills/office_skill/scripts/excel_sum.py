from langchain_core.tools import tool
import pandas as pd
import os

@tool
def excel_sum(file_path: str, column_name: str, save_path: str = None):
    """
    读取 Excel 文件，计算指定列的总和，并可选地保存结果。
    
    Args:
        file_path: Excel 文件路径 (.xlsx 或 .xls)
        column_name: 需要求和的列名 (A列对应第一列，如果列有标题，请直接提供标题名称；如果没有标题，这可能需要调整)
                     注：为简化，这里假设提供的是列标题（Header）。
        save_path: (可选) 结果保存路径。如果是目录，会生成一个 summary.txt。如果是文件路径，直接写入。
    """
    if not os.path.exists(file_path):
        return f"错误: 文件未找到 {file_path}"
    
    try:
        df = pd.read_excel(file_path)
        
        if column_name in df.columns:
            total = df[column_name].sum()
        else:
            col_idx = -1
            if len(column_name) == 1 and column_name.upper() >= 'A' and column_name.upper() <= 'Z':
                col_idx = ord(column_name.upper()) - ord('A')
            
            if col_idx >= 0 and col_idx < len(df.columns):
                total = df.iloc[:, col_idx].sum()
            else:
                return f"错误: 找不到列名 '{column_name}'，且无法解析为有效的列索引。"

        result_msg = f"文件 {os.path.basename(file_path)} 中 '{column_name}' 列的总和为: {total}"
        
        if save_path:
            if os.path.isdir(save_path):
                final_save_path = os.path.join(save_path, "summary.txt")
            else:
                final_save_path = save_path
            
            os.makedirs(os.path.dirname(os.path.abspath(final_save_path)), exist_ok=True)
            
            with open(final_save_path, "w", encoding="utf-8") as f:
                f.write(result_msg)
            
            return f"{result_msg}\n结果已保存至: {final_save_path}"
            
        return result_msg

    except Exception as e:
        return f"Excel 处理失败: {e}"
