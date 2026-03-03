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
        server = ".\\SQLEXPRESS"
        database = "CanyinSimple"
        username = "sa"
        password = "sa"
        
        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
        return pyodbc.connect(conn_str)

@tool
def test_sql_syntax(sql: str) -> Dict[str, Any]:
    """
    测试SQL语法是否正确
    
    Args:
        sql: SQL语句
        
    Returns:
        包含语法检查结果的字典
    """
    try:
        # 使用连接管理器获取连接
        conn = get_connection()
        cursor = conn.cursor()
        
        # 尝试解析SQL（不实际执行）
        # 在SQL Server中，我们可以使用SET PARSEONLY ON来只解析不执行
        try:
            cursor.execute("SET PARSEONLY ON")
            cursor.execute(sql)
            cursor.execute("SET PARSEONLY OFF")
            
            result = {
                "success": True,
                "message": "SQL语法正确",
                "sql": sql,
                "syntax_check": {
                    "status": "valid",
                    "parse_only": True
                }
            }
            
        except pyodbc.Error as e:
            # 解析失败，语法有错误
            error_info = {
                "success": False,
                "message": f"SQL语法错误: {str(e)}",
                "sql": sql,
                "syntax_check": {
                    "status": "invalid",
                    "error": str(e),
                    "error_code": e.args[0] if e.args else None,
                    "error_message": e.args[1] if len(e.args) > 1 else str(e)
                }
            }
            
            if hasattr(e, 'sqlstate'):
                error_info["syntax_check"]["sqlstate"] = e.sqlstate
            
            result = error_info
            
        finally:
            # 确保关闭连接
            try:
                cursor.execute("SET PARSEONLY OFF")
            except:
                pass
            
            cursor.close()
            conn.close()
        
        return result
        
    except pyodbc.Error as e:
        # 连接失败或其他数据库错误
        return {
            "success": False,
            "message": f"数据库连接或语法检查失败: {str(e)}",
            "sql": sql,
            "error": str(e),
            "error_code": e.args[0] if e.args else None,
            "error_message": e.args[1] if len(e.args) > 1 else str(e)
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"语法检查过程中发生错误: {str(e)}",
            "sql": sql,
            "error": str(e)
        }