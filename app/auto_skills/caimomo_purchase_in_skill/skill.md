# Skill

## Name
caimomo_purchase_in_skill

## Version
1.0.0

## Description
菜么么库存管理系统采购入库操作技能 - 同步执行，用于打开菜么么库存页面并导航到采购入库功能

本技能专门用于菜么么库存管理系统的采购入库操作，包含完整的同步执行流程：
1. 打开菜么么库存管理系统页面
2. 展开"库存管理"菜单
3. 点击"采购入库"选项
4. 等待采购入库页面加载完成

## 特性
- **同步执行**：所有操作步骤按顺序同步执行，确保操作可靠性
- **错误处理**：包含完善的错误处理和异常捕获
- **步骤记录**：详细记录每个操作步骤的执行情况
- **浏览器保持**：操作完成后浏览器保持打开状态，用户可继续操作

## Entry
app.auto_skills.caimomo_purchase_in_skill.scripts

## Tools
- open_caimomo_purchase_in: 打开菜么么库存管理系统并导航到采购入库页面

## 工具参数
- url: 菜么么库存页面URL，默认为库存管理页面 (https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx)
- headless: 是否无头模式，默认False（显示浏览器）

## 返回值
- success: 操作是否成功
- message: 操作结果消息
- steps: 详细的操作步骤记录
- error: 错误信息（如果有）

## Platforms
- Windows

## Dependencies
- playwright>=1.57.0,<1.58.0

## 使用示例
```python
from app.auto_skills.caimomo_purchase_in_skill.scripts.open_caimomo_purchase_in import open_caimomo_purchase_in_sync

# 同步执行
result = open_caimomo_purchase_in_sync(headless=False)
if result["success"]:
    print("采购入库页面已成功打开")
else:
    print(f"操作失败: {result['error']}")
```

## References
- references/usage.md