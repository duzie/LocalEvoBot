# file_skill 使用指南

## 工具清单

| 工具名 | 功能 | 参数 | 示例 |
|--------|------|------|------|
| read_file | 读取文件内容 | file_path, max_chars, encoding, return_summary | `read_file("test.py")` |
| write_file | 写入文件内容 | file_path, content, encoding, create_backup | `write_file("test.py", "print('hi')")` |
| append_file | 追加内容 | file_path, content, encoding, add_newline | `append_file("log.txt", "new line")` |
| file_organize | 按后缀整理 | directory, group_by_ext | `file_organize("./downloads")` |

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
    "create_backup": False  # 新文件不需要备份
})
```

### 场景 3：追加日志

```python
result = append_file.invoke({
    "file_path": "app.log",
    "content": "[INFO] 操作完成",
    "add_newline": True
})
```

### 场景 4：读取大文件并摘要

```python
result = read_file.invoke({
    "file_path": "large_file.py",
    "max_chars": 100000,
    "return_summary": True
})
if result.get("ok"):
    print(result.get("summary"))  # 打印摘要
    print(result.get("content"))  # 打印内容
```

## 最佳实践

1. **读取前检查文件是否存在**
   - read_file 会自动检查，但提前检查可以避免不必要的调用

2. **写入时启用备份**
   - `create_backup=True`（默认）可以在出错时恢复

3. **大文件使用 max_chars 限制**
   - 默认 50000 字符，避免占用过多内存

4. **让系统自动检测编码**
   - 不指定 encoding 参数，使用 chardet 自动检测

## 常见错误

### 错误 1：file_not_found

**原因**: 文件路径不存在

**修复**: 检查路径是否正确，使用绝对路径

### 错误 2：write_error

**原因**: 写入失败（权限不足/磁盘满）

**修复**: 检查文件权限和磁盘空间

### 错误 3：read_error

**原因**: 读取失败（编码问题/文件损坏）

**修复**: 尝试指定 encoding 参数

## 相关技能

- large_file_processing_skill - 大文件处理（>100MB）
- safe_file_editing_skill - 安全代码编辑
- file_directory_skill - 目录操作
