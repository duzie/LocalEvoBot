"""
审计日志记录器
用于在工具调用时自动记录审计日志
"""
import sqlite3
import json
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, Callable
import functools
import traceback

# 数据库路径
def get_audit_db_path():
    """获取审计日志数据库路径"""
    # 当前文件：app/integrations/audit_logger.py
    # 目标：app/data/audit_logs.db
    base_dir = os.path.dirname(os.path.dirname(__file__))
    db_dir = os.path.join(base_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "audit_logs.db")

def init_audit_db():
    """初始化审计日志数据库"""
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT,
                user_name TEXT,
                operation_type TEXT NOT NULL,
                tool_name TEXT,
                task_id INTEGER,
                spec_id TEXT,
                status TEXT DEFAULT 'success',
                duration_ms INTEGER,
                request_data TEXT,
                response_data TEXT,
                error_message TEXT,
                ip_address TEXT,
                session_id TEXT,
                extra_data TEXT,
                created_at TEXT NOT NULL
            )
        """)
        # 创建索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_logs(operation_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_tool ON audit_logs(tool_name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_task ON audit_logs(task_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_status ON audit_logs(status)")
        
        # 创建 FTS 虚拟表用于全文搜索
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS audit_logs_fts
            USING fts5(tool_name, operation_type, request_data, response_data, error_message)
        """)
        
        conn.commit()
    finally:
        conn.close()

# 初始化数据库
init_audit_db()

class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, user_id: Optional[str] = None, user_name: Optional[str] = None, session_id: Optional[str] = None):
        self.user_id = user_id
        self.user_name = user_name
        self.session_id = session_id
        self.db_path = get_audit_db_path()
    
    def log(
        self,
        operation_type: str,
        tool_name: Optional[str] = None,
        task_id: Optional[int] = None,
        spec_id: Optional[str] = None,
        status: str = 'success',
        duration_ms: Optional[int] = None,
        request_data: Optional[Dict[str, Any]] = None,
        response_data: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        ip_address: Optional[str] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ):
        """
        记录审计日志
        
        Args:
            operation_type: 操作类型 (如：tool_call, file_operation, web_operation 等)
            tool_name: 工具名称
            task_id: 任务 ID
            spec_id: Spec ID
            status: 状态 (success/failed)
            duration_ms: 执行耗时 (毫秒)
            request_data: 请求数据
            response_data: 响应数据
            error_message: 错误信息
            ip_address: IP 地址
            extra_data: 额外数据
        """
        timestamp = datetime.now().isoformat()
        created_at = datetime.now().isoformat()
        
        # 序列化 JSON 字段
        request_data_str = json.dumps(request_data) if request_data else None
        response_data_str = json.dumps(response_data) if response_data else None
        extra_data_str = json.dumps(extra_data) if extra_data else None
        
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO audit_logs (
                    timestamp, user_id, user_name, operation_type, tool_name,
                    task_id, spec_id, status, duration_ms, request_data,
                    response_data, error_message, ip_address, session_id,
                    extra_data, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, self.user_id, self.user_name, operation_type, tool_name,
                task_id, spec_id, status, duration_ms, request_data_str,
                response_data_str, error_message, ip_address, self.session_id,
                extra_data_str, created_at
            ))
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    
    def log_tool_call(
        self,
        tool_name: str,
        request_data: Dict[str, Any],
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
        duration_ms: Optional[int] = None,
        task_id: Optional[int] = None,
        spec_id: Optional[str] = None
    ):
        """
        记录工具调用日志
        
        Args:
            tool_name: 工具名称
            request_data: 请求参数
            response_data: 响应数据
            error: 异常对象
            duration_ms: 执行耗时
            task_id: 任务 ID
            spec_id: Spec ID
        """
        status = 'failed' if error else 'success'
        error_message = str(error) if error else None
        
        return self.log(
            operation_type='tool_call',
            tool_name=tool_name,
            task_id=task_id,
            spec_id=spec_id,
            status=status,
            duration_ms=duration_ms,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message
        )

def audit_tool_call(logger: AuditLogger, tool_name: str):
    """
    工具调用审计装饰器
    
    用法:
        @audit_tool_call(audit_logger, 'my_tool')
        def my_tool(arg1, arg2):
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            request_data = {
                'args': args,
                'kwargs': kwargs
            }
            
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # 尝试序列化响应
                try:
                    response_data = result if isinstance(result, dict) else {'result': str(result)}
                except:
                    response_data = {'result': '<unserializable>'}
                
                logger.log_tool_call(
                    tool_name=tool_name,
                    request_data=request_data,
                    response_data=response_data,
                    duration_ms=duration_ms
                )
                
                return result
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.log_tool_call(
                    tool_name=tool_name,
                    request_data=request_data,
                    error=e,
                    duration_ms=duration_ms
                )
                raise
        
        return wrapper
    return decorator

# 全局审计日志记录器实例
_global_logger: Optional[AuditLogger] = None

def get_audit_logger(user_id: Optional[str] = None, user_name: Optional[str] = None, session_id: Optional[str] = None) -> AuditLogger:
    """获取全局审计日志记录器"""
    global _global_logger
    if _global_logger is None:
        _global_logger = AuditLogger(user_id=user_id, user_name=user_name, session_id=session_id)
    return _global_logger

def set_audit_logger(logger: AuditLogger):
    """设置全局审计日志记录器"""
    global _global_logger
    _global_logger = logger
