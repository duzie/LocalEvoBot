# WORKFLOW.md - 任务执行流程

## 标准工作流

```
┌─────────────────────────────────────────────────────────────┐
│  0. Plan (任务拆解)                                          │
│     - 复杂任务？→ get_task_planning_rules                  │
│     - 创建计划 → create_task_plan                          │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Recall (经验检索) ← 必须先做！                           │
│     - 复杂操作？→ get_operation_experience                 │
│     - 历史对话？→ search_short_term_memory                 │
│     - 提炼要点 → 约束条件                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Check (技能检查)                                         │
│     - 缺技能？→ scaffold_skill → write_tool_code           │
│     - 缺依赖？→ install_packages                            │
│     - 重载技能？→ reload_skills (仅在有变更时)               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Execute (执行)                                           │
│     - 结合经验和技能执行                                    │
│     - 跨文件？→ analysis index                              │
│     - 记录工具调用轨迹                                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Verify (验证) ← 关键步骤！                               │
│     - 修改代码？→ 运行测试                                  │
│     - 修改配置？→ 验证生效                                  │
│     - Web 操作？→ 截图确认                                   │
│     - **禁止** 仅凭静态分析就宣称修复                       │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  5. Record (沉淀)                                            │
│     - 解决难题？→ add_operation_experience                 │
│     - 内容：关键步骤/关键参数/常见坑/验证方法               │
│     - **不要** 包含密钥等敏感信息                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  6. Cleanup (清理)                                           │
│     - 删除临时文件                                          │
│     - 自检任务是否闭环                                      │
│     - 输出 STATE: DONE                                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 各阶段详细说明

### 0. Plan - 任务拆解

**何时使用**:
- 任务 > 3 步
- 验收标准不明确
- 影响面大
- 需要多人协作

**工具**:
- `get_task_planning_rules` - 获取拆解规则
- `create_task_plan` - 创建计划
- `read_task_plan` - 读取计划
- `mark_task_completed` - 标记完成

**示例**:
```
用户：帮我改造这个项目，注入"灵魂"

Plan:
1. 创建身份文件 (SOUL.md, IDENTITY.md, USER.md, AGENTS.md)
2. 改造 prompts.py，加载身份文件
3. 创建记忆维护工具
4. 注册心跳任务
```

---

### 1. Recall - 经验检索

**何时必须检索**:
- 流程/排错/修复/优化类问题
- 涉及高频域：playwright/uia/ocr/excel/ppt/音频/公告板/whatsapp/mcp/http
- 输入含路径/命令/API/系统名
- 用户问题含"刚才/上次/之前/前面/继续/照你说的"等指代

**工具**:
- `get_operation_experience` - 检索长期记忆 (RAG)
- `search_short_term_memory` - 检索短期记忆 (SQLite)

**示例**:
```
# 检索 Playwright 点击失败的经验
get_operation_experience(
    query="playwright 点击失败怎么办",
    system_filter="Playwright",
    n_results=3
)

# 检索历史对话
search_short_term_memory(
    query="刚才说的配置文件",
    limit=10
)
```

---

### 2. Check - 技能检查

**技能生成流程**:
```
scaffold_skill (生成脚手架)
    ↓
write_tool_code (编写代码)
    ↓
install_packages (安装依赖，如需要)
    ↓
reload_skills (热加载) ← 仅在有变更时
    ↓
run_skill_test_cases (测试)
```

**禁止**:
- ❌ 无变更时 `reload_skills`
- ❌ 跳过测试直接转正
- ❌ 手动修改 auto_skills（应该通过生成流程）

---

### 3. Execute - 执行

**最佳实践**:
1. **先备份再修改**: `safe_file_backup`
2. **小步快跑**: 每次修改 < 50 行
3. **记录轨迹**: 工具调用自动记录到 transcript

**跨文件分析**:
```
# 优先使用 deep_analysis_skill
read_files_to_analysis_index(file_paths=[...])
    ↓
query_analysis_index(query="...")
    ↓
# 避免把整段源码直接塞进对话历史
```

---

### 4. Verify - 验证

**验证方式**:
| 修改类型 | 验证方式 |
|----------|----------|
| 代码修改 | 运行测试 / lint / 编译 |
| 配置修改 | 重启服务 / curl 测试 |
| Web 操作 | 截图 / 检查元素 |
| 文件操作 | 检查文件存在/内容 |

**示例**:
```python
# 修改代码后运行测试
run_pytest(test_path="tests/test_feature.py")

# 修改配置后验证
run_shell_command("curl http://localhost:5011/health")

# Web 操作后截图
take_screenshot(output_path="verify.png")
```

---

### 5. Record - 沉淀

**何时必须记录**:
- 解决新问题
- 验证新方案
- 遇到常见坑

**内容要求**:
```python
add_operation_experience(
    system_name="Playwright",
    content="点击失败时先等待元素可见：wait_for_selector(..., state='visible')",
    tags=["playwright", "click", "wait"],
    scope="Web 自动化",
    project_id="localevobot"
)
```

**不要包含**:
- ❌ 密钥/密码
- ❌ 个人隐私信息
- ❌ 临时调试信息

---

### 6. Cleanup - 清理

**检查清单**:
- [ ] 删除临时文件
- [ ] 关闭打开的服务
- [ ] 释放文件锁
- [ ] 输出 STATE: DONE

---

## 状态标记规范

### STATE: DONE
- 任务完成
- 等待用户确认
- 无法继续（需要用户输入）

### STATE: CONTINUE
- 下一步会调用工具
- 任务进行中
- 需要多轮执行

**规则**:
- 只有下一步会调用工具时才输出 `STATE: CONTINUE`
- 同一工具使用相同参数最多重试 2 次
- 如果连续两轮对话没有产生新的有效信息，必须输出 `STATE: DONE`

---

## 响应示例

### 示例 1：代码修复

```
用户：main.py 有个 bug，启动时报错

助手：我先读取 main.py 分析一下错误...
（调用 read_document_part）
STATE: CONTINUE

助手：发现第 50 行有语法错误，现在修复...
（调用 safe_file_editing）
STATE: CONTINUE

助手：修复完成，运行验证...
（调用 run_shell_command: python main.py）
✅ 服务启动成功
📝 已记录经验到 RAG 知识库
STATE: DONE
```

### 示例 2：Web 自动化

```
用户：帮我在淘宝上搜索"macbook"

助手：我先打开淘宝网页...
（调用 playwright_open）
STATE: CONTINUE

助手：页面加载完成，搜索"macbook"...
（调用 playwright_fill + playwright_click）
STATE: CONTINUE

助手：搜索结果已加载，截图确认...
（调用 take_screenshot）
✅ 搜索完成，共找到 1000+ 商品
STATE: DONE
```

---

_这个工作流是你行动的指南。随着你学习成长，优化它。_
