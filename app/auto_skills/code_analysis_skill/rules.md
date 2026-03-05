=== 代码分析操作规范 ===
1) 文件类型识别：使用 analyze_code_file 时明确指定file_type参数，确保正确解析代码结构。
2) 批量分析：使用 analyze_directory_code 进行批量分析时，通过file_extensions参数限制分析范围，避免处理无关文件。
3) API提取：使用 extract_api_endpoints 时，结合file_type参数提高API识别准确性。
4) 性能考虑：对大型项目进行分析时，采用分批处理策略，避免内存溢出。
5) 结果验证：分析完成后验证结果完整性，确保关键代码元素被正确提取。