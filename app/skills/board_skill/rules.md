=== 多 Agent 协作（公告板）===
1) 只要调用 run_role_agent / run_role_agents_parallel，必须显式给出 workdir 或 output_dir，并与用户指定的“工作目录/目标目录”一致；禁止让子 Agent 默认落到当前项目目录。
2) 子 Agent 运行终端命令（run_shell_command）时，除非明确需要其他目录，否则一律传 cwd=workdir（或 cwd=output_dir），保证相对路径稳定。
3) 文件产物（代码/脚本/数据/截图）统一写到 workdir（或 output_dir）下，避免散落到项目目录。
4) 若用户未指定工作目录：优先使用环境变量 AGENT_WORKDIR（若存在）；否则使用公告板默认输出目录。
