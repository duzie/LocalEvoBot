# MEMORY.md - 长期记忆 Curated

> 这里记录重要的经验、决策、教训，不是原始对话日志。
> 
> 原始对话日志在 `short_term_markdown/` 目录。

---

## 2026-03-08 - 项目改造

### 注入"灵魂"改造

**背景**: localevobot 项目技术架构完善（45+ 技能、RAG 混合检索、三层记忆），但缺少"灵魂"——身份定义、行为哲学、主动性机制。

**改造内容**:
1. 创建 SOUL.md - 人格定义
2. 创建 AGENTS.md - 行为准则（融合 OpenClaw + localevobot STATE 机制）
3. 创建 WORKFLOW.md - 任务流程
4. 改造 app/prompts.py - 从文件加载身份定义
5. 创建记忆维护工具 - memory_maintenance.py
6. 创建主动性检查工具 - proactive_checks.py

**关键决策**:
- 保留 localevobot 的 STATE 循环机制（与 OpenClaw 不同）
- 融合 OpenClaw 的身份哲学
- 记忆维护从"只存不整理"改为"定期整理"

**学到的教训**:
- 身份定义与代码分离，便于维护
- STATE 机制虽然增加认知负担，但便于调试
- 记忆系统需要定期维护，避免膨胀

### 技术细节

**提示词加载流程**:
```
SOUL.md → AGENTS.md → WORKFLOW.md → 技能规则 (rules.md)
```

**记忆维护周期**:
- 每 3 天：整理 MEMORY.md
- 每 7 天：合并相似经验
- 每月：清理短期记忆归档

**主动检查项目**:
- Git 状态
- 测试覆盖率
- Linter 警告
- 依赖更新
- 磁盘使用

---

_新的记忆会自动添加到这里。定期回顾，删除过期的内容。_
