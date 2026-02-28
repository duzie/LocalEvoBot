# Usage

## Scope
安全文件编辑技能，提供备份、增量编辑、AST 代码替换、代码提取和合并功能，避免文件覆盖问题。

## Tools
- safe_file_backup
- incremental_file_edit
- extract_code_class
- merge_classes_into_file
- python_code_edit (NEW! 推荐用于 Python 文件修改)

## Examples

### 1. 使用 python_code_edit 精准修改 Python 代码
这是修改 Python 文件中函数或类的**最推荐方式**，因为它基于 AST 语法树，能自动处理缩进并验证语法。

**场景**：替换类 `MyClass` 中的 `my_method` 方法。

```python
# 假设原代码:
# class MyClass:
#     def my_method(self):
#         print("old")

# 你只需要提供新的函数代码，不需要关心缩进，工具会自动调整！
new_code = """def my_method(self):
    print("This is the new implementation")
    return True
"""

python_code_edit(
    file_path="path/to/file.py",
    edit_type="replace_function",  # 或 'replace_class'
    name="my_method",              # 要替换的函数名/类名
    new_code=new_code,
    backup=True
)
```

**优势**：
1. **自动缩进**：你提供的代码可以是顶层（无缩进）的，工具会根据目标位置自动添加正确的缩进。
2. **语法安全**：在写入文件前会自动进行 AST 语法检查，防止写入坏代码。
3. **精准定位**：不再依赖脆弱的正则表达式，即使文件中有同名字符串也不会改错。

### 2. 使用 incremental_file_edit 进行通用文本替换
适用于非 Python 文件，或简单的文本替换。

```python
incremental_file_edit(
    file_path="path/to/config.yaml",
    operation="replace",
    target_pattern="timeout: \d+",
    content="timeout: 60"
)
```

### 4. 使用 json_file_edit 结构化修改 JSON
避免使用正则表达式修改 JSON 文件，使用此工具可以保证 JSON 格式合法性。

```python
json_file_edit(
    file_path="config.json",
    updates={
        "server.port": 8080,         # 修改/新增值
        "server.host": "0.0.0.0",
        "debug": True,
        "deprecated_key": None       # 删除键
    },
    create_backup=True
)
```
