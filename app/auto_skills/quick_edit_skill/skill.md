# Skill

## Name
quick_edit_skill

## Version
1.0.0

## Description
快速文件编辑工具。无规则约束，直接修改。⚠️ 仅用于简单文本替换

## Entry
app.auto_skills.quick_edit_skill.scripts

## Tools
- quick_edit: 快速编辑文件（直接替换文本）

## Platforms
- Windows
- Linux
- macOS

## When to Use
- ✅ 修改 < 5 行
- ✅ 简单文本替换
- ✅ 用户明确知道后果
- ✅ 快速修改配置文件
- ✅ 修改注释/字符串

## When NOT to Use
- ❌ 修改函数/类定义
- ❌ 改变代码逻辑
- ❌ 重要配置文件
- ❌ 需要语法验证的场景

## ⚠️ 警告
- 不会验证语法
- 不会记录经验
- 不会自动备份（会创建.bak 文件）
- 仅用于简单修改

## References
- references/usage.md
