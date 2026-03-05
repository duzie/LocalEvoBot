=== 通用文本替换 ===
1) 简单文本替换使用 `simple_text_replace`。
2) **代码文件修改禁止使用 `replace_block_between_anchors`**：建议在修改代码文件时慎用。对于 Markdown 这种文档结构修改，我会建议 Agent 未来优先使用 safe_block_update 的 replace_between 模式，并确保 new_block 不包含锚点，或者明确使用全量替换模式。
3) **代码修改推荐方案**：
   - Python 文件：优先使用 `python_code_edit`（AST 语法树）
   - C# 文件：优先使用 `csharp_code_edit` 或 `simple_text_replace`（完整块替换）
   - JSON 文件：优先使用 `json_file_edit`
   - 其他文件：使用 `safe_block_update` 并提供 `expected_old` 校验
4) `replace_block_between_anchors` 仅限简单配置文件使用，且必须验证 `expected_old`。
5) 锚点失败才允许行号兜底。
6) 插入/替换开启 `skip_if_present`；`insert_text_at_line` 需 `expected_pattern`，重叠开启 `dedupe_overlap`。
7) `safe_file_merge` 仅做新增插入，函数定义必须 `before_pattern` 或区间替换，禁止 `after_pattern`。