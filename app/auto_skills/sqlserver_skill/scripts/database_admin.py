from langchain_core.tools import tool
import pyodbc
import json
import pandas as pd
from typing import Dict, Any, Optional, List
from datetime import datetime
from decimal import Decimal

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
def list_databases() -> Dict[str, Any]:
    """
    列出所有数据库
    
    Returns:
        包含数据库列表的字典
    """
    try:
        # 使用连接管理器，但指定连接到master数据库
        server = ".\\SQLEXPRESS"
        database = "master"  # 连接到master数据库来获取所有数据库列表
        username = "sa"
        password = "sa"
        
        # 构建连接字符串
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                d.name,
                d.database_id,
                d.create_date,
                d.compatibility_level,
                d.collation_name,
                d.state_desc,
                d.recovery_model_desc,
                CAST(COALESCE(SUM(mf.size) * 8.0 / 1024, 0) AS DECIMAL(10,2)) as size_mb,
                CAST(COALESCE(SUM(CASE WHEN mf.type = 1 THEN mf.size ELSE 0 END) * 8.0 / 1024, 0) AS DECIMAL(10,2)) as log_size_mb
            FROM sys.databases d
            LEFT JOIN sys.master_files mf ON d.database_id = mf.database_id
            WHERE d.name NOT IN ('master', 'tempdb', 'model', 'msdb')
            GROUP BY 
                d.name,
                d.database_id,
                d.create_date,
                d.compatibility_level,
                d.collation_name,
                d.state_desc,
                d.recovery_model_desc
            ORDER BY d.name
        """)
        
        databases = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            db_info = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, datetime):
                    value = value.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(value, Decimal):
                    value = float(value)
                db_info[col] = value
            databases.append(db_info)
        
        cursor.close()
        conn.close()
        
        return {
            "ok": True,
            "message": f"找到 {len(databases)} 个数据库",
            "databases": databases,
            "count": len(databases)
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": f"获取数据库列表失败: {str(e)}"
        }


@tool
def create_database(database_name: str,
                   collation: str = "Chinese_PRC_CI_AS",
                   recovery_model: str = "SIMPLE") -> Dict[str, Any]:
    """
    创建新数据库
    
    Args:
        database_name: 数据库名称
        collation: 排序规则，默认 Chinese_PRC_CI_AS
        recovery_model: 恢复模式，可选 SIMPLE/FULL/BULK_LOGGED
    
    Returns:
        包含创建结果的字典
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 检查数据库是否已存在
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", database_name)
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return {
                "ok": False,
                "error": "数据库已存在",
                "message": f"数据库 '{database_name}' 已存在"
            }
        
        # 创建数据库
        sql = f"""
        CREATE DATABASE [{database_name}]
        COLLATE {collation}
        """
        
        cursor.execute(sql)
        conn.commit()
        
        # 设置恢复模式
        if recovery_model.upper() in ["FULL", "BULK_LOGGED"]:
            cursor.execute(f"ALTER DATABASE [{database_name}] SET RECOVERY {recovery_model.upper()}")
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "ok": True,
            "message": f"数据库 '{database_name}' 创建成功",
            "database_name": database_name,
            "collation": collation,
            "recovery_model": recovery_model.upper()
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": f"创建数据库失败: {str(e)}"
        }


@tool
def backup_database(database_name: str,
                   backup_path: str = None,
                   backup_type: str = "FULL") -> Dict[str, Any]:
    """
    备份数据库
    
    Args:
        database_name: 数据库名称
        backup_path: 备份文件路径，如不指定则使用默认路径
        backup_type: 备份类型，FULL/DIFFERENTIAL/LOG
    
    Returns:
        包含备份结果的字典
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 检查数据库是否存在
        cursor.execute("SELECT name FROM sys.databases WHERE name = ?", database_name)
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return {
                "ok": False,
                "error": "数据库不存在",
                "message": f"数据库 '{database_name}' 不存在"
            }
        
        # 生成备份文件名
        if not backup_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"D:\\Backups\\{database_name}_{timestamp}.bak"
        
        # 执行备份
        if backup_type.upper() == "FULL":
            sql = f"BACKUP DATABASE [{database_name}] TO DISK = '{backup_path}' WITH INIT"
        elif backup_type.upper() == "DIFFERENTIAL":
            sql = f"BACKUP DATABASE [{database_name}] TO DISK = '{backup_path}' WITH DIFFERENTIAL, INIT"
        elif backup_type.upper() == "LOG":
            sql = f"BACKUP LOG [{database_name}] TO DISK = '{backup_path}' WITH INIT"
        else:
            cursor.close()
            conn.close()
            return {
                "ok": False,
                "error": "不支持的备份类型",
                "message": f"不支持的备份类型: {backup_type}"
            }
        
        cursor.execute(sql)
        conn.commit()
        
        # 获取备份文件信息
        import os
        file_size = os.path.getsize(backup_path) if os.path.exists(backup_path) else 0
        
        cursor.close()
        conn.close()
        
        return {
            "ok": True,
            "message": f"数据库 '{database_name}' 备份成功",
            "database_name": database_name,
            "backup_path": backup_path,
            "backup_type": backup_type,
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2) if file_size > 0 else 0
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": f"备份数据库失败: {str(e)}"
        }


@tool
def restore_database(database_name: str,
                    backup_path: str,
                    with_replace: bool = False) -> Dict[str, Any]:
    """
    恢复数据库
    
    Args:
        database_name: 数据库名称
        backup_path: 备份文件路径
        with_replace: 是否替换现有数据库
    
    Returns:
        包含恢复结果的字典
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 检查备份文件是否存在
        import os
        if not os.path.exists(backup_path):
            cursor.close()
            conn.close()
            return {
                "ok": False,
                "error": "备份文件不存在",
                "message": f"备份文件不存在: {backup_path}"
            }
        
        # 构建恢复SQL
        if with_replace:
            sql = f"RESTORE DATABASE [{database_name}] FROM DISK = '{backup_path}' WITH REPLACE"
        else:
            sql = f"RESTORE DATABASE [{database_name}] FROM DISK = '{backup_path}'"
        
        cursor.execute(sql)
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return {
            "ok": True,
            "message": f"数据库 '{database_name}' 恢复成功",
            "database_name": database_name,
            "backup_path": backup_path,
            "with_replace": with_replace
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": f"恢复数据库失败: {str(e)}"
        }


@tool
def get_database_size(database_name: str = None) -> Dict[str, Any]:
    """
    获取数据库大小信息
    
    Args:
        database_name: 数据库名称，如不指定则获取所有数据库
    
    Returns:
        包含数据库大小信息的字典
    """
    try:
        # 直接使用连接字符串
        server = ".\\SQLEXPRESS"
        db = "master"
        username = "sa"
        password = "sa"
        
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={db};UID={username};PWD={password}"
        conn = pyodbc.connect(conn_str)
        cursor = conn.cursor()
        
        if database_name:
            # 获取指定数据库的大小
            cursor.execute("""
                SELECT 
                    DB_NAME(database_id) as database_name,
                    CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(10,2)) as size_mb,
                    CAST(SUM(size) * 8.0 / 1024 / 1024 AS DECIMAL(10,2)) as size_gb,
                    COUNT(*) as file_count
                FROM sys.master_files
                WHERE DB_NAME(database_id) = ?
                GROUP BY database_id
            """, database_name)
        else:
            # 获取所有数据库的大小
            cursor.execute("""
                SELECT 
                    DB_NAME(database_id) as database_name,
                    CAST(SUM(size) * 8.0 / 1024 AS DECIMAL(10,2)) as size_mb,
                    CAST(SUM(size) * 8.0 / 1024 / 1024 AS DECIMAL(10,2)) as size_gb,
                    COUNT(*) as file_count
                FROM sys.master_files
                WHERE DB_NAME(database_id) NOT IN ('master', 'tempdb', 'model', 'msdb')
                GROUP BY database_id
                ORDER BY size_mb DESC
            """)
        
        sizes = []
        columns = [column[0] for column in cursor.description]
        
        for row in cursor.fetchall():
            size_info = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, Decimal):
                    value = float(value)
                size_info[col] = value
            sizes.append(size_info)
        
        cursor.close()
        conn.close()
        
        return {
            "ok": True,
            "message": f"获取到 {len(sizes)} 个数据库的大小信息",
            "database_sizes": sizes,
            "count": len(sizes)
        }
        
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "message": f"获取数据库大小失败: {str(e)}"
        }