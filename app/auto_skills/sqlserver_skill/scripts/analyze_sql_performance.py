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
def analyze_sql_performance(sql: str):
    """
    分析SQL性能，获取执行计划
    Args:
        sql: SQL语句
    """
    tool_name = "analyze_sql_performance"
    conn = None
    cursor = None
    try:
        _emit_event(tool_name, "start", sql_preview=sql[:100] + "..." if len(sql) > 100 else sql)
        
        if not sql:
            return _error_payload("missing_param", "SQL语句不能为空", tool=tool_name)
        
        conn = _get_connection()
        cursor = conn.cursor()
        
        # 设置统计信息
        cursor.execute("SET STATISTICS TIME ON")
        cursor.execute("SET STATISTICS IO ON")
        
        # 获取执行计划
        execution_plan_sql = f"SET SHOWPLAN_XML ON; {sql}; SET SHOWPLAN_XML OFF;"
        
        try:
            # 尝试获取XML执行计划
            cursor.execute("SET SHOWPLAN_XML ON")
            cursor.execute(sql)
            plan_result = cursor.fetchall()
            cursor.execute("SET SHOWPLAN_XML OFF")
            
            # 提取执行计划XML
            execution_plan = ""
            if plan_result:
                for row in plan_result:
                    if row and row[0]:
                        execution_plan = str(row[0])
                        break
        except:
            # 如果SHOWPLAN_XML失败，尝试其他方法
            execution_plan = "无法获取XML执行计划"
        
        # 执行SQL并获取统计信息
        cursor.execute("SET STATISTICS TIME OFF")
        cursor.execute("SET STATISTICS IO OFF")
        
        return _ok_payload(
            "分析完成",
            tool=tool_name,
            execution_plan=execution_plan
        )
        
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
