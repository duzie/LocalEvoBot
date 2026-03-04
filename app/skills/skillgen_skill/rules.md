=== 技能生成提示 ===
1) 技能生命周期：缺失工具时执行 scaffold_skill -> write_tool_code -> reload_skills。
2) 代码规范：每个 @tool 函数必须包含 docstring 或 description；避免未使用导出。
3) 变更验证：写入后运行语法与 lint 检查；失败则回滚或修复。
4) 元数据同步：当使用 `write_tool_code` 修改工具签名或逻辑后，**必须**检查并更新同目录下的 `skill.md` (工具列表/Entry)、`usage.md` (使用示例) 及 `rules.md` (Prompt规则)，确保文档与代码一致。
