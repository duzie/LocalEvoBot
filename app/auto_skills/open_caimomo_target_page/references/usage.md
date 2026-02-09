# 菜么么菜单导航技能使用指南

## 概述
本技能用于自动化操作菜么么库存管理系统的菜单导航。支持以**主菜单文本**与**子选项文本**进行纯文本+层级定位，适配不同菜单与功能页面。

## 功能特点
1. **动态菜单**：主菜单与子选项文本可自由指定
2. **纯文本定位**：避免依赖易变的属性（id/class/for），以层级+文本稳定定位
3. **详细日志**：记录每个操作步骤，便于调试与问题排查
4. **错误处理**：完善的异常捕获与错误截图
5. **浏览器保持**：操作完成后浏览器保持打开，便于继续操作

## 使用方式

### 1. 直接调用工具
```python
from app.auto_skills.open_caimomo_target_page.scripts.open_caimomo_target_page import open_caimomo_target_page
from app.auto_skills.open_caimomo_target_page.scripts.create_purchase_in_flow import create_caimomo_purchase_in_bill

# 示例：打开 库存管理 -> 采购入库
result = open_caimomo_target_page(
    module="库存",
    headless=False,
    target_menu="库存管理",
    target_option="采购入库"
)

# 检查结果
if result["success"]:
    print("✅ 目标页面已成功打开")
    print("操作步骤:")
    for i, step in enumerate(result["steps"], 1):
        print(f"  {i}. {step}")
else:
    print(f"❌ 操作失败: {result['error']}")

# 示例：采购入库新增流程
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

### 2. 在Agent中使用
```python
# Agent会自动加载技能，可以直接调用
result = open_caimomo_target_page(
    module="库存",
    headless=False,
    target_menu="库存管理",
    target_option="采购入库"
)
```

## 参数说明

### url
- **类型**: string
- **默认值**: `"https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx"`
- **说明**: 菜么么库存管理系统的入口URL

### headless
- **类型**: boolean
- **默认值**: `False`
- **说明**: 是否使用无头模式（不显示浏览器窗口）
  - `True`: 无头模式，后台运行
  - `False`: 显示浏览器窗口，便于观察操作过程

### module
- **类型**: string
- **示例**: `"库存"`, `"总部"`, `"会员"`, `"报表"`, `"微信系统"`, `"营销中心"`, `"系统设置"`
- **说明**: 直接选择模块菜单页；若提供该参数，会覆盖 url

### target_menu
- **类型**: string
- **示例**: `"库存管理"`, `"报表分析"`, `"连锁物流单据"`
- **说明**: 要展开的主菜单文本，使用纯文本定位；为空时默认选择第一个主菜单

### target_option
- **类型**: string
- **示例**: `"采购入库"`, `"部门进销存汇总表"`, `"要货单"`
- **说明**: 在主菜单下要点击的子选项文本，使用纯文本定位；为空时默认选择第一个子选项

### supplier
- **类型**: string
- **示例**: `"菜嬷嬷"`
- **说明**: 采购入库新增流程中选择的供应商（必填）

### department
- **类型**: string
- **示例**: `"仓库"`
- **说明**: 采购入库新增流程中选择的入库部门（必填）

### materials
- **类型**: array
- **示例**: `[{"keyword": "土豆", "quantity": 10, "unit_price": 3.5}]`
- **说明**: 物料列表，每项支持 keyword/name/goods_name/goods_no 作为匹配关键字，可选 quantity/unit_price/total_price/pieces/memo

### save_and_continue
- **类型**: boolean
- **默认值**: `False`
- **说明**: 是否点击“保存并继续”按钮


## 返回值结构
```json
{
  "success": true,
  "message": "成功打开[库存管理] -> [采购入库]页面",
  "steps": [
    "已加载v2.caimomo.com的cookie",
    "导航到菜单页: https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    "页面加载完成，标题: 库存管理系统",
    "开始定位主菜单: [库存管理]",
    "成功点击主菜单: [库存管理]",
    "主菜单[库存管理]已展开，加载子选项",
    "开始定位子选项: [采购入库]",
    "成功点击子选项: [采购入库]",
    "等待[采购入库]页面加载",
    "目标页面加载完成，当前URL: ...",
    "所有操作完成，浏览器保持打开状态，可继续后续操作"
  ],
  "error": null,
  "screenshot": null
}
```

## 操作流程
1. **初始化环境**：创建页面与扩展环境，加载对应域名的cookie（可选）
2. **打开页面**：导航到菜么么菜单页
3. **展开菜单**：定位并点击目标主菜单
4. **选择功能**：定位并点击目标子选项
5. **等待加载**：等待目标页面完成加载
6. **验证结果**：记录当前URL与步骤，确认操作成功

## 错误处理
技能包含以下错误处理机制：

### 1. 元素定位失败
- 采用纯文本+层级结构定位，避免属性变化导致的失败
- 定位失败会抛出异常并记录错误详情

### 2. 页面加载超时
- 设置合理的超时时间（30秒）
- 网络空闲时继续执行

### 3. 浏览器异常
- 捕获所有异常并记录详细信息
- 错误时尝试截图保存现场

### 4. 资源清理
- 确保浏览器资源正确释放
- 保持浏览器打开状态供用户继续操作

## 常见问题

### Q1: 为什么采用纯文本定位而不是依赖 id/class？
A: 菜么么系统的属性可能随版本更新而变化，纯文本+层级结构更稳定、更通用。

### Q2: 如果页面结构有调整怎么办？
A: 本技能以 `#ulmenu` 为根容器，定位 `section>label` 作为主菜单，`content>ul>li>a` 作为子选项；若结构大改，可调整对应的层级选择器。

### Q3: 如何调试操作过程？
A: 可以通过以下方式调试：
1. 设置 `headless=False` 观察浏览器操作
2. 查看返回的 `steps` 字段了解每个步骤
3. 错误时会自动截图保存现场

### Q4: 是否需要登录？
A: 若目标页面需要登录，可先在同一浏览器上下文完成登录，或确保已加载有效的 cookie。

## 最佳实践
1. **先测试**：首次使用前，先设置 `headless=False` 测试操作流程
2. **检查网络**：确保网络连接稳定，菜么么系统可访问
3. **调整选择器**：若菜单层级结构有调整，更新对应的 XPath 选择器
4. **错误处理**：在生产环境中添加适当的错误处理和重试机制

## 扩展建议
如果需要扩展本技能，可以考虑：
1. 添加登录功能
2. 支持更多功能页面（如出库、盘点、要货单、报表等）
3. 添加页面数据提取能力
4. 支持批量导航与自动回退
