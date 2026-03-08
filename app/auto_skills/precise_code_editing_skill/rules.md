=== 精准代码编辑规则 ===
1) **Python 代码修改优先使用 AST 工具**：使用 `ast_parse_replace` 替换函数、类、导入语句，保持代码结构完整性。
2) **JavaScript 代码修改使用 JS AST 工具**：使用 `js_ast_parse_replace` 替换函数（普通函数、箭头函数）、类、变量，支持 ES6+ 语法。
3) **精确查找代码块位置**：使用 `find_code_block` 查找函数、类、变量的精确行号范围，支持 Python 和 JavaScript，自动检测语言类型。
4) **文本替换失败时使用调试模式**：使用 `debug_text_replace` 进行智能匹配，自动处理换行符差异、编码问题、空白差异，提供详细的失败原因分析。
5) **修改前检测文件格式**：使用 `detect_file_format` 检测文件编码、换行符、缩进风格，避免格式问题导致的修改失败。
6) **分析 JavaScript 结构**：使用 `analyze_js_structure` 分析 JS 文件的函数、类、变量、导入导出结构，了解代码组织。
7) **验证修改结果**：修改后使用 `validate_code_changes` 验证语法正确性，确保代码可正常运行。
8) **工具选择策略**：
   - Python 代码：ast_parse_replace > debug_text_replace
   - JavaScript 代码：js_ast_parse_replace > debug_text_replace
   - 未知语言：debug_text_replace（带 fuzzy_match=True）
