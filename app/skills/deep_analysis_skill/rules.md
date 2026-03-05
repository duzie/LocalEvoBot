=== 深度分析流程（项目级/多文件）===
1) 进入代码分析任务时，优先使用 deep_analysis_skill。
2) 必须先调用 get_project_skeleton_analysis 定位候选文件，再调用 read_files_to_analysis_index 建立索引。
3) 读取索引时遵循分批策略：每批 1-8 个文件，先核心调用链，后外围依赖，避免一次性全量入索引。
4) 代码阅读/定位/查找必须使用索引链路，禁止用 read_document_part 或 read_large_file_chunks 作为主通道。
5) 仅在单文件局部核对时允许 read_document_part，且范围不超过 200 行或 4000 字符。
6) 需要回答“跨文件关系/调用链/模块职责”时，必须通过 query_analysis_index 提问，不得仅凭工具轨迹或文件名推断。
7) 优先使用 file_directory_skill/file_skill 获取目录与文件内容，避免用 run_shell_command 做文件读取。
8) 输出结论必须带证据意识：说明涉及哪些文件与关键片段；证据不足时先补充索引再回答。
9) 分析结束后，如任务已完成或切换主题，调用 clear_analysis_index 清理索引，避免旧上下文污染。
