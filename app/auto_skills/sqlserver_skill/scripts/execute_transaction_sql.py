"""
增强版SQL执行工具，支持事务操作
"""
from langchain_core.tools import tool
import pyodbc
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from .enhanced_sqlserver_manager import db_transaction, get_connection, request_connection_context

@tool
def execute_transaction_sql(queries_with_params: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    执行事务SQL，支持多语句原子操作
    queries_with_params: [{'sql': '...', 'params': {...}}, ...]
    """
    try:
        with db_transaction() as conn:
            cursor = conn.cursor()
            results = []
            
            for i, query_info in enumerate(queries_with_params):
                sql = query_info.get('sql', '')
                params = query_info.get('params', {})
                
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
                                # 处理特殊类型
                                if isinstance(value, datetime):
                                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                                elif value is None:
                                    value = None
                                row_dict[col] = value
                            query_results.append(row_dict)
                        
                        row_count = len(query_results)
                        results.append({
                            "index": i,
                            "success": True,
                            "type": "select",
                            "sql": sql,
                            "params": params,
                            "row_count": row_count,
                            "columns": columns,
                            "results": query_results,
                            "execution_time_ms": (datetime.now() - query_start).total_seconds() * 1000
                        })
                    else:
                        # 非查询语句（INSERT、UPDATE、DELETE等）
                        row_count = cursor.rowcount
                        results.append({
                            "index": i,
                            "success": True,
                            "type": "execute",
                            "sql": sql,
                            "params": params,
                            "row_count": row_count,
                            "results": None,
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
                    # 由于在事务中，这里会自动回滚
        
        # 统计信息
        total_queries = len(queries_with_params)
        successful_queries = sum(1 for r in results if r.get("success", False))
        failed_queries = total_queries - successful_queries
        
        return {
            "success": True,
            "message": f"事务执行完成，成功 {successful_queries} 个，失败 {failed_queries} 个",
            "total_queries": total_queries,
            "successful_queries": successful_queries,
            "failed_queries": failed_queries,
            "results": results,
            "transaction_status": "committed"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"事务执行失败: {str(e)}",
            "error": str(e),
            "transaction_status": "rolled_back"
        }


@tool
def execute_sql_query_enhanced(sql: str, params: Optional[Dict[str, Any]] = None, 
                              reuse_connection: bool = False) -> Dict[str, Any]:
    """
    增强版SQL查询执行，支持连接复用
    
    Args:
        sql: SQL查询语句
        params: 查询参数（可选）
        reuse_connection: 是否复用连接（用于连续操作）
        
    Returns:
        包含查询结果和统计信息的字典
    """
    conn = None
    cursor = None
    try:
        # 根据reuse_connection参数决定如何获取连接
        if reuse_connection:
            conn = get_connection()
        else:
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
            
            # 只有在不复用连接时才提交
            if not reuse_connection:
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
        # 根据reuse_connection参数决定是否关闭连接
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn and not reuse_connection:
            try:
                conn.close()
            except:
                pass


@tool
def execute_batch_sql_v2(queries: List[Dict[str, Any]], transaction_mode: bool = True) -> Dict[str, Any]:
    """
    增强版批量执行SQL，支持事务模式
    queries: [{'sql': '...', 'params': {...}}, ...]
    transaction_mode: 是否在事务中执行
    """
    try:
        if transaction_mode:
            # 在事务中执行
            with db_transaction() as conn:
                cursor = conn.cursor()
                results = []
                
                for i, query_info in enumerate(queries):
                    sql = query_info.get('sql', '')
                    params = query_info.get('params', {})
                    
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
                            results.append({
                                "index": i,
                                "success": True,
                                "type": "select",
                                "sql": sql,
                                "params": params,
                                "row_count": row_count,
                                "columns": columns,
                                "results": query_results,
                                "execution_time_ms": (datetime.now() - query_start).total_seconds() * 1000
                            })
                        else:
                            row_count = cursor.rowcount
                            results.append({
                                "index": i,
                                "success": True,
                                "type": "execute",
                                "sql": sql,
                                "params": params,
                                "row_count": row_count,
                                "results": None,
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
                        # 如果在事务模式下遇到错误，抛出异常以便回滚
                        if transaction_mode:
                            raise
                        
                # 如果所有查询都成功执行
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
                        "start_time": results[0]["execution_time_ms"] if results else 0,
                        "transaction_status": "committed"
                    }
                }
        else:
            # 非事务模式执行
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