# 版本控制与回滚机制

## 概述

skillgen_skill 提供了一个完整的版本控制和回滚系统，专门用于管理技能开发过程中的变更。这个系统基于以下核心原则设计：

1. **原子性**: 每个操作都是原子的，要么完全成功，要么完全回滚
2. **可追溯性**: 所有操作都有完整的审计日志
3. **安全性**: 使用加密存储敏感数据
4. **可靠性**: 自动错误恢复和回滚机制

## 架构设计

### 1. 三层架构

```
┌─────────────────┐
│   应用层         │ ← 工具调用 (write_tool_code, rollback_change等)
├─────────────────┤
│   服务层         │ ← 业务逻辑 (快照、加密、数据库操作)
├─────────────────┤
│   存储层         │ ← SQLite数据库 + 文件快照
└─────────────────┘
```

### 2. 核心组件

#### 2.1 数据库系统
- **数据库**: SQLite
- **表名**: change_ops
- **位置**: `app/data/devops/change_history.sqlite3`
- **加密**: 所有日志数据都经过Fernet加密存储

#### 2.2 快照系统
- **目录**: `app/data/devops/snapshots/`
- **格式**: 加密的二进制文件
- **命名**: `操作ID/相对路径哈希.bin`

#### 2.3 加密系统
- **算法**: Fernet (AES-128-CBC)
- **密钥**: 环境变量或文件存储
- **强度**: 128位加密，HMAC验证

## 详细机制

### 1. 操作生命周期

#### 1.1 正常流程
```
开始操作 → 创建快照 → 执行操作 → 验证结果 → 记录成功 → 结束
```

#### 1.2 回滚流程
```
开始操作 → 创建快照 → 执行操作 → 发生错误 → 恢复快照 → 记录回滚 → 结束
```

### 2. 快照机制

#### 2.1 快照创建
```python
def _snapshot_file(op_id: str, abs_path: str):
    # 1. 检查文件是否存在
    before_exists = os.path.exists(abs_path)
    
    # 2. 读取文件内容
    before_bytes = open(abs_path, "rb").read() if before_exists else b""
    
    # 3. 加密内容
    enc = _encrypt_bytes(before_bytes)
    
    # 4. 保存快照
    with open(snap_path, "wb") as f:
        f.write(enc)
    
    # 5. 返回元数据
    return {
        "path": abs_path,
        "before_exists": before_exists,
        "before_sha256": _sha256_bytes(before_bytes),
        "snapshot_path": snap_path
    }
```

#### 2.2 快照恢复
```python
def _restore_snapshot(file_item: dict):
    abs_path = file_item.get("path")
    before_exists = file_item.get("before_exists")
    snap_path = file_item.get("snapshot_path")
    
    if before_exists:
        # 恢复文件内容
        enc = open(snap_path, "rb").read()
        raw = _decrypt_bytes(enc)
        with open(abs_path, "wb") as f:
            f.write(raw)
    else:
        # 删除文件（如果操作前不存在）
        if os.path.exists(abs_path):
            os.remove(abs_path)
```

### 3. 数据库设计

#### 3.1 表结构
```sql
CREATE TABLE change_ops (
    id TEXT PRIMARY KEY,           -- 格式: YYYYMMDDTHHMMSSZ-UUID
    created_at TEXT NOT NULL,      -- ISO 8601格式
    actor TEXT NOT NULL,           -- 操作者标识
    action TEXT NOT NULL,          -- 操作类型
    status TEXT NOT NULL,          -- 状态: stable, rolled_back
    log_blob BLOB NOT NULL         -- 加密的JSON日志
)
```

#### 3.2 索引设计
```sql
CREATE INDEX idx_change_ops_created ON change_ops(created_at);
CREATE INDEX idx_change_ops_action ON change_ops(action);
CREATE INDEX idx_change_ops_status ON change_ops(status);
```

### 4. 加密机制

#### 4.1 密钥管理
```python
def _get_fernet():
    # 优先级: 环境变量 > 密钥文件 > 自动生成
    env_key = os.getenv("DEVOPS_ENC_KEY") or os.getenv("AUDIT_LOG_KEY")
    
    if env_key:
        key = env_key.encode("utf-8")
    elif os.path.exists(key_path):
        key = open(key_path, "rb").read().strip()
    else:
        key = Fernet.generate_key()
        with open(key_path, "wb") as f:
            f.write(key)
    
    return Fernet(key)
```

#### 4.2 数据加密
```python
def _encrypt_bytes(data: bytes) -> bytes:
    if data is None:
        data = b""
    return _get_fernet().encrypt(data)

def _decrypt_bytes(token: bytes) -> bytes:
    if token is None:
        return b""
    return _get_fernet().decrypt(token)
```

## 工具实现

### 1. write_tool_code 工具

#### 1.1 完整流程
```python
def write_tool_code(file_path: str, code: str = None, content: str = None):
    # 1. 生成操作ID
    op_id = _new_op_id()
    
    # 2. 创建快照
    snap = _snapshot_file(op_id, file_path)
    
    try:
        # 3. 写入文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)
        
        # 4. 验证语法
        py_compile.compile(file_path, doraise=True)
        
        # 5. 记录成功
        log_data = {
            "id": op_id,
            "action": "write_tool_code",
            "status": "stable",
            "files": [snap]
        }
        _write_change_op(op_id, actor, "write_tool_code", "stable", log_data)
        
        return f"已写入: {file_path}"
        
    except Exception as e:
        # 6. 自动回滚
        _restore_snapshot(snap)
        
        # 7. 记录回滚
        log_data = {
            "id": op_id,
            "action": "write_tool_code",
            "status": "rolled_back",
            "error": str(e),
            "files": [snap]
        }
        _write_change_op(op_id, actor, "write_tool_code", "rolled_back", log_data)
        
        return f"写入失败(已自动回滚): {e}"
```

#### 1.2 关键特性
- **原子性**: 要么完全成功，要么完全回滚
- **验证**: 写入后验证Python语法
- **审计**: 完整记录操作历史
- **安全**: 快照加密存储

### 2. rollback_change 工具

#### 2.1 回滚逻辑
```python
def rollback_change(change_id: str = None):
    # 1. 确定目标版本
    if not change_id:
        change_id = _get_latest_stable_op_id()
    
    # 2. 读取操作记录
    item = _read_change_op(change_id)
    if not item:
        return f"未找到版本: {change_id}"
    
    # 3. 恢复文件
    files = item.get("log", {}).get("files", [])
    for f in files:
        _restore_snapshot(f)
    
    # 4. 记录回滚操作
    new_log = {
        "id": _new_op_id(),
        "action": "rollback",
        "target_id": change_id,
        "files": files
    }
    _write_change_op(new_log["id"], actor, "rollback", "stable", new_log)
    
    return f"已回滚到版本: {change_id}"
```

#### 2.2 回滚策略
- **精确回滚**: 恢复到指定版本的文件状态
- **级联回滚**: 支持多个文件的批量恢复
- **审计跟踪**: 记录回滚操作本身
- **状态管理**: 维护版本间的依赖关系

### 3. 查询工具

#### 3.1 list_change_versions
```python
def list_change_versions(n: int = 10):
    items = _list_ops(n)
    result = []
    for it in items:
        result.append({
            "id": it["id"],
            "created_at": it["created_at"],
            "actor": it["actor"],
            "action": it["action"],
            "status": it["status"],
            "summary": it.get("log", {}).get("summary", "")
        })
    return json.dumps(result, indent=2)
```

#### 3.2 search_change_logs
```python
def search_change_logs(keyword: str, limit: int = 20):
    # 获取所有记录
    items = _list_ops(1000)  # 假设最多1000条记录
    
    # 关键词过滤
    filtered = []
    for it in items:
        log_text = json.dumps(it.get("log", {}), ensure_ascii=False)
        if keyword.lower() in log_text.lower():
            filtered.append(it)
            if len(filtered) >= limit:
                break
    
    # 返回简化格式
    return json.dumps([{
        "id": it["id"],
        "action": it["action"],
        "status": it["status"],
        "summary": it.get("log", {}).get("summary", "")
    } for it in filtered], indent=2)
```

## 安全设计

### 1. 数据加密

#### 1.1 加密范围
- 数据库中的日志数据
- 文件快照内容
- 敏感配置信息

#### 1.2 加密算法
- **算法**: Fernet (基于AES-128-CBC)
- **模式**: 认证加密 (AEAD)
- **密钥**: 256位随机密钥
- **IV**: 随机生成，每个加密操作不同

### 2. 访问控制

#### 2.1 操作者标识
```python
def _get_actor():
    return (os.getenv("LOCAL_USER_ID") or 
            os.getenv("USER") or 
            os.getenv("USERNAME") or 
            "local_user").strip()
```

#### 2.2 权限验证
- 记录所有操作的操作者
- 支持基于操作者的审计
- 可扩展为基于角色的访问控制

### 3. 完整性保护

#### 3.1 哈希校验
```python
def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data or b"")
    return h.hexdigest()
```

#### 3.2 完整性验证
- 文件操作前后计算SHA256
- 快照恢复时验证完整性
- 防止数据篡改

## 性能优化

### 1. 存储优化

#### 1.1 快照清理
```python
def _trim_ops(keep: int = 10):
    # 保留最近keep个操作
    # 删除旧快照文件
    # 清理数据库记录
```

#### 1.2 增量快照
- 只保存变更的文件
- 支持二进制差异
- 减少存储空间

### 2. 查询优化

#### 2.1 索引设计
- 创建时间索引: 加速时间范围查询
- 操作类型索引: 加速按类型过滤
- 状态索引: 加速状态查询

#### 2.2 缓存机制
- 热点数据内存缓存
- 查询结果缓存
- 减少数据库访问

### 3. 并发控制

#### 3.1 数据库锁
- 使用SQLite的WAL模式
- 支持并发读取
- 写操作串行化

#### 3.2 文件锁
- 操作期间锁定文件
- 防止并发修改
- 确保数据一致性

## 扩展性设计

### 1. 插件系统

#### 1.1 自定义加密
```python
# 可替换加密实现
class CustomEncryption:
    def encrypt(self, data: bytes) -> bytes:
        # 自定义加密逻辑
        pass
    
    def decrypt(self, token: bytes) -> bytes:
        # 自定义解密逻辑
        pass
```

#### 1.2 自定义存储
```python
# 可替换存储后端
class StorageBackend:
    def save_snapshot(self, op_id: str, file_data: dict):
        pass
    
    def restore_snapshot(self, file_item: dict):
        pass
```

### 2. 监控集成

#### 2.1 指标收集
- 操作成功率
- 回滚频率
- 存储使用情况
- 性能指标

#### 2.2 告警系统
- 异常操作检测
- 存储空间告警
- 性能下降告警
- 安全事件告警

### 3. 集成接口

#### 3.1 REST API
```python
# 提供HTTP接口
@app.route("/api/versions")
def list_versions():
    return list_change_versions()

@app.route("/api/rollback", methods=["POST"])
def api_rollback():
    data = request.json
    return rollback_change(data.get("change_id"))
```

#### 3.2 CLI工具
```bash
# 命令行接口
skillgen list-versions
skillgen rollback --id 20250203T101500Z-abc123
skillgen search --keyword "write_tool_code"
```

## 故障恢复

### 1. 数据库损坏

#### 1.1 检测机制
- 定期完整性检查
- 备份验证
- 异常检测

#### 1.2 恢复流程
```python
def recover_database():
    # 1. 检查备份
    # 2. 恢复备份
    # 3. 验证数据
    # 4. 重建索引
```

### 2. 快照损坏

#### 2.1 损坏检测
- 文件完整性校验
- 加密验证
- 元数据验证

#### 2.2 恢复策略
- 从其他副本恢复
- 使用旧版本快照
- 手动修复

### 3. 密钥丢失

#### 3.1 预防措施
- 密钥备份
- 密钥轮换
- 多副本存储

#### 3.2 恢复流程
- 使用备份密钥
- 密钥恢复流程
- 数据重新加密

## 最佳实践

### 1. 开发实践

#### 1.1 小步提交
```python
# 频繁提交小变更
write_tool_code("file.py", small_change)
# 验证通过后再继续
```

#### 1.2 测试驱动
```python
# 先写测试
# 再实现功能
# 验证回滚
```

### 2. 运维实践

#### 2.1 定期备份
- 数据库备份
- 密钥备份
- 配置备份

#### 2.2 监控告警
- 设置监控指标
- 配置告警规则
- 定期审计

### 3. 安全实践

#### 3.1 密钥管理
- 定期更换密钥
- 安全存储密钥
- 访问控制

#### 3.2 审计日志
- 定期审查日志
- 异常检测
- 合规性检查

## 总结

skillgen_skill 的版本控制和回滚机制提供了一个强大、安全、可靠的变更管理系统。它具有以下特点：

1. **完整性**: 完整的操作生命周期管理
2. **安全性**: 加密存储和完整性保护
3. **可靠性**: 自动错误恢复和回滚
4. **可扩展性**: 支持插件和自定义
5. **易用性**: 简单的API和工具

这个系统不仅适用于技能开发，也可以作为通用的变更管理框架，用于其他需要版本控制和回滚能力的场景。
