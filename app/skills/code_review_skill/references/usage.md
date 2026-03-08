# Code Review Skill 使用说明

## 功能概述

代码审查技能提供自动化的代码质量检查功能，帮助发现代码中的问题、安全隐患和性能瓶颈。

## 工具列表

### 代码审查
- `review_code`: 审查单个文件的代码质量
- `review_project`: 审查整个项目的代码结构

### 专项检查
- `check_security`: 检查代码安全问题
- `check_performance`: 检查代码性能问题
- `suggest_refactoring`: 提供重构建议

## 使用示例

### 审查单个文件
```python
review_code(file_path="D:/my_project/app/main.py")
```

### 审查整个项目
```python
review_project(project_path="D:/my_project", max_files=20)
```

### 安全检查
```python
check_security(file_path="D:/my_project/app/auth.py")
```

### 性能检查
```python
check_performance(file_path="D:/my_project/app/utils.py")
```

### 重构建议
```python
suggest_refactoring(file_path="D:/my_project/app/models.py")
```

## 检查项说明

### review_code 检查项
- 语法错误
- 代码风格 (PEP8)
- 潜在 bug
- 代码复杂度
- 命名规范
- 常见问题（print、TODO、通配符导入等）

### check_security 检查项
- eval() 使用
- exec() 使用
- os.system() 命令注入风险
- subprocess shell=True 使用
- pickle.load() 反序列化风险
- 硬编码敏感信息（密码、密钥、API key）

### check_performance 检查项
- range(len()) 使用
- 循环中频繁 append
- 不必要的 sleep
- 列表拼接优化
- 全局变量使用

### suggest_refactoring 分析项
- 函数长度
- 参数数量
- 嵌套深度
- 类方法数量
- 重复代码

## 输出格式

审查结果包含以下信息：
- ❌ 严重问题
- ⚠️ 警告
- ℹ️ 建议
- 统计信息（问题数、警告数、建议数）

## 注意事项

1. 支持 Python 文件（.py）
2. 项目审查会自动跳过常见忽略目录（__pycache__, .git, venv 等）
3. 审查结果仅供参考，建议结合人工审查
4. 某些检查可能存在误报，需要人工判断