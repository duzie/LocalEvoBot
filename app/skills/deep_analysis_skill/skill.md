# Skill

## Name
deep_analysis_skill

## Version
1.0.0

## Description
深度代码分析技能，用于防止上下文窗口爆炸，支持多文件与项目级关联分析。

## Entry
app.skills.deep_analysis_skill.scripts

## Tools
- get_project_skeleton_analysis: 扫描项目骨架并提取符号，定位候选文件
- read_files_to_analysis_index: 将文件内容写入分析索引，避免全文进入会话历史
- get_analysis_index_status: 查询索引状态、文件数量和总体规模
- query_analysis_index: 基于索引做聚合分析，返回跨文件关系与证据
- clear_analysis_index: 清空索引，释放资源并开始新会话

## Platforms
- Windows
- Linux
- macOS

## References
- rules.md
