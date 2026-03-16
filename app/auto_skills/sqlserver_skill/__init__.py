"""
SQL Server技能包初始化文件
"""
from .scripts.connect_sqlserver import connect_sqlserver
from .scripts.execute_sql_query import execute_sql_query, execute_batch_sql
from .scripts.get_table_structure import get_table_structure
from .scripts.analyze_sql_performance import analyze_sql_performance
from .scripts.test_sql_syntax import test_sql_syntax
from .scripts.sqlserver_manager import (
    manage_sqlserver_connections,
    configure_sqlserver
)
from .scripts.database_admin import (
    list_databases,
    create_database,
    backup_database,
    restore_database,
    get_database_size
)
from .scripts.enhanced_sqlserver_manager import (
    enhanced_manage_sqlserver_connections,
    enhanced_configure_sqlserver
)
from .scripts.execute_transaction_sql import (
    execute_transaction_sql,
    execute_sql_query_enhanced,
    execute_batch_sql_v2
)
from .scripts.session_manager import (
    start_session,
    execute_in_session,
    end_session,
    list_sessions,
    close_all_sessions
)

__all__ = [
    # 原有工具
    "connect_sqlserver",
    "execute_sql_query", 
    "execute_batch_sql",
    "get_table_structure",
    "analyze_sql_performance",
    "test_sql_syntax",
    "manage_sqlserver_connections",
    "configure_sqlserver",
    "list_databases",
    "create_database",
    "backup_database",
    "restore_database",
    "get_database_size",
    # 新增增强工具
    "enhanced_manage_sqlserver_connections",
    "enhanced_configure_sqlserver",
    "execute_transaction_sql",
    "execute_sql_query_enhanced",
    "execute_batch_sql_v2",
    # 会话管理工具（推荐使用）
    "start_session",
    "execute_in_session",
    "end_session",
    "list_sessions",
    "close_all_sessions"
]