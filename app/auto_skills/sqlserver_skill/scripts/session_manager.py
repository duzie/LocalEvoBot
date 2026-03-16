"""
会话级别的SQL Server连接管理工具
提供简单的会话管理接口，让Agent可以方便地管理连接生命周期
"""
from langchain_core.tools import tool
import pyodbc
import json
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime
from .enhanced_sqlserver_manager import _connection_config

# 会话存储（使用线程锁保证线程安全）
_sessions = {}
_session_counter = 0
_session_lock = threading.Lock()

def _create_connection(server: str = None, database: str = None, 
                    username: str = None, password: str = None) -> pyodbc.Connection:
    """创建新的独立数据库连接（不使用连接池）"""
    server = server or _connection_config["server"]
    database = database or _connection_config["database"]
    username = username or _connection_config["username"]
    password = password or _connection_config["password"]
    
    if username and password:
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    else:
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
    
    return pyodbc.connect(conn_str, timeout=_connection_config["connection_timeout"])

@tool
def start_session(server: str = None, database: str = None, 
                  username: str = None, password: str = None) -> Dict[str, Any]:
    """
    开始一个新的数据库会话，建立连接并保持开启状态
    
    Args:
        server: 服务器地址，如 .\\SQLEXPRESS（可选，默认使用配置）
        database: 数据库名称（可选，默认使用配置）
        username: 用户名（可选，默认使用配置）
        password: 密码（可选，默认使用配置）
        
    Returns:
        包含会话ID和连接信息的字典
    """
    global _session_counter
    
    try:
        # 创建新的独立连接
        conn = _create_connection(server, database, username, password)
        
        # 测试连接
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        
        cursor.execute("SELECT DB_NAME() as database_name, @@SERVERNAME as server_name")
        db_info = cursor.fetchone()
        
        # 生成会话ID
        with _session_lock:
            _session_counter += 1
            session_id = f"session_{_session_counter}"
        
        # 存储会话信息
        _sessions[session_id] = {
            "connection": conn,
            "created_at": datetime.now(),
            "last_used": datetime.now(),
            "server": server or _connection_config["server"],
            "database": database or _connection_config["database"],
            "username": username or _connection_config["username"],
            "query_count": 0
        }
        
        return {
            "success": True,
            "message": "数据库会话已成功建立",
            "session_id": session_id,
            "connection_info": {
                "server": _sessions[session_id]["server"],
                "database": _sessions[session_id]["database"],
                "sql_version": version[:50] + "..." if len(version) > 50 else version,
                "database_name": db_info[0],
                "server_name": db_info[1]
            },
            "usage_hint": "使用 execute_in_session 执行查询，使用 end_session 关闭会话"
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"建立数据库会话失败: {str(e)}",
            "error": str(e)
        }


@tool
def execute_in_session(session_id: str, sql: str, 
                      params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    在指定会话中执行SQL查询
    
    Args:
        session_id: 会话ID（由start_session返回）
        sql: SQL查询语句
        params: 查询参数（可选）
        
    Returns:
        包含查询结果和统计信息的字典
    """
    # 检查会话是否存在
    if session_id not in _sessions:
        return {
            "success": False,
            "message": f"会话不存在: {session_id}",
            "error": "Invalid session ID",
            "available_sessions": list(_sessions.keys())
        }
    
    session = _sessions[session_id]
    conn = session["connection"]
    
    # 检查连接是否仍然有效
    try:
        conn.cursor().execute("SELECT 1")
    except Exception as e:
        return {
            "success": False,
            "message": f"数据库连接已断开: {str(e)}",
            "error": str(e),
            "suggestion": "请重新调用 start_session 建立新会话"
        }
    
    cursor = None
    try:
        cursor = conn.cursor()
        
        # 记录开始时间
        start_time = datetime.now()
        
        # 执行SQL
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # 更新会话信息
        session["last_used"] = datetime.now()
        session["query_count"] += 1
        
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
                "session_id": session_id,
                "sql": sql,
                "params": params,
                "columns": columns,
                "row_count": row_count,
                "results": results,
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                },
                "session_info": {
                    "query_count": session["query_count"],
                    "session_duration_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60
                }
            }
        else:
            # 非查询语句（INSERT、UPDATE、DELETE等）
            row_count = cursor.rowcount
            conn.commit()
            
            return {
                "success": True,
                "message": f"执行成功，影响 {row_count} 行",
                "session_id": session_id,
                "sql": sql,
                "params": params,
                "row_count": row_count,
                "execution_info": {
                    "start_time": start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    "end_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "duration_ms": (datetime.now() - start_time).total_seconds() * 1000
                },
                "session_info": {
                    "query_count": session["query_count"],
                    "session_duration_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"SQL执行失败: {str(e)}",
            "session_id": session_id,
            "sql": sql,
            "params": params,
            "error": str(e)
        }
    finally:
        if cursor:
            cursor.close()


@tool
def end_session(session_id: str) -> Dict[str, Any]:
    """
    结束指定的数据库会话，关闭连接
    
    Args:
        session_id: 会话ID（由start_session返回）
        
    Returns:
        包含会话结束信息的字典
    """
    # 检查会话是否存在
    if session_id not in _sessions:
        return {
            "success": False,
            "message": f"会话不存在: {session_id}",
            "error": "Invalid session ID",
            "available_sessions": list(_sessions.keys())
        }
    
    session = _sessions[session_id]
    
    try:
        # 关闭连接
        try:
            session["connection"].close()
        except:
            pass
        
        # 计算会话统计
        session_duration = datetime.now() - session["created_at"]
        
        # 删除会话
        del _sessions[session_id]
        
        return {
            "success": True,
            "message": "数据库会话已成功关闭",
            "session_id": session_id,
            "session_stats": {
                "query_count": session["query_count"],
                "session_duration_seconds": session_duration.total_seconds(),
                "session_duration_minutes": round(session_duration.total_seconds() / 60, 2),
                "database": session["database"],
                "server": session["server"]
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"关闭会话失败: {str(e)}",
            "error": str(e)
        }


@tool
def list_sessions() -> Dict[str, Any]:
    """
    列出所有活跃的数据库会话
    
    Returns:
        包含所有活跃会话信息的字典
    """
    if not _sessions:
        return {
            "success": True,
            "message": "当前没有活跃的会话",
            "active_sessions": [],
            "total_count": 0
        }
    
    current_time = datetime.now()
    sessions_info = []
    
    for session_id, session in _sessions.items():
        session_duration = current_time - session["created_at"]
        idle_time = current_time - session["last_used"]
        
        sessions_info.append({
            "session_id": session_id,
            "server": session["server"],
            "database": session["database"],
            "username": session["username"],
            "query_count": session["query_count"],
            "created_at": session["created_at"].strftime('%Y-%m-%d %H:%M:%S'),
            "last_used": session["last_used"].strftime('%Y-%m-%d %H:%M:%S'),
            "session_duration_minutes": round(session_duration.total_seconds() / 60, 2),
            "idle_time_minutes": round(idle_time.total_seconds() / 60, 2)
        })
    
    return {
        "success": True,
        "message": f"找到 {len(sessions_info)} 个活跃会话",
        "active_sessions": sessions_info,
        "total_count": len(sessions_info)
    }


@tool
def close_all_sessions() -> Dict[str, Any]:
    """
    关闭所有活跃的数据库会话
    
    Returns:
        包含关闭操作结果的字典
    """
    if not _sessions:
        return {
            "success": True,
            "message": "没有需要关闭的会话",
            "closed_count": 0
        }
    
    closed_count = 0
    failed_count = 0
    errors = []
    
    # 获取所有会话ID
    with _session_lock:
        session_ids = list(_sessions.keys())
    
    # 关闭所有连接
    for session_id in session_ids:
        try:
            if session_id in _sessions:
                _sessions[session_id]["connection"].close()
                closed_count += 1
        except Exception as e:
            failed_count += 1
            errors.append(f"{session_id}: {str(e)}")
    
    # 清空会话字典
    _sessions.clear()
    
    return {
        "success": True,
        "message": f"已关闭 {closed_count} 个会话",
        "closed_count": closed_count,
        "failed_count": failed_count,
        "errors": errors if errors else None
    }