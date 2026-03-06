=== 文档处理操作规范 ===
1) 大文件处理：使用 read_document_part 分块读取大文件，避免内存溢出；合理设置max_chars参数。
2) 编码处理：处理不同编码文档时显式指定encoding参数，避免乱码问题。
3) 内容提取：使用 extract_document_section 精确提取特定章节内容，利用section_marker参数准确定位。
4) 安全写入：使用 insert_text_at_line 插入内容时，建议启用备份功能避免意外覆盖。
5) 性能优化：对于大文件搜索，使用search_document的context_lines限制上下文范围，提高检索效率。