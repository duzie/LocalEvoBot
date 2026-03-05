=== 文件编辑安全 ===
1) 修改前先备份，失败回滚：`safe_file_backup` / `restore_from_backup`。
2) Python 文件修改必须优先使用 `python_code_edit`，它基于 AST 语法树，能自动处理缩进和语法检查，禁止使用正则表达式或全量覆盖修改 Python 代码。
3) JSON 文件修改必须优先使用 `json_file_edit`，禁止使用正则替换。
4) 简单文本替换使用 `simple_text_replace`。
5) C#文件修改：新增类/方法强烈建议使用 `csharp_code_edit` 以确保正确插入 Namespace 内部；避免使用文件末尾追加。
6) 修改代码后必须运行 `validate_code_syntax` 检查语法 (Python/JS/JSON/C#)。
