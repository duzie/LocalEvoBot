# Usage

## Scope
技能生成与管理。这是一个核心技能，提供了完整的技能生命周期管理功能，包括技能生成、版本控制、回滚机制、依赖管理和热重载。

## Tools

### 核心管理工具

#### 1. inspect_environment
获取环境与技能信息。
```python
# 示例
inspect_environment()
```
**返回**: Python版本、操作系统、已安装包、技能列表等环境信息

#### 2. install_packages
安装 Python 依赖包。
```python
# 示例
install_packages(["requests", "beautifulsoup4==4.12.0"])
```
**参数**: 
- packages: 包名列表，支持版本指定
- upgrade: 是否升级已安装的包

#### 3. scaffold_skill
生成新技能脚手架。
```python
# 示例
scaffold_skill("new_skill", ["tool1", "tool2"])
```
**参数**:
- skill_name: 技能名称
- tool_names: 工具名称列表
- description: 技能描述

#### 4. write_tool_code
写入或覆盖工具实现代码。
```python
# 示例
write_tool_code("new_skill/scripts/tools.py", "def my_tool(): ...")
```
**特性**:
- 自动创建快照，支持回滚
- 验证Python语法
- 记录变更历史

#### 5. reload_skills
触发技能热加载。
```python
# 示例
reload_skills()
```
**作用**: 无需重启系统即可加载新技能

#### 6. promote_skill
迁移技能至核心库。
```python
# 示例
promote_skill("new_skill")
```
**作用**: 将自动生成的技能从临时目录迁移到正式技能目录

### 版本控制与回滚工具

#### 7. list_change_versions
列出最近变更版本。
```python
# 示例
list_change_versions(10)  # 列出最近10个变更
```
**返回**: 操作ID、时间、操作者、操作类型、状态

#### 8. rollback_change
回滚到指定版本或最近稳定版本。
```python
# 示例
rollback_change()  # 回滚到最近稳定版本
rollback_change("20250203T101500Z-abc123")  # 回滚到指定版本
```
**特性**:
- 自动恢复文件快照
- 记录回滚操作
- 支持精确版本回滚

#### 9. search_change_logs
按关键词检索变更日志。
```python
# 示例
search_change_logs("write_tool_code", 20)  # 搜索包含"write_tool_code"的变更
```
**参数**:
- keyword: 搜索关键词
- limit: 最大返回结果数

#### 10. export_change_logs
导出变更日志。
```python
# 示例
export_change_logs("audit_log.json", "json")  # 导出为JSON
export_change_logs("audit_log.csv", "csv")    # 导出为CSV
```
**格式**: JSON或CSV

## 工作流程示例

### 1. 创建新技能
```python
# 步骤1: 生成脚手架
scaffold_skill("web_scraper", ["scrape_page", "extract_data"])

# 步骤2: 安装依赖
install_packages(["requests", "beautifulsoup4"])

# 步骤3: 编写工具代码
write_tool_code("web_scraper/scripts/tools.py", code_content)

# 步骤4: 热重载
reload_skills()
```

### 2. 版本管理和回滚
```python
# 查看变更历史
history = list_change_versions(5)

# 发现错误，回滚到稳定版本
rollback_change()

# 搜索特定操作
search_change_logs("install_packages")

# 导出审计日志
export_change_logs("audit_report.json", "json")
```

### 3. 错误恢复流程
```python
# 当 write_tool_code 失败时，系统自动执行：
# 1. 从快照恢复文件
# 2. 记录回滚操作到数据库
# 3. 返回错误信息
# 4. 状态标记为"rolled_back"
```

## 数据库结构

### change_ops 表
```sql
CREATE TABLE change_ops (
    id TEXT PRIMARY KEY,           -- 操作ID: 时间戳-UUID
    created_at TEXT NOT NULL,      -- 创建时间: ISO格式
    actor TEXT NOT NULL,           -- 操作者: 用户ID
    action TEXT NOT NULL,          -- 操作类型: write_tool_code等
    status TEXT NOT NULL,          -- 状态: stable, rolled_back
    log_blob BLOB NOT NULL         -- 加密的日志数据
)
```

### 索引
- idx_change_ops_created: 创建时间索引
- idx_change_ops_action: 操作类型索引
- idx_change_ops_status: 状态索引

## 快照系统

### 存储结构
```
app/data/devops/snapshots/
├── 20250203T101500Z-abc123/      # 操作ID目录
│   ├── app__skills__new__tools.py.bin  # 加密快照文件
│   └── ...
├── 20250203T101600Z-def456/
└── ...
```

### 快照文件格式
- **文件名**: 相对路径哈希 + .bin
- **内容**: 加密的文件原始内容
- **元数据**: 存储在数据库的log_blob中

## 安全配置

### 密钥管理
```bash
# 方式1: 环境变量
export DEVOPS_ENC_KEY="your-encryption-key-here"

# 方式2: 密钥文件
# 自动生成: app/data/devops/devops.key
```

### 权限设置
```bash
# 数据库文件权限
chmod 600 app/data/devops/change_history.sqlite3

# 密钥文件权限
chmod 600 app/data/devops/devops.key

# 快照目录权限
chmod 700 app/data/devops/snapshots/
```

## 错误处理

### 常见错误及解决方案

#### 1. 加密错误
**症状**: "缺少依赖 cryptography" 或 "解密失败"
**解决方案**:
```python
install_packages(["cryptography"])
# 或检查密钥是否正确
```

#### 2. 数据库错误
**症状**: "数据库锁定" 或 "权限拒绝"
**解决方案**:
- 检查数据库文件权限
- 确保没有其他进程在使用数据库
- 重启应用

#### 3. 快照错误
**症状**: "快照文件不存在" 或 "磁盘空间不足"
**解决方案**:
- 检查磁盘空间
- 清理旧快照
- 检查文件权限

#### 4. 依赖错误
**症状**: "模块未找到" 或 "导入错误"
**解决方案**:
```python
install_packages(["missing-package-name"])
```

## 性能优化

### 1. 快照清理
```python
# 自动清理机制
# 默认保留最近10个操作
# 旧快照自动删除
```

### 2. 数据库优化
- 使用索引加速查询
- 定期清理旧记录
- 使用连接池

### 3. 内存管理
- 大文件使用流式处理
- 及时释放资源
- 监控内存使用

## 最佳实践

### 1. 开发流程
```python
# 小步提交，频繁验证
scaffold_skill("skill_name", ["tool1"])
write_tool_code("skill_name/scripts/tools.py", simple_code)
reload_skills()
# 测试通过后，逐步添加功能
```

### 2. 版本控制
```python
# 重要操作前查看历史
list_change_versions(5)

# 操作后验证
# 如有问题，立即回滚
rollback_change()
```

### 3. 安全实践
- 定期更换加密密钥
- 监控变更日志
- 限制敏感操作权限
- 定期备份数据

### 4. 测试策略
```python
# 单元测试
# 集成测试
# 回滚测试
# 性能测试
```

## 扩展开发

### 1. 添加新工具
```python
# 在 skill_tools.py 中添加新函数
@tool
def new_tool(param1: str, param2: int):
    """工具描述"""
    # 实现代码
    # 自动支持版本控制和回滚
```

### 2. 自定义加密
```python
# 替换 _get_fernet 函数
def _get_custom_fernet():
    # 实现自定义加密
    pass
```

### 3. 数据库迁移
```python
# 支持迁移到其他数据库
# 如 PostgreSQL, MySQL
```

### 4. Web界面
```python
# 可扩展为Web管理界面
# 提供可视化操作历史
# 支持图形化回滚
```

## 故障排除指南

### 1. 技能无法加载
**检查步骤**:
1. 查看技能目录结构是否正确
2. 检查 __init__.py 文件
3. 验证工具代码语法
4. 查看错误日志

### 2. 回滚失败
**检查步骤**:
1. 确认操作ID是否存在
2. 检查快照文件是否完整
3. 验证文件权限
4. 查看数据库状态

### 3. 性能问题
**优化建议**:
1. 清理旧快照
2. 优化数据库查询
3. 分批处理大文件
4. 增加缓存机制

### 4. 安全警报
**应对措施**:
1. 立即更换加密密钥
2. 审查变更日志
3. 恢复备份数据
4. 加强权限控制

## 联系支持

如有问题，请参考:
1. 源代码: scripts/skill_tools.py
2. 数据库文档
3. 加密库文档: cryptography
4. SQLite文档

## 更新日志

### v1.0.0 (2026-02-03)
- 初始版本发布
- 完整的技能生命周期管理
- 版本控制和回滚机制
- 加密存储和审计日志
- 热重载支持
