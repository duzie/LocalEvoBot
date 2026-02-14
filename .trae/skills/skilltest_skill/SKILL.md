---
name: "skilltest_skill"
description: "Validates that generated skills can load and that required capabilities meet the original requirements. Invoke when you need to verify skill loadability and requirement coverage."
---

# SkillTest

用于验证新生成技能是否可加载，并评估是否满足最初需求的功能指标。

## 适用场景
- 新技能生成后需要快速验证是否可加载
- 需要对照最初需求，检查功能是否达到预期

## 测试范围
1. 可加载性
   - 扫描技能目录结构
   - 验证 skill.md 与 Entry 定义
   - 检查工具可被注册与发现

2. 需求达标性
   - 读取最初需求描述
   - 生成需求-功能对照清单
   - 给出通过/未通过结论与差距

## 输入
- skill_name: 目标技能名称
- requirement_text: 最初需求描述

## 输出
- loadability: 可加载性检测结果（通过/失败 + 原因）
- coverage: 需求覆盖结论（通过/部分/未通过）
- gaps: 未覆盖项与改进建议

## 执行步骤（建议流程）
1. 读取技能目录与 skill.md
2. 验证 Entry 是否可解析并可加载
3. 对照 requirement_text 输出覆盖报告
4. 若存在差距，列出最小补齐方案
