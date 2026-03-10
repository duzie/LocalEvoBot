# Safe File Editing Skill - 安全文件编辑技能

提供安全的文件编辑功能，包含备份、验证、回滚机制。

## Entry
app.auto_skills.safe_file_editing_skill.scripts

## Tools
- safe_edit_file: 安全编辑文件（备份 + 验证 + 回滚）
- create_backup: 创建文件备份
- rollback_edit: 回滚文件修改
- verify_edit: 验证文件修改
- list_backups: 列出备份历史

## Platforms
- Windows
- Linux
- macOS

## When to Use
- ✅ 修改现有代码文件
- ✅ 修改超过 5 行
- ✅ 修改函数/类定义
- ✅ 重要配置文件
- ✅ 需要语法验证的场景

## When NOT to Use
- ❌ 修改 < 5 行（用 quick_edit）
- ❌ 简单文本替换（用 quick_edit）
- ❌ 用户明确不需要备份

## ⚠️ 警告
- 会自动创建备份
- 会验证语法
- 会记录经验
- 高危修改前必须提示用户确认

## References
- references/usage.md
- references/usage_syntax.md
