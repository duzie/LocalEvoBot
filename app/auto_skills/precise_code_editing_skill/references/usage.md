# Usage

## Scope
精准代码编辑技能，提供基于AST解析和行号定位的精确代码修改工具，支持 Python 和 JavaScript (ES6+)

## Tools

### 核心工具

#### find_code_block
在代码文件中查找特定函数、类或其他代码块的精确行号范围，支持 Python 和 JavaScript

**参数：**
- `file_path`: 文件路径
- `block_name`: 代码块名称（函数名、类名、变量名等）
- `block_type`: 代码块类型：function, class, method, variable, const, let, var
- `language`: 编程语言（python, javascript, typescript），不指定则自动检测

**返回：**
- `start_line`: 起始行号
- `end_line`: 结束行号
- `code_snippet`: 代码片段
- `language`: 检测到的语言

**示例：**
```python
# 查找 Python 函数
find_code_block("/path/to/file.py", "my_function", "function")

# 查找 JavaScript 箭头函数
find_code_block("/path/to/file.js", "handleClick", "function")

# 查找 JavaScript 类
find_code_block("/path/to/file.js", "MyClass", "class")
```

#### ast_parse_replace
基于 AST 解析的 Python 代码替换，保持代码结构完整性

**参数：**
- `file_path`: 文件路径
- `target_node`: 目标节点标识（函数名、类名等）
- `new_code`: 新的代码内容
- `node_type`: 节点类型：function, class, import

**示例：**
```python
# 替换 Python 函数
ast_parse_replace(
    "/path/to/file.py",
    "my_function",
    "def my_function():\n    return 'updated'",
    "function"
)
```

#### js_ast_parse_replace
基于 AST 风格的 JavaScript 代码替换，支持 ES6+ 语法

**参数：**
- `file_path`: 文件路径
- `target_name`: 目标节点名称（函数名、类名、变量名等）
- `new_code`: 新的代码内容
- `node_type`: 节点类型：function, class, variable, const, let, export
- `preserve_indent`: 是否保持原始缩进（默认 true）

**支持的语法：**
- 普通函数：`function name() {}`
- 箭头函数：`const name = () => {}`
- 类：`class Name {}`
- 变量：`const/let/var name = ...`
- 导出：`export function/class/const ...`

**示例：**
```python
# 替换 JavaScript 箭头函数
js_ast_parse_replace(
    "/path/to/file.js",
    "handleClick",
    "const handleClick = () => {\n  console.log('clicked')\n}",
    "function"
)

# 替换 JavaScript 类
js_ast_parse_replace(
    "/path/to/file.js",
    "MyComponent",
    "class MyComponent extends React.Component {\n  render() {\n    return <div/>\n  }\n}",
    "class"
)
```

#### debug_text_replace
增强的调试文本替换，智能处理特殊字符、换行符、编码问题

**参数：**
- `file_path`: 文件路径
- `old_text`: 原文本
- `new_text`: 新文本
- `fuzzy_match`: 是否启用模糊匹配（默认 true）
- `preserve_line_ending`: 是否保持原始换行符（默认 true）
- `show_debug_info`: 是否显示详细调试信息（默认 true）

**特性：**
- ✅ 自动检测文件编码
- ✅ 自动检测和处理换行符差异（\n vs \r\n）
- ✅ 模糊匹配支持（空白差异、行级匹配）
- ✅ 详细的差异分析和建议

**示例：**
```python
# 精确替换
debug_text_replace(
    "/path/to/file.js",
    "function old() {}",
    "function new() {}"
)

# 模糊匹配（忽略空白差异）
debug_text_replace(
    "/path/to/file.js",
    "function old() {}",
    "function new() {}",
    fuzzy_match=True
)
```

#### validate_code_changes
验证代码修改的语法正确性和完整性

**参数：**
- `file_path`: 文件路径
- `start_line`: 起始行号
- `end_line`: 结束行号

### 辅助工具

#### detect_file_format
检测文件格式信息，包括编码、换行符、语言、缩进风格等

**参数：**
- `file_path`: 文件路径

**返回：**
- `encoding`: 文件编码
- `line_ending`: 换行符类型
- `language`: 编程语言
- `indent_style`: 缩进风格
- `statistics`: 文件统计信息

**示例：**
```python
result = detect_file_format("/path/to/file.js")
# 返回：
# {
#   "encoding": {"encoding": "utf-8", "confidence": 0.99},
#   "line_ending": {"type": "lf", "description": "Unix/Linux风格 (\\n)"},
#   "language": {"name": "JavaScript", "version": "ES6+"},
#   "indent_style": {"type": "space", "size": 2},
#   "statistics": {"line_count": 100, "char_count": 2500}
# }
```

#### analyze_js_structure
分析 JavaScript 文件的代码结构

**参数：**
- `file_path`: JavaScript 文件路径

**返回：**
- `functions`: 函数列表（名称、类型、行号）
- `classes`: 类列表（名称、父类、行号）
- `variables`: 变量列表（名称、类型、行号）
- `imports`: 导入语句列表
- `exports`: 导出语句列表
- `statistics`: 统计信息

**示例：**
```python
result = analyze_js_structure("/path/to/component.js")
# 返回：
# {
#   "functions": [
#     {"name": "handleClick", "type": "arrow", "line": 10}
#   ],
#   "classes": [
#     {"name": "MyComponent", "extends": "React.Component", "line": 15}
#   ],
#   "imports": [
#     {"type": "default", "name": "React", "module": "react", "line": 1}
#   ],
#   "statistics": {"function_count": 5, "class_count": 1}
# }
```

## 使用场景

### 1. 精确修改 JavaScript 函数
```python
# 步骤1：查找函数位置
result = find_code_block("app.js", "handleSubmit", "function")

# 步骤2：替换函数
js_ast_parse_replace(
    "app.js",
    "handleSubmit",
    "const handleSubmit = async (e) => {\n  e.preventDefault()\n  await submitForm()\n}",
    "function"
)
```

### 2. 调试文本替换失败
```python
# 当精确替换失败时，使用调试模式
result = debug_text_replace(
    "config.js",
    "old configuration",
    "new configuration",
    fuzzy_match=True,
    show_debug_info=True
)

# 查看调试信息
if not result["success"]:
    print(result["debug_info"]["suggestions"])
```

### 3. 分析代码结构
```python
# 分析 JavaScript 文件结构
structure = analyze_js_structure("component.js")

# 查看所有函数
for func in structure["structures"]["functions"]:
    print(f"{func['name']} at line {func['line']}")

# 查看依赖
print("Dependencies:", structure["summary"]["dependencies"])
```

## 最佳实践

1. **优先使用 AST 工具**
   - 对于 Python 代码，使用 `ast_parse_replace`
   - 对于 JavaScript 代码，使用 `js_ast_parse_replace`
   - 这些工具能保持代码结构完整性

2. **调试时使用 debug_text_replace**
   - 当 AST 工具不适用时，使用 `debug_text_replace`
   - 启用 `fuzzy_match=True` 处理空白差异
   - 启用 `show_debug_info=True` 获取详细诊断

3. **先检测文件格式**
   - 在处理未知文件前，先用 `detect_file_format` 检测格式
   - 了解编码、换行符、缩进风格等信息

4. **分析代码结构**
   - 对于复杂的 JavaScript 文件，先用 `analyze_js_structure` 分析结构
   - 了解函数、类、导入导出的分布

## 注意事项

1. **备份重要文件**
   - 修改前建议备份或使用版本控制

2. **验证修改结果**
   - 使用 `validate_code_changes` 验证语法正确性

3. **处理编码问题**
   - 工具会自动检测编码，但某些特殊编码可能需要手动指定

4. **JavaScript 限制**
   - 不支持动态代码分析（eval、动态导入等）
   - 对于极其复杂的嵌套结构，可能需要手动调整
