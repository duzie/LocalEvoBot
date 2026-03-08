# web_validator_skill 使用指南

## 工具清单

| 工具 | 功能 | 适用文件 |
|------|------|---------|
| **validate_html** | HTML 结构校验 | .html, .htm |
| **validate_js** | JavaScript 语法校验 | .js, .jsx, .mjs |
| **validate_css** | CSS 语法校验 | .css, .scss, .less |
| **validate_web_file** | 自动识别并校验 | 所有 Web 文件 |
| **validate_web_project** | 校验整个项目 | 项目目录 |

---

## 快速开始

### 1. HTML 校验

```python
# 基础校验
validate_html.invoke({
    "file_path": "index.html"
})

# 严格模式
validate_html.invoke({
    "file_path": "index.html",
    "strict_mode": True
})
```

**返回**:
```json
{
    "success": true,
    "message": "HTML 结构校验通过"
}
```

### 2. JS 校验

```python
# 基础校验
validate_js.invoke({
    "file_path": "app.js"
})

# 使用 ESLint（如果已安装）
validate_js.invoke({
    "file_path": "app.js",
    "use_eslint": true
})
```

### 3. CSS 校验

```python
validate_css.invoke({
    "file_path": "style.css"
})
```

### 4. 自动识别

```python
# 自动识别文件类型
validate_web_file.invoke({
    "file_path": "main.js"
})
```

### 5. 项目校验

```python
# 校验整个项目
validate_web_project.invoke({
    "project_path": "D:\\web-project"
})
```

---

## 参数说明

### validate_html

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_path | string | - | HTML 文件路径 |
| strict_mode | boolean | False | 严格模式 |

### validate_js

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_path | string | - | JS 文件路径 |
| use_eslint | boolean | False | 使用 ESLint |

### validate_css

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_path | string | - | CSS 文件路径 |

### validate_web_file

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| file_path | string | - | 文件路径 |

### validate_web_project

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| project_path | string | - | 项目目录 |

---

## 检查内容

### HTML 校验

- ✅ DOCTYPE 声明
- ✅ html/head/body 标签
- ✅ 标签闭合
- ✅ 标签嵌套
- ✅ 属性引号（严格模式）
- ✅ 链接检查

### JS 校验

- ✅ 语法错误
- ✅ 括号匹配
- ✅ 未闭合的字符串
- ✅ Node.js 语法检查（如果可用）
- ✅ ESLint 集成（可选）

### CSS 校验

- ✅ 括号匹配
- ✅ 属性分号
- ✅ 颜色值格式
- ✅ 常见拼写错误
- ✅ Vendor prefix 检查

---

## 常见错误

### HTML 错误

```json
{
    "success": false,
    "errors": [
        {
            "line": 10,
            "col": 5,
            "message": "未闭合的标签 <div>",
            "code": "UNCLOSED_TAG"
        }
    ]
}
```

### JS 错误

```json
{
    "success": false,
    "errors": [
        {
            "line": 25,
            "col": 10,
            "message": "SyntaxError: Unexpected token",
            "code": "SyntaxError"
        }
    ]
}
```

### CSS 错误

```json
{
    "success": false,
    "errors": [
        {
            "line": 50,
            "col": 0,
            "message": "未闭合的大括号 { 共 2 个",
            "code": "UNCLOSED_BRACE"
        }
    ]
}
```

---

## 最佳实践

### 1. 修改后自动校验

```python
# 修改 HTML 文件后
safe_file_editing.invoke({...})

# 自动校验
validate_web_file.invoke({
    "file_path": "index.html"
})
```

### 2. 提交前校验

```python
# 提交前校验整个项目
result = validate_web_project.invoke({
    "project_path": "."
})

if result["success"]:
    print("✅ 可以提交")
else:
    print(f"❌ 有 {result['failed_files']} 个文件需要修复")
```

### 3. CI/CD 集成

```python
# 在 CI 脚本中
result = validate_web_project.invoke({
    "project_path": "."
})

if not result["success"]:
    exit(1)  # 失败则终止 CI
```

---

## 依赖安装

### 可选依赖

```bash
# HTML 解析（可选，用于更精确的检查）
pip install html5lib

# JS 美化（可选）
pip install jsbeautifier

# ESLint（需要 Node.js）
npm install -g eslint
```

### 必需依赖

- ✅ Python 3.7+
- ✅ Node.js（可选，用于 JS 校验）

---

## 对比其他工具

| 工具 | 速度 | 准确性 | 依赖 |
|------|------|--------|------|
| **web_validator_skill** | ⭐⭐⭐⭐ | ⭐⭐⭐ | 无 |
| **ESLint** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Node.js |
| **HTMLHint** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Node.js |
| **Stylelint** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Node.js |

**优势**:
- ✅ 无需额外安装
- ✅ Python 原生
- ✅ 集成在技能系统中

**劣势**:
- ❌ 功能不如专业工具全面
- ❌ 规则较少

---

## 示例

### 完整工作流

```python
# 1. 修改文件
safe_file_editing.invoke({
    "file_path": "app.js",
    "old_text": "function hello() {",
    "new_text": "function hello(name) {"
})

# 2. 校验
result = validate_js.invoke({
    "file_path": "app.js"
})

# 3. 检查结果
if result["success"]:
    print("✅ 校验通过")
else:
    print("❌ 发现错误:")
    for error in result["errors"]:
        print(f"  行{error['line']}: {error['message']}")
```

---

_让 Web 代码更健壮！_ 🦞
