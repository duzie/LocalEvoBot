# quick_edit_skill 使用指南

## ⚠️ 重要提示

**这个工具不会验证语法！**

仅用于简单修改，复杂修改请用 `safe_file_editing_skill`。

---

## 快速开始

### 1. 简单替换

```python
# 修改配置
quick_edit.invoke({
    "file_path": "config.py",
    "old_text": "DEBUG = True",
    "new_text": "DEBUG = False"
})
```

### 2. 修改多行

```python
# 替换函数
quick_edit.invoke({
    "file_path": "utils.py",
    "old_text": "def hello():\n    print('Hello')",
    "new_text": "def hello():\n    print('Hello World')"
})
```

### 3. 追加内容

```python
# 在文件末尾添加
quick_append.invoke({
    "file_path": "requirements.txt",
    "text": "requests==2.28.0"
})
```

---

## 参数说明

### quick_edit

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | ✅ | 文件路径 |
| old_text | string | ✅ | 要替换的文本（必须完全匹配） |
| new_text | string | ✅ | 新文本 |

**返回**:
```json
{
    "ok": true,
    "message": "修改成功",
    "replaced_count": 1,
    "backup_path": "config.20260308_162000.bak.py"
}
```

### quick_append

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | ✅ | 文件路径 |
| text | string | ✅ | 要追加的文本 |
| add_newline | boolean | ❌ | 是否添加换行（默认 True） |

---

## 使用场景

### ✅ 适合的场景

1. **修改配置值**
   ```python
   quick_edit.invoke({
       "file_path": ".env",
       "old_text": "API_KEY=old_key",
       "new_text": "API_KEY=new_key"
   })
   ```

2. **修改注释**
   ```python
   quick_edit.invoke({
       "file_path": "main.py",
       "old_text": "# TODO: 修复 bug",
       "new_text": "# FIXED: 已修复"
   })
   ```

3. **修改字符串**
   ```python
   quick_edit.invoke({
       "file_path": "app.py",
       "old_text": "Welcome",
       "new_text": "Welcome to My App"
   })
   ```

4. **追加依赖**
   ```python
   quick_append.invoke({
       "file_path": "requirements.txt",
       "text": "flask==2.0.0"
   })
   ```

---

### ❌ 不适合的场景

1. **修改函数定义**
   ```python
   # ❌ 不要用 quick_edit
   quick_edit.invoke({
       "file_path": "utils.py",
       "old_text": "def calculate(a, b):",
       "new_text": "def calculate(a, b, c):"
   })
   
   # ✅ 用 safe_file_editing_skill
   ```

2. **改变代码逻辑**
   ```python
   # ❌ 不要用 quick_edit
   quick_edit.invoke({
       "file_path": "main.py",
       "old_text": "if x > 0:",
       "new_text": "if x >= 0:"
   })
   ```

3. **重要配置文件**
   ```python
   # ❌ 不要用 quick_edit
   quick_edit.invoke({
       "file_path": "database.yml",
       "old_text": "host: localhost",
       "new_text": "host: production.db"
   })
   ```

---

## 常见错误

### 错误 1: 找不到要替换的文本

```json
{
    "ok": false,
    "error": "找不到要替换的文本",
    "suggestion": "请检查 old_text 是否完全匹配（包括空格和换行）"
}
```

**原因**:
- 缩进不对（4 空格 vs 8 空格）
- 换行符不同（`\n` vs `\r\n`）
- 有多余空格

**解决**:
```python
# 1. 先读取文件确认内容
content = read(path="main.py")

# 2. 找到准确的文本
import re
match = re.search(r"DEBUG = True", content)

# 3. 查看周围内容
start = max(0, match.start() - 50)
end = min(len(content), match.end() + 50)
print(content[start:end])

# 4. 构造准确的 old_text
old_text = content[match.start():match.end()]
```

---

### 错误 2: 编码问题

```json
{
    "ok": false,
    "error": "无法读取文件（可能是二进制文件或编码不支持）"
}
```

**解决**:
- 用文本编辑器打开，另存为 UTF-8
- 或用 `safe_file_editing_skill`（支持自动编码检测）

---

## 最佳实践

### 1. 先读取确认

```python
# 先读取
content = read(path="config.py")

# 查找
if "DEBUG = True" in content:
    # 再修改
    quick_edit.invoke({...})
```

### 2. 包含上下文

```python
# ❌ 太短，可能匹配多处
old_text = "DEBUG = True"

# ✅ 包含上下文，确保唯一
old_text = """
# 调试模式
DEBUG = True
"""
```

### 3. 检查备份

```python
result = quick_edit.invoke({...})
if result.get("ok"):
    print(f"备份文件：{result.get('backup_path')}")
```

### 4. 验证修改

```python
# 修改后读取确认
content = read(path="config.py")
if "DEBUG = False" in content:
    print("修改成功")
```

---

## 对比其他编辑工具

| 工具 | 速度 | 安全性 | 适用场景 |
|------|------|--------|---------|
| **quick_edit** | ⭐⭐⭐⭐⭐ | ⭐⭐ | 简单替换 |
| **safe_file_editing** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 代码修改 |
| **python_code_edit** | ⭐⭐ | ⭐⭐⭐⭐⭐ | Python 代码 |
| **exec (PowerShell)** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 批量操作 |

---

## 示例

### 完整流程

```python
# 1. 读取确认
content = read(path=".env")

# 2. 检查是否存在
if "API_KEY=old" in content:
    # 3. 修改
    result = quick_edit.invoke({
        "file_path": ".env",
        "old_text": "API_KEY=old",
        "new_text": "API_KEY=new"
    })
    
    # 4. 检查结果
    if result.get("ok"):
        print(f"✅ 修改成功，备份：{result.get('backup_path')}")
        
        # 5. 验证
        new_content = read(path=".env")
        if "API_KEY=new" in new_content:
            print("✅ 验证通过")
    else:
        print(f"❌ 失败：{result.get('error')}")
```

---

_快速编辑，但要小心使用！_ 🦞
