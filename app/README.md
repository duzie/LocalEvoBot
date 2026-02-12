# app

核心 Python 代码目录，包含 Agent 逻辑、技能体系与集成模块。

## 目录结构
- agent.py: Agent 创建与主执行逻辑
- prompts.py: 工具/技能提示模板
- integrations/: 外部集成与心跳任务
- skills/: 核心技能（稳定、通用）
- auto_skills/: 自动生成或业务扩展技能
- data/: 运行时数据与缓存（本地）

## 技能组织
- 每个技能目录包含 skill.md 与 references/usage.md
- scripts/ 下是 @tool 工具实现

## 添加技能
### 手动添加
1. 在 app/skills/<skill_name>/ 创建目录结构：
   - skill.md
   - scripts/（工具实现）
   - references/usage.md
2. 在 skill.md 的 ## Entry 中填写入口包路径，例如：
   - app.skills.<skill_name>.scripts
3. 在 scripts/ 下编写工具模块，导出 @tool 装饰的函数或 BaseTool 子类
4. 运行 reload_skills 触发热加载

### 自动生成
- 使用 scaffold_skill 生成脚手架
- 用 write_tool_code 写入工具实现
- 用 reload_skills 热加载
- 用 promote_skill 将 auto_skills 迁移为正式 skills

## 注册与加载规则
- 入口在 app/skills/registry.py 的 load_skills
- 默认扫描 app.skills 与 app.auto_skills
- 优先读取 skill.md 中的 ## Entry 作为加载入口
- 若未提供 Entry，则按 app.skills.<skill_name>.scripts 约定加载
- scripts 包内的 @tool 或 BaseTool 子类会被自动发现并注册

## 运行入口
- 项目入口在仓库根目录 main.py
