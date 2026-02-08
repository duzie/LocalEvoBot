# Skill

## Name
open_caimomo_target_page

## Version
1.0.0

## Description
菜么么菜单导航技能 - 支持按模块进入菜单页，并动态定位主菜单与子选项

本技能支持任意菜单/选项组合，包含完整的执行流程：
1. 打开模块对应菜单页（或使用自定义URL）
2. 定位并点击指定主菜单（为空时默认首项）
3. 定位并点击指定子选项（为空时默认首项）
4. 等待目标页面加载完成

## 特性
- **动态菜单**：主菜单与子选项均可自定义文本
- **纯文本定位**：优先依赖文本与层级结构定位
- **步骤记录**：详细记录每个操作步骤的执行情况
- **浏览器保持**：操作完成后浏览器保持打开状态，用户可继续操作

## Entry
app.auto_skills.open_caimomo_target_page.scripts

## Tools
- open_caimomo_target_page: 打开菜么么系统并定位主菜单与子选项
- create_caimomo_purchase_in_bill: 打开菜么么系统在采购入库页面执行新增流程（选择部门/供应商、添加物料、编辑数量与单价并保存）

## 工具参数
- url: 菜么么系统菜单页URL，默认 https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx
- headless: 是否无头模式，默认False（显示浏览器）
- module: 模块名称（库存/总部/会员/报表/微信系统/营销中心/系统设置）
- target_menu: 主菜单文本（如：库存管理、报表分析、连锁物流单据），为空则自动选择首个主菜单
- target_option: 子选项文本（如：采购入库、部门进销存汇总表、要货单），为空则自动选择首个子选项

## 返回值
- success: 操作是否成功
- message: 操作结果消息
- steps: 详细的操作步骤记录
- error: 错误信息（如果有）
- screenshot: 错误截图文件名（如果有）

## Platforms
- Windows

## Dependencies
- playwright>=1.57.0,<1.58.0

## 使用示例
```python
from app.auto_skills.open_caimomo_target_page.scripts.open_caimomo_target_page import open_caimomo_target_page
from app.auto_skills.open_caimomo_target_page.scripts.create_purchase_in_flow import create_caimomo_purchase_in_bill

result = open_caimomo_target_page(
    module="库存",
    headless=False,
    target_menu="库存管理",
    target_option="采购入库"
)
if result["success"]:
    print("目标页面已成功打开")
else:
    print(f"操作失败: {result['error']}")

# 采购入库新增流程
flow = create_caimomo_purchase_in_bill(
    headless=False,
    supplier="菜嬷嬷",
    department="仓库",
    materials=[
        {"keyword": "土豆", "quantity": 10, "unit_price": 3.5},
        {"keyword": "辣椒", "quantity": 5, "unit_price": 6.2}
    ],
    save_and_continue=False
)
print(flow["message"])
```

## References
- references/usage.md
