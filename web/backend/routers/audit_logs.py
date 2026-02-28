"""
审计日志 API 路由
提供审计日志的查询、筛选、导出等功能
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import sqlite3
import os
import json

router = APIRouter()

# 数据库路径
def get_audit_db_path():
    """获取审计日志数据库路径"""
    # 当前文件：web/backend/routers/audit_logs.py
    # 目标：app/data/audit_logs.db
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    db_dir = os.path.join(base_dir, "app", "data")
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

class AuditLogQuery(BaseModel):
    """审计日志查询参数"""
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    user_id: Optional[str] = None
    operation_type: Optional[str] = None
    tool_name: Optional[str] = None
    task_id: Optional[int] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    page: int = 1
    page_size: int = 50

class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: int
    timestamp: str
    user_id: Optional[str]
    user_name: Optional[str]
    operation_type: str
    tool_name: Optional[str]
    task_id: Optional[int]
    spec_id: Optional[str]
    status: str
    duration_ms: Optional[int]
    request_data: Optional[Dict[str, Any]]
    response_data: Optional[Dict[str, Any]]
    error_message: Optional[str]
    ip_address: Optional[str]
    session_id: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    created_at: str

def dict_factory(cursor, row):
    """SQLite 字典工厂"""
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

@router.get("/list", response_model=Dict[str, Any])
def list_audit_logs(
    start_time: Optional[str] = Query(None, description="开始时间 (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="结束时间 (ISO 8601)"),
    user_id: Optional[str] = Query(None, description="用户 ID"),
    operation_type: Optional[str] = Query(None, description="操作类型"),
    tool_name: Optional[str] = Query(None, description="工具名称"),
    task_id: Optional[int] = Query(None, description="任务 ID"),
    status: Optional[str] = Query(None, description="状态"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=500, description="每页数量")
):
    """
    查询审计日志列表
    
    - **start_time**: 开始时间 (ISO 8601 格式)
    - **end_time**: 结束时间 (ISO 8601 格式)
    - **user_id**: 用户 ID 筛选
    - **operation_type**: 操作类型筛选
    - **tool_name**: 工具名称筛选
    - **task_id**: 任务 ID 筛选
    - **status**: 状态筛选 (success/failed)
    - **keyword**: 关键词全文搜索
    - **page**: 页码
    - **page_size**: 每页数量 (1-500)
    """
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    try:
        cur = conn.cursor()
        
        # 构建查询条件
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        if user_id:
            conditions.append("user_id = ?")
            params.append(user_id)
        
        if operation_type:
            conditions.append("operation_type = ?")
            params.append(operation_type)
        
        if tool_name:
            conditions.append("tool_name LIKE ?")
            params.append(f"%{tool_name}%")
        
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        if keyword:
            # 使用 FTS 全文搜索
            fts_query = "SELECT rowid FROM audit_logs_fts WHERE audit_logs_fts MATCH ?"
            cur.execute(fts_query, (keyword,))
            fts_results = cur.fetchall()
            if fts_results:
                fts_ids = [r['rowid'] for r in fts_results]
                conditions.append(f"id IN ({','.join(['?'] * len(fts_ids))})")
                params.extend(fts_ids)
            else:
                # 没有匹配结果
                return {
                    "total": 0,
                    "page": page,
                    "page_size": page_size,
                    "total_pages": 0,
                    "logs": []
                }
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 查询总数
        count_sql = f"SELECT COUNT(*) as cnt FROM audit_logs WHERE {where_clause}"
        cur.execute(count_sql, params)
        total = cur.fetchone()['cnt']
        
        # 查询数据
        offset = (page - 1) * page_size
        query_sql = f"""
            SELECT * FROM audit_logs 
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params_with_limit = params + [page_size, offset]
        cur.execute(query_sql, params_with_limit)
        rows = cur.fetchall()
        
        # 解析 JSON 字段
        for row in rows:
            if row.get('request_data'):
                try:
                    row['request_data'] = json.loads(row['request_data'])
                except:
                    pass
            if row.get('response_data'):
                try:
                    row['response_data'] = json.loads(row['response_data'])
                except:
                    pass
            if row.get('extra_data'):
                try:
                    row['extra_data'] = json.loads(row['extra_data'])
                except:
                    pass
        
        total_pages = (total + page_size - 1) // page_size
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "logs": rows
        }
    finally:
        conn.close()

@router.get("/{log_id}", response_model=AuditLogResponse)
def get_audit_log(log_id: int):
    """
    获取单条审计日志详情
    
    - **log_id**: 日志 ID
    """
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
        row = cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="日志不存在")
        
        # 解析 JSON 字段
        if row.get('request_data'):
            try:
                row['request_data'] = json.loads(row['request_data'])
            except:
                pass
        if row.get('response_data'):
            try:
                row['response_data'] = json.loads(row['response_data'])
            except:
                pass
        if row.get('extra_data'):
            try:
                row['extra_data'] = json.loads(row['extra_data'])
            except:
                pass
        
        return row
    finally:
        conn.close()

@router.get("/stats")
def get_audit_stats(
    start_time: Optional[str] = Query(None, description="开始时间"),
    end_time: Optional[str] = Query(None, description="结束时间")
):
    """
    获取审计日志统计信息
    
    - 总日志数
    - 按操作类型统计
    - 按状态统计
    - 按用户统计
    """
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = dict_factory
    try:
        cur = conn.cursor()
        
        conditions = []
        params = []
        
        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time)
        
        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 总数
        cur.execute(f"SELECT COUNT(*) as total FROM audit_logs WHERE {where_clause}", params)
        total = cur.fetchone()['total']
        
        # 按操作类型统计
        cur.execute(f"""
            SELECT operation_type, COUNT(*) as count 
            FROM audit_logs 
            WHERE {where_clause}
            GROUP BY operation_type 
            ORDER BY count DESC
            LIMIT 20
        """, params)
        by_type = cur.fetchall()
        
        # 按状态统计
        cur.execute(f"""
            SELECT status, COUNT(*) as count 
            FROM audit_logs 
            WHERE {where_clause}
            GROUP BY status
        """, params)
        by_status = cur.fetchall()
        
        # 按用户统计
        cur.execute(f"""
            SELECT user_id, user_name, COUNT(*) as count 
            FROM audit_logs 
            WHERE {where_clause} AND user_id IS NOT NULL
            GROUP BY user_id, user_name
            ORDER BY count DESC
            LIMIT 20
        """, params)
        by_user = cur.fetchall()
        
        # 成功率
        cur.execute(f"""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count
            FROM audit_logs
            WHERE {where_clause}
        """, params)
        stats_row = cur.fetchone()
        success_rate = (stats_row['success_count'] / stats_row['total'] * 100) if stats_row['total'] > 0 else 0
        
        return {
            "total": total,
            "success_rate": round(success_rate, 2),
            "by_operation_type": by_type,
            "by_status": by_status,
            "by_user": by_user
        }
    finally:
        conn.close()

@router.delete("/clear")
def clear_audit_logs(
    older_than_days: int = Query(30, description="清除多少天前的日志")
):
    """
    清理旧的审计日志
    
    - **older_than_days**: 清除多少天前的日志 (默认 30 天)
    """
    db_path = get_audit_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cutoff_date = (datetime.now() - timedelta(days=older_than_days)).isoformat()
        cur.execute("DELETE FROM audit_logs WHERE timestamp < ?", (cutoff_date,))
        deleted_count = cur.rowcount
        
        # 清理 FTS 表
        cur.execute("DELETE FROM audit_logs_fts WHERE rowid NOT IN (SELECT id FROM audit_logs)")
        
        conn.commit()
        
        return {
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date
        }
    finally:
        conn.close()
