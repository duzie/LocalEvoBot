# Skill

## Name
file_skill

## Version
1.0.0

## Description
文件读写操作。支持自动编码检测、大文件处理、备份恢复。

## Entry
app.skills.file_skill.scripts

## Tools
- read_file: 读取文件内容（支持自动编码检测）
- write_file: 写入文件内容（支持自动备份）
- append_file: 追加内容到文件
- file_organize: 按后缀整理文件

## Platforms
- Windows

## When to Use
- 需要读取配置文件时
- 需要写入日志或结果时
- 需要追加内容到现有文件时
- 需要整理目录文件时

## When NOT to Use
- 大文件（>100MB）使用 large_file_processing_skill
- 代码编辑使用 safe_file_editing_skill
- 需要事务性操作时

## References
- references/usage.md
