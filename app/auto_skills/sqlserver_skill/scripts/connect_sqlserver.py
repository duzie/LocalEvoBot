from langchain_core.tools import tool
import pyodbc
import json
from typing import Dict, Any, Optional

@tool
def connect_sqlserver(server: str, database: str, username: str, password: str) -> Dict[str, Any]:
    """
    连接SQL Server数据库并测试连接状态。
    注意：此工具仅用于测试连接参数是否正确，不会保持持久连接。
    
    Args:
        server: 服务器地址，如 .\\SQLEXPRESS
        database: 数据库名称
        username: 用户名
        password: 密码
        
    Returns:
        包含连接状态和连接信息的字典
    """
    conn = None
    cursor = None
    try:
        # 构建连接字符串
        conn_str = ""
        if username and password:
            # SQL Server认证
            conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
        else:
            # Windows认证
            conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes"
        
        # 建立连接
        conn = pyodbc.connect(conn_str, timeout=10) # 设置超时
        cursor = conn.cursor()
        
        # 测试连接
        cursor.execute("SELECT @@VERSION")
        version_row = cursor.fetchone()
        version = version_row[0] if version_row else "Unknown"
        
        # 获取数据库信息
        cursor.execute("""
            SELECT 
                DB_NAME() as database_name,
                @@SERVERNAME as server_name
        """)
        db_info = cursor.fetchone()
        
        result = {
            "success": True,
            "message": "数据库连接测试成功",
            "connection_info": {
                "server": server,
                "database": database,
                "sql_version": version,
                "database_name": db_info[0] if db_info else "Unknown",
                "server_name": db_info[1] if db_info else "Unknown"
            }
        }
        
        return result
        
    except pyodbc.Error as e:
        return {
            "success": False,
            "message": f"数据库连接失败: {str(e)}",
            "error": str(e),
            "connection_info": {
                "server": server,
                "database": database
            }
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"连接过程中发生错误: {str(e)}",
            "error": str(e)
        }
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