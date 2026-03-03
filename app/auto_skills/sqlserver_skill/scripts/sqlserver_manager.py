"""
SQL Server 连接管理器
提供连接池、连接状态管理和配置管理功能
"""
from langchain_core.tools import tool
import pyodbc
import json
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import os

# 全局连接池
_connection_pool = {}
_connection_lock = threading.Lock()
_connection_config = {
    "server": os.environ.get("SQLSERVER_SERVER", ".\\SQLEXPRESS"),
    "database": os.environ.get("SQLSERVER_DATABASE", "CanyinSimple"),
    "username": os.environ.get("SQLSERVER_USERNAME", "sa"),
    "password": os.environ.get("SQLSERVER_PASSWORD", "sa"),
    "max_pool_size": int(os.environ.get("SQLSERVER_MAX_POOL_SIZE", "10")),
    "connection_timeout": int(os.environ.get("SQLSERVER_CONNECTION_TIMEOUT", "30")),
    "idle_timeout": int(os.environ.get("SQLSERVER_IDLE_TIMEOUT", "300"))
}

def _get_connection_key(server: str = None, database: str = None, 
                       username: str = None, password: str = None) -> str:
    """生成连接键"""
    server = server or _connection_config["server"]
    database = database or _connection_config["database"]
    username = username or _connection_config["username"]
    password = password or _connection_config["password"]
    
    return f"{server}|{database}|{username}"

def _create_connection(server: str, database: str, username: str, password: str) -> pyodbc.Connection:
    """创建新的数据库连接"""
    if username and password:
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    else:
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
    
    return pyodbc.connect(conn_str, timeout=_connection_config["connection_timeout"])

def get_connection(server: str = None, database: str = None, 
                  username: str = None, password: str = None) -> pyodbc.Connection:
    """
    从连接池获取数据库连接
    
    Args:
        server: 服务器地址
        database: 数据库名称
        username: 用户名
        password: 密码
        
    Returns:
        pyodbc.Connection对象
    """
    connection_key = _get_connection_key(server, database, username, password)
    
    with _connection_lock:
        # 清理过期连接
        current_time = datetime.now()
        expired_keys = []
        
        for key, conn_info in _connection_pool.items():
            if (current_time - conn_info["last_used"]).seconds > _connection_config["idle_timeout"]:
                try:
                    conn_info["connection"].close()
                except:
                    pass
                expired_keys.append(key)
        
        for key in expired_keys:
            del _connection_pool[key]
        
        # 获取或创建连接
        if connection_key in _connection_pool:
            conn_info = _connection_pool[connection_key]
            conn_info["last_used"] = current_time
            return conn_info["connection"]
        else:
            # 检查连接池大小
            if len(_connection_pool) >= _connection_config["max_pool_size"]:
                # 移除最久未使用的连接
                oldest_key = min(_connection_pool.items(), 
                               key=lambda x: x[1]["last_used"])[0]
                try:
                    _connection_pool[oldest_key]["connection"].close()
                except:
                    pass
                del _connection_pool[oldest_key]
            
            # 创建新连接
            server = server or _connection_config["server"]
            database = database or _connection_config["database"]
            username = username or _connection_config["username"]
            password = password or _connection_config["password"]
            
            try:
                conn = _create_connection(server, database, username, password)
                _connection_pool[connection_key] = {
                    "connection": conn,
                    "last_used": current_time,
                    "created": current_time,
                    "server": server,
                    "database": database,
                    "username": username
                }
                return conn
            except Exception as e:
                raise Exception(f"创建数据库连接失败: {str(e)}")


def close_all_connections():
    """关闭所有连接"""
    with _connection_lock:
        for key, conn_info in _connection_pool.items():
            try:
                conn_info["connection"].close()
            except:
                pass
        _connection_pool.clear()

def get_connection_stats() -> Dict[str, Any]:
    """获取连接池统计信息"""
    with _connection_lock:
        current_time = datetime.now()
        connections = []
        
        for key, conn_info in _connection_pool.items():
            connections.append({
                "connection_key": key,
                "server": conn_info["server"],
                "database": conn_info["database"],
                "username": conn_info["username"],
                "created": conn_info["created"].isoformat(),
                "last_used": conn_info["last_used"].isoformat(),
                "idle_seconds": (current_time - conn_info["last_used"]).seconds,
                "age_seconds": (current_time - conn_info["created"]).seconds
            })
        
        return {
            "total_connections": len(_connection_pool),
            "max_pool_size": _connection_config["max_pool_size"],
            "connections": connections,
            "config": _connection_config
        }

@tool
def manage_sqlserver_connections(action: str = "stats", 
                                server: str = None, 
                                database: str = None, 
                                username: str = None, 
                                password: str = None) -> Dict[str, Any]:
    """
    管理SQL Server连接
    
    Args:
        action: 操作类型 - stats（统计）、test（测试连接）、close（关闭连接）
        server: 服务器地址
        database: 数据库名称
        username: 用户名
        password: 密码
        
    Returns:
        包含操作结果的字典
    """
    try:
        if action == "stats":
            # 获取连接统计
            stats = get_connection_stats()
            return {
                "success": True,
                "message": "连接池统计信息",
                "action": action,
                "stats": stats
            }
            
        elif action == "test":
            # 测试连接
            try:
                conn = get_connection(server, database, username, password)
                cursor = conn.cursor()
                cursor.execute("SELECT @@VERSION")
                version = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT 
                        DB_NAME() as database_name,
                        @@SERVERNAME as server_name,
                        @@VERSION as sql_version
                """)
                db_info = cursor.fetchone()
                
                return {
                    "success": True,
                    "message": "数据库连接测试成功",
                    "action": action,
                    "connection_info": {
                        "server": server or _connection_config["server"],
                        "database": database or _connection_config["database"],
                        "sql_version": version,
                        "database_name": db_info[0],
                        "server_name": db_info[1]
                    }
                }
            except Exception as e:
                return {
                    "success": False,
                    "message": f"数据库连接测试失败: {str(e)}",
                    "action": action,
                    "error": str(e)
                }
                
        elif action == "close":
            # 关闭连接
            close_all_connections()
            return {
                "success": True,
                "message": "已关闭所有数据库连接",
                "action": action
            }
            
        else:
            return {
                "success": False,
                "message": f"不支持的操作类型: {action}",
                "action": action,
                "supported_actions": ["stats", "test", "close"]
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"连接管理操作失败: {str(e)}",
            "action": action,
            "error": str(e)
        }

@tool
def configure_sqlserver(server: str = None, database: str = None, 
                       username: str = None, password: str = None,
                       max_pool_size: int = None, connection_timeout: int = None,
                       idle_timeout: int = None) -> Dict[str, Any]:
    """
    配置SQL Server连接参数
    
    Args:
        server: 服务器地址
        database: 数据库名称
        username: 用户名
        password: 密码
        max_pool_size: 最大连接池大小
        connection_timeout: 连接超时时间（秒）
        idle_timeout: 空闲连接超时时间（秒）
        
    Returns:
        包含配置结果的字典
    """
    try:
        old_config = _connection_config.copy()
        
        if server is not None:
            _connection_config["server"] = server
        if database is not None:
            _connection_config["database"] = database
        if username is not None:
            _connection_config["username"] = username
        if password is not None:
            _connection_config["password"] = password
        if max_pool_size is not None:
            _connection_config["max_pool_size"] = max_pool_size
        if connection_timeout is not None:
            _connection_config["connection_timeout"] = connection_timeout
        if idle_timeout is not None:
            _connection_config["idle_timeout"] = idle_timeout
        
        # 关闭旧连接，使用新配置
        close_all_connections()
        
        return {
            "success": True,
            "message": "SQL Server配置已更新",
            "old_config": old_config,
            "new_config": _connection_config
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"配置更新失败: {str(e)}",
            "error": str(e)
        }