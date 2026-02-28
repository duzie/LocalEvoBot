### 6. 使用 validate_code_syntax 检查代码语法
在修改代码后，特别是使用正则替换或手动编辑后，务必运行此工具检查语法，防止引入低级错误。

**支持语言**：Python, JavaScript, JSON

```python
# 检查 Python 文件
validate_code_syntax(file_path="app.py", language="python")

# 检查 JS 文件 (自动检测)
validate_code_syntax(file_path="script.js")

# 检查 JSON 文件
validate_code_syntax(file_path="config.json")
```
