# Skill

## Name
uia_skill

## Version
1.0.0

## Description
Windows UI Automation 控件定位与点击。

## Entry
app.skills.uia_skill.scripts

## Tools
- uia_find_control: 按窗口与控件属性定位控件并返回坐标
- uia_click_control: 直接点击控件
- uia_list_controls: 枚举窗口控件树
- uia_list_windows: 列出所有顶级窗口（含标题、PID、进程名），解决“知道进程不知窗口名”的问题
- uia_dump_tree: 获取窗口的完整控件树（分层分析），支持 JSON/XML
- uia_activate_window: 激活或还原指定窗口

## Platforms
- Windows

## References
- references/usage.md
