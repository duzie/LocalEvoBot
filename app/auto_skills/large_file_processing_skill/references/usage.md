# Usage

## Scope
大文件安全处理技能，支持分块读取、行号精确定位修改、备份恢复与完整性校验

## Tools
- read_large_file_chunks
- replace_lines
- insert_lines
- delete_lines
- get_line_content
- validate_file_integrity
- restore_from_backup

## Examples

### 代码修改标准流程
```python
# 步骤1：查看目标行及上下文
get_line_content(
    file_path="app/views.py",
    line_number=42,
    context_lines=5
)
# 确认行号正确后再操作

# 步骤2：替换指定行
replace_lines(
    file_path="app/views.py",
    new_content="def new_function():\n    return 'new'",
    start_line=42,
    end_line=42
)

# 步骤3：在指定行前插入
insert_lines(
    file_path="app/models.py",
    new_content="class NewModel:",
    line_number=20
)

# 步骤4：删除指定行
delete_lines(
    file_path="app/views.py",
    start_line=10,
    end_line=15
)
```

### 大文件处理
```python
# 分块读取大文件
read_large_file_chunks(
    file_path="large.log",
    chunk_size=1000,
    encoding="utf-8"
)

# 校验文件完整性
validate_file_integrity(
    file_path="app/views.py",
    expected_size=10240,
    checksum_algorithm="md5"
)

# 恢复备份
restore_from_backup(
    file_path="app/views.py",
    backup_suffix=".bak"
)
```

### 最佳实践
- ✅ **先确认，后操作**：使用 `get_line_content` 确认行号后再修改
- ✅ **小范围修改**：单次修改不超过50行
- ✅ **自动备份**：所有修改自动创建 .bak 备份
- ✅ **校验结果**：修改后使用 `validate_file_integrity` 校验
