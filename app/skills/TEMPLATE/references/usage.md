# {skill_name} 使用指南

## 工具清单

| 工具名 | 功能 | 参数 | 示例 |
|--------|------|------|------|
| {tool_name} | {功能} | param1, param2 | `{tool_name}("test", 20)` |

## 使用场景

### 场景 1：{场景名称}

```python
result = {tool_name}.invoke({"param1": "value"})
if result.get("ok"):
    print(result.get("message"))
else:
    print(f"失败：{result.get('error')}")
```

## 常见错误

### 错误 1：invalid_param

**原因**: 参数验证失败

**修复**: 检查参数是否符合要求

### 错误 2：unexpected_error

**原因**: 意外错误

**修复**: 查看日志，报告问题

## 最佳实践

1. **先验证再执行**: 检查参数有效性
2. **使用 SkillException**: 便于统一错误处理
3. **返回标准化**: 使用 ok_payload/error_payload
4. **记录经验**: 解决新问题后调用 `add_operation_experience`

## 相关技能

- {related_skill_1}
- {related_skill_2}
