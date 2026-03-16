# file_read_write_skill 使用指南

## 工具清单

| 工具名 | 功能 | 参数 | 示例 |
|--------|------|------|------|
| read_file | 读取文件内容 | file_path, max_chars, encoding, return_summary | `read_file("test.py")` |
| write_file | 写入文件内容 | file_path, content, encoding, create_backup | `write_file("test.py", "print('hi')")` |
| append_file | 追加内容 | file_path, content, encoding, add_newline | `append_file("log.txt", "new line")` |

## 使用场景

### 场景 1：读取配置文件

```python
result = read_file.invoke({
    "file_path": "config.json",
    "max_chars": 10000
})
if result.get("ok"):
    content = result.get("content")
    # 处理配置
```

### 场景 2：写入结果文件

```python
result = write_file.invoke({
    "file_path": "output/result.txt",
    "content": "处理结果...",
    "create_backup": False
})
```

### 场景 3：追加日志

```python
result = append_file.invoke({
    "file_path": "app.log",
    "content": "[INFO] 操作完成"
})
```

## 最佳实践

1. **写入时启用备份** - `create_backup=True`（默认）
2. **大文件限制读取** - 使用 `max_chars` 参数
3. **自动检测编码** - 不指定 encoding 参数
4. **检查返回值** - 始终检查 `result.get("ok")`

## 常见错误

### file_not_found
文件不存在，检查路径

### write_error
写入失败，检查权限和磁盘空间

### read_error
读取失败，尝试指定 encoding

## 相关技能

- large_file_processing_skill - 大文件处理
- safe_file_editing_skill - 代码编辑
- file_delete_skill - 文件删除
