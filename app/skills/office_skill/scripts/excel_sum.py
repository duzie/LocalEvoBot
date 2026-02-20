from langchain_core.tools import tool
import pandas as pd
import os
import json
from datetime import datetime
from typing import Any, Dict
from web.backend.shared import shared

def _error_payload(code: str, message: str, **fields) -> Dict[str, Any]:
    info = {"code": str(code or "error"), "message": str(message or "")}
    payload: Dict[str, Any] = {"ok": False, "error": info["message"], "error_info": info}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _ok_payload(message: str = "", **fields) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"ok": True}
    if message:
        payload["message"] = str(message)
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    return payload

def _emit_event(tool_name: str, event: str, **fields):
    payload = {"event": str(event or ""), "tool": str(tool_name or ""), "time": datetime.now().isoformat()}
    for k, v in (fields or {}).items():
        if v is None:
            continue
        payload[str(k)] = v
    shared.broadcast_threadsafe(json.dumps(payload, ensure_ascii=False))

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
    tool_name = "excel_sum"
    if not file_path or not column_name:
        return _error_payload("invalid_args", "file_path 与 column_name 不能为空", tool=tool_name)
    if not os.path.exists(file_path):
        return _error_payload("file_not_found", f"文件未找到 {file_path}", tool=tool_name, file_path=file_path)
    
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
                return _error_payload("column_not_found", f"找不到列名 '{column_name}'，且无法解析为有效的列索引。", tool=tool_name, column_name=column_name)

        result_msg = f"文件 {os.path.basename(file_path)} 中 '{column_name}' 列的总和为: {total}"
        
        if save_path:
            if os.path.isdir(save_path):
                final_save_path = os.path.join(save_path, "summary.txt")
            else:
                final_save_path = save_path
            
            os.makedirs(os.path.dirname(os.path.abspath(final_save_path)), exist_ok=True)
            
            with open(final_save_path, "w", encoding="utf-8") as f:
                f.write(result_msg)
            
            _emit_event(tool_name, "sum_saved", file_path=file_path, column_name=column_name, save_path=final_save_path)
            return _ok_payload("求和完成并已保存", total=total, file_path=file_path, column_name=column_name, save_path=final_save_path)
            
        _emit_event(tool_name, "sum", file_path=file_path, column_name=column_name)
        return _ok_payload("求和完成", total=total, file_path=file_path, column_name=column_name)

    except Exception as e:
        _emit_event(tool_name, "error", error=str(e))
        return _error_payload("excel_sum_failed", str(e), tool=tool_name)
