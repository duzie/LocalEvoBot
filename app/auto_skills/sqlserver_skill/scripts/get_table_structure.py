from langchain_core.tools import tool
import pyodbc
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
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

def _get_connection():
    """获取全局数据库连接"""
    # 这里需要从全局状态获取连接信息
    # 暂时使用硬编码的连接信息，后续可以改进
    try:
        # 导入连接管理器
        try:
            from .sqlserver_manager import get_connection as get_sqlserver_connection
            return get_sqlserver_connection()
        except ImportError:
            # 如果导入失败，使用旧的硬编码方式
            import pyodbc
            server = ".\\SQLEXPRESS"
            database = "CanyinSimple"
            username = "sa"
            password = "sa"
            
            conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
            return pyodbc.connect(conn_str)
    except Exception as e:
        raise Exception(f"数据库连接失败: {e}")

@tool
def get_table_structure(table_name: str):
    """
    获取表结构信息
    Args:
        table_name: 表名
    """
    tool_name = "get_table_structure"
    try:
        _emit_event(tool_name, "start", table_name=table_name)
        
        if not table_name:
            return _error_payload("missing_param", "表名不能为空", tool=tool_name)
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # 获取表的基本信息
        cursor.execute("""
            SELECT 
                t.TABLE_NAME,
                t.TABLE_TYPE,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT,
                CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS IS_PRIMARY_KEY
            FROM INFORMATION_SCHEMA.TABLES t
            LEFT JOIN INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME
            LEFT JOIN (
                SELECT 
                    ku.TABLE_NAME,
                    ku.COLUMN_NAME
                FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
            ) pk ON t.TABLE_NAME = pk.TABLE_NAME AND c.COLUMN_NAME = pk.COLUMN_NAME
            WHERE t.TABLE_NAME = ?
            ORDER BY c.ORDINAL_POSITION
        """, table_name)
        
        columns = cursor.fetchall()
        
        if not columns:
            return _error_payload("table_not_found", f"表 '{table_name}' 不存在", tool=tool_name)
        
        # 获取索引信息
        cursor.execute("""
            SELECT 
                i.name AS INDEX_NAME,
                ic.key_ordinal AS ORDINAL_POSITION,
                c.name AS COLUMN_NAME,
                i.is_unique AS IS_UNIQUE,
                i.type_desc AS INDEX_TYPE
            FROM sys.indexes i
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            JOIN sys.tables t ON i.object_id = t.object_id
            WHERE t.name = ? AND i.is_primary_key = 0
            ORDER BY i.name, ic.key_ordinal
        """, table_name)
        
        indexes = cursor.fetchall()
        
        # 获取外键信息
        cursor.execute("""
            SELECT 
                fk.name AS CONSTRAINT_NAME,
                OBJECT_NAME(fk.parent_object_id) AS TABLE_NAME,
                COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS COLUMN_NAME,
                OBJECT_NAME(fk.referenced_object_id) AS REFERENCED_TABLE,
                COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REFERENCED_COLUMN
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            WHERE OBJECT_NAME(fk.parent_object_id) = ?
            ORDER BY fk.name, fkc.constraint_column_id
        """, table_name)
        
        foreign_keys = cursor.fetchall()
        
        # 组织结果
        table_info = {
            "table_name": columns[0][0],
            "table_type": columns[0][1],
            "columns": [],
            "indexes": [],
            "foreign_keys": []
        }
        
        # 处理列信息
        for col in columns:
            column_info = {
                "name": col[2],
                "data_type": col[3],
                "max_length": col[4],
                "is_nullable": col[5] == "YES",
                "default_value": col[6],
                "is_primary_key": bool(col[7])
            }
            table_info["columns"].append(column_info)
        
        # 处理索引信息
        current_index = None
        for idx in indexes:
            if current_index is None or current_index["name"] != idx[0]:
                if current_index is not None:
                    table_info["indexes"].append(current_index)
                current_index = {
                    "name": idx[0],
                    "is_unique": bool(idx[3]),
                    "type": idx[4],
                    "columns": []
                }
            current_index["columns"].append(idx[2])
        
        if current_index is not None:
            table_info["indexes"].append(current_index)
        
        # 处理外键信息
        current_fk = None
        for fk in foreign_keys:
            if current_fk is None or current_fk["name"] != fk[0]:
                if current_fk is not None:
                    table_info["foreign_keys"].append(current_fk)
                current_fk = {
                    "name": fk[0],
                    "columns": [],
                    "referenced_table": fk[3],
                    "referenced_columns": []
                }
            current_fk["columns"].append(fk[2])
            current_fk["referenced_columns"].append(fk[4])
        
        if current_fk is not None:
            table_info["foreign_keys"].append(current_fk)
        
        result = _ok_payload(
            f"成功获取表 '{table_name}' 的结构信息",
            table_structure=table_info,
            column_count=len(table_info["columns"]),
            index_count=len(table_info["indexes"]),
            fk_count=len(table_info["foreign_keys"])
        )
        return result
        
    except Exception as e:
        return _error_payload("execution_error", str(e), tool=tool_name)
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass
