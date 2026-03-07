=== 代码修改规则 ===
1) **代码文件修改必须使用行号定位**：优先使用 `replace_lines`、`insert_lines`、`delete_lines`，通过 `get_line_content` 确认行号后操作。
2) **禁止使用锚点搜索**：所有基于正则表达式或文本模式的锚点匹配工具（如 replace_block_between_anchors、safe_block_update）已废弃，因其在代码文件中容易匹配错误或重复。
3) **行号操作流程**：
   - 步骤1：使用 `get_line_content(file_path, line_number, context_lines=5)` 查看目标行及上下文
   - 步骤2：确认行号正确后，使用 `replace_lines`/`insert_lines`/`delete_lines` 执行操作
4) **大文件分块读取**：使用 `read_large_file_chunks` 分块读取大文件，避免一次性加载。
5) **备份与恢复**：所有修改操作自动创建 .bak 备份，必要时使用 `restore_from_backup` 恢复。
6) **完整性校验**：修改后使用 `validate_file_integrity` 检查文件完整性。
