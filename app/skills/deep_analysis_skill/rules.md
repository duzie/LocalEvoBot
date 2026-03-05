=== 深度分析流程（项目级/多文件）===
1) 进入代码分析任务时，优先使用 deep_analysis_skill，不要直接连续调用 read_document_part 读取多个大文件。
2) 必须先调用 get_project_skeleton_analysis 定位候选文件，再调用 read_files_to_analysis_index 建立索引。
3) 读取索引时遵循分批策略：每批 1-8 个文件，先核心调用链，后外围依赖，避免一次性全量入索引。
4) 需要回答“跨文件关系/调用链/模块职责”时，必须通过 query_analysis_index 提问，不得仅凭工具轨迹或文件名推断。
5) 输出结论必须带证据意识：说明涉及哪些文件与关键片段；证据不足时先补充索引再回答。
6) read_document_part 仅用于小范围精读与定位（例如单文件局部片段核对），不能作为项目级主分析通道。
7) 分析结束后，如任务已完成或切换主题，调用 clear_analysis_index 清理索引，避免旧上下文污染。
