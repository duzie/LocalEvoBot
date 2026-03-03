from langchain_core.tools import tool
import pyodbc
import json
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime

# 导入连接管理器
try:
    from .sqlserver_manager import get_connection
except ImportError:
    # 如果导入失败，使用旧的硬编码方式
    def get_connection():
        import pyodbc
        server = ".\\SQLEXPRESS"
        database = "CanyinSimple"
        username = "sa"
        password = "sa"
        
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
        return pyodbc.connect(conn_str)

@tool
def execute_sql_query(sql: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    执行SQL查询并返回结果
    
    Args:
        sql: SQL查询语句
        params: 查询参数（可选）
        
    Returns:
        包含查询结果和统计信息的字典
    """
    conn = None
    cursor = None
    try:
        # 建立连接
        conn = get_connection()
        cursor = conn.cursor()
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 执行SQL
        if params:
            # 如果有参数，使用参数化查询
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # 获取结果
        if cursor.description:
            # 查询语句，有返回结果
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            
            # 转换为字典列表
            results = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # 处理特殊类型
                    if isinstance(value, datetime):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif value is None:
                        value = None
                    row_dict[col] = value
                results.append(row_dict)
            
            # 统计信息
            row_count = len(results)
            
            return {
                "success": True,
                "message": f"查询成功，返回 {row_count} 行数据",
                "sql": sql,
                "params": params,
                "columns": columns,
                "row_count": row_count,
                "results": results,
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
        else:
            # 非查询语句（INSERT、UPDATE、DELETE等）
            row_count = cursor.rowcount
            conn.commit()
            
            return {
                "success": True,
                "message": f"执行成功，影响 {row_count} 行",
                "sql": sql,
                "params": params,
                "row_count": row_count,
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"执行过程中发生错误: {str(e)}",
            "error": str(e),
            "sql": sql,
            "params": params
        }
    finally:
        # 显式关闭资源
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

@tool
def execute_batch_sql(queries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    批量执行SQL语句
    
    Args:
        queries: SQL语句列表，每个元素包含sql和params
        
    Returns:
        包含批量执行结果的字典
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        start_time = datetime.now()
        results = []
        
        for i, query in enumerate(queries):
            sql = query.get("sql", "")
            params = query.get("params", None)
            
            if not sql:
                continue
                
            query_start = datetime.now()
            
            try:
                if params:
                    cursor.execute(sql, params)
                else:
                    cursor.execute(sql)
                
                # 如果是查询语句，获取结果
                if cursor.description:
                    columns = [column[0] for column in cursor.description]
                    rows = cursor.fetchall()
                    
                    # 转换为字典列表
                    query_results = []
                    for row in rows:
                        row_dict = {}
                        for j, col in enumerate(columns):
                            value = row[j]
                            if isinstance(value, datetime):
                                value = value.strftime('%Y-%m-%d %H:%M:%S')
                            row_dict[col] = value
                        query_results.append(row_dict)
                    
                    row_count = len(query_results)
                else:
                    row_count = cursor.rowcount
                    query_results = None
                
                results.append({
                    "index": i,
                    "success": True,
                    "sql": sql,
                    "params": params,
                    "row_count": row_count,
                    "results": query_results,
                    "execution_time_ms": (datetime.now() - query_start).total_seconds() * 1000
                })
                
            except Exception as e:
                results.append({
                    "index": i,
                    "success": False,
                    "sql": sql,
                    "params": params,
                    "error": str(e),
                    "execution_time_ms": (datetime.now() - query_start).total_seconds() * 1000
                })
        
        # 提交事务
        conn.commit()
        
        cursor.close()
        conn.close()
        
        # 统计信息
        total_queries = len(queries)
        successful_queries = sum(1 for r in results if r.get("success", False))
        failed_queries = total_queries - successful_queries
        
        return {
            "success": True,
            "message": f"批量执行完成，成功 {successful_queries} 个，失败 {failed_queries} 个",
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "results": results,
            "execution_info": {
                "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "total_duration_ms": (datetime.now() - start_time).total_seconds() * 1000
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"批量执行失败: {str(e)}",
            "error": str(e)
        }