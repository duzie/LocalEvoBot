# Usage

## Scope
大文件安全处理技能，支持分块读取、增量编辑、备份恢复等功能

## Tools
- read_large_file_chunks
- safe_file_merge
- extract_and_merge_class
- truncate_incomplete_tail
- replace_block_between_anchors
- safe_block_update
- validate_file_integrity
- restore_from_backup

## Examples
- 修改场景优先区间替换：replace_block_between_anchors(..., expected_old="def foo")
- 锚点失败才允许行号兜底：replace_block_between_anchors(..., allow_fallback=True, start_line=120, end_line=180, expected_old="def foo")
- 大块替换增加内容校验：safe_block_update(..., expected_old="def foo")
- 避免重复写入：replace_block_between_anchors(..., skip_if_present=True)
- 全链路精确修改：replace_block_between_anchors(..., expected_old="def foo", skip_if_present=True, allow_fallback=False)
- 在函数前插入新函数：safe_file_merge(..., insert_position="before_pattern", anchor_pattern="^def target_function\\(", skip_if_present=True)
- 修改完成后校验：validate_file_integrity(...)
