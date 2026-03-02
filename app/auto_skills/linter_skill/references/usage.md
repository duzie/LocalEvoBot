# Usage

## Scope
代码静态分析技能，用于在代码修改后自动检测错误，支持 Python (Ruff/Compile)

## Tools
- run_linter: 运行代码检查工具，返回错误列表

## Examples
- 检查单个 Python 文件: `run_linter(file_path="app/utils.py")`
- 配合代码编辑使用: 修改代码后运行 `run_linter` 确保无语法错误
