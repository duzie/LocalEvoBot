from langchain_core.tools import tool
import pyodbc
import json
from typing import Dict, Any, Optional
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
def paginated_sql_query_fixed(sql: str, page: int = 1, page_size: int = 50, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    执行分页SQL查询，防止大量数据导致的内存问题
    修复版：解决了连接提前关闭的问题
    
    Args:
        sql: SQL查询语句（不包含ORDER BY和OFFSET/FETCH子句）
        page: 页码，从1开始
        page_size: 每页大小，默认50条记录
        params: 查询参数（可选）
        
    Returns:
        包含分页查询结果和统计信息的字典
    """
    conn = None
    cursor = None
    try:
        # 建立连接
        conn = get_connection()
        cursor = conn.cursor()
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 首先执行原查询获取总数（使用子查询避免复杂SQL问题）
        # 构建计数查询 - 直接在原SQL外包裹SELECT COUNT(*)
        # 需要确保原始SQL不包含ORDER BY，否则需要特殊处理
        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS temp_table"
        if params:
            cursor.execute(count_sql, params)
        else:
            cursor.execute(count_sql)
        
        total_count = cursor.fetchone()[0]
        
        # 计算总页数
        total_pages = (total_count + page_size - 1) // page_size
        
        # 检查页码是否有效
        if page < 1:
            return {
                "success": False,
                "message": f"页码不能小于1，当前请求页码 {page}",
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }
            
        if total_pages == 0:
            # 没有数据的情况
            return {
                "success": True,
                "message": "查询成功，但没有数据",
                "sql": sql,
                "params": params,
                "columns": [],
                "row_count": 0,
                "results": [],
                "pagination_info": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": False,
                    "has_prev": False
                },
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
        
        if page > total_pages:
            return {
                "success": False,
                "message": f"页码超出范围，当前请求页码 {page}，最大页数 {total_pages}",
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }
        
        # 构建分页查询语句
        offset = (page - 1) * page_size
        # 使用ROW_NUMBER()进行分页，这样可以处理复杂查询
        paginated_sql = f"""
            SELECT * FROM (
                SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS RowNum, * 
                FROM ({sql}) AS subquery
            ) AS numbered_result 
            WHERE RowNum BETWEEN {offset + 1} AND {offset + page_size}
        """
        
        # 执行分页查询
        if params:
            cursor.execute(paginated_sql, params)
        else:
            cursor.execute(paginated_sql)
        
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
                "message": f"分页查询成功，返回第 {page} 页，共 {row_count} 行数据",
                "sql": paginated_sql,
                "original_sql": sql,
                "params": params,
                "columns": columns,
                "row_count": row_count,
                "results": results,
                "pagination_info": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                },
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
        else:
            # 非查询语句不应该出现在分页查询中
            return {
                "success": False,
                "message": "分页查询仅支持SELECT语句",
                "sql": sql,
                "params": params
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
                pass  # 忽略关闭游标的错误
        # 注意：这里不关闭连接，因为它是从连接池获取的
        # 如果连接池管理器正确实现，连接会被放回池中而不是真正关闭


@tool
def paginated_sql_query_with_order_fixed(sql: str, order_by: str = "id", page: int = 1, page_size: int = 50, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    执行分页SQL查询，支持自定义排序
    修复版：解决了连接提前关闭的问题
    
    Args:
        sql: SQL查询语句（不包含ORDER BY子句）
        order_by: 排序列，如 'id ASC' 或 'name DESC'
        page: 页码，从1开始
        page_size: 每页大小，默认50条记录
        params: 查询参数（可选）
        
    Returns:
        包含分页查询结果和统计信息的字典
    """
    conn = None
    cursor = None
    try:
        # 建立连接
        conn = get_connection()
        cursor = conn.cursor()
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 构建计数查询
        count_sql = f"SELECT COUNT(*) FROM ({sql}) AS temp_table"
        if params:
            cursor.execute(count_sql, params)
        else:
            cursor.execute(count_sql)
        
        total_count = cursor.fetchone()[0]
        
        # 计算总页数
        total_pages = (total_count + page_size - 1) // page_size
        
        # 检查页码是否有效
        if page < 1:
            return {
                "success": False,
                "message": f"页码不能小于1，当前请求页码 {page}",
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }
            
        if total_pages == 0:
            # 没有数据的情况
            return {
                "success": True,
                "message": "查询成功，但没有数据",
                "sql": sql,
                "params": params,
                "columns": [],
                "row_count": 0,
                "results": [],
                "pagination_info": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": False,
                    "has_prev": False
                },
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
        
        if page > total_pages:
            return {
                "success": False,
                "message": f"页码超出范围，当前请求页码 {page}，最大页数 {total_pages}",
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "page_size": page_size
            }
        
        # 构建分页查询语句，包含自定义排序
        offset = (page - 1) * page_size
        if order_by:
            paginated_sql = f"""
                SELECT * FROM (
                    SELECT ROW_NUMBER() OVER (ORDER BY {order_by}) AS RowNum, * 
                    FROM ({sql}) AS subquery
                ) AS numbered_result 
                WHERE RowNum BETWEEN {offset + 1} AND {offset + page_size}
            """
        else:
            paginated_sql = f"""
                SELECT * FROM (
                    SELECT ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS RowNum, * 
                    FROM ({sql}) AS subquery
                ) AS numbered_result 
                WHERE RowNum BETWEEN {offset + 1} AND {offset + page_size}
            """
        
        # 执行分页查询
        if params:
            cursor.execute(paginated_sql, params)
        else:
            cursor.execute(paginated_sql)
        
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
                "message": f"分页查询成功，返回第 {page} 页，共 {row_count} 行数据",
                "sql": paginated_sql,
                "original_sql": sql,
                "order_by": order_by,
                "params": params,
                "columns": columns,
                "row_count": row_count,
                "results": results,
                "pagination_info": {
                    "current_page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": page < total_pages,
                    "has_prev": page > 1
                },
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                }
            }
        else:
            # 非查询语句不应该出现在分页查询中
            return {
                "success": False,
                "message": "分页查询仅支持SELECT语句",
                "sql": sql,
                "params": params
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
                pass  # 忽略关闭游标的错误