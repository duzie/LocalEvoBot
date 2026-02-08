# openscmskill 使用说明

## 功能概述
`openscmskill` 是一个用于自动化访问菜么么SCM系统库存页面的技能。它使用Playwright打开指定URL，并可选择性地获取页面的无障碍快照。

## 工具函数

### open_scm_page
打开菜么么库存页面并获取无障碍快照。

#### 参数
- `url` (str, 可选): 目标网址，默认为 `"https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx"`
- `headless` (bool, 可选): 是否无头模式，默认 `False`（显示浏览器）
- `get_accessibility_snapshot` (bool, 可选): 是否获取无障碍快照，默认 `True`

#### 返回值
返回一个包含以下字段的字典：
- `success` (bool): 操作是否成功
- `url` (str): 请求的URL
- `final_url` (str): 最终加载的URL（可能发生重定向）
- `title` (str): 页面标题
- `is_caimomo_page` (bool): 是否检测到菜么么页面
- `accessibility_snapshot` (dict, 可选): 无障碍快照数据
- `status_code` (int, 可选): HTTP状态码
- `error` (str, 可选): 错误信息
- `message` (str): 操作结果消息

#### 使用示例

```python
# 基本用法：打开菜么么库存页面
result = open_scm_page()

# 指定URL和无头模式
result = open_scm_page(
    url="https://v2.caimomo.com/ScmWeb/SCM/Menu4.aspx",
    headless=True,
    get_accessibility_snapshot=True
)

# 检查操作结果
if result["success"]:
    print(f"页面标题: {result['title']}")
    print(f"最终URL: {result['final_url']}")
    print(f"是菜么么页面: {result['is_caimomo_page']}")
    
    if result.get("accessibility_snapshot"):
        print("已获取无障碍快照")
else:
    print(f"操作失败: {result.get('error')}")
```

## 依赖要求
- Python 3.7+
- Playwright: `pip install playwright`
- Chromium浏览器: `playwright install chromium`

## 安装依赖
```bash
pip install playwright
playwright install chromium
```

## 注意事项
1. **浏览器保持打开**: 该工具在成功打开页面后不会自动关闭浏览器，需要手动管理浏览器生命周期。
2. **网络连接**: 需要稳定的网络连接来访问菜么么系统。
3. **登录状态**: 如果目标页面需要登录，需要先处理登录流程。
4. **页面重定向**: 菜么么系统可能会进行重定向，最终URL可能与初始URL不同。

## 错误处理
- 如果缺少Playwright依赖，会返回相应的错误信息。
- 如果网络连接失败或页面无法加载，会返回详细的错误信息。
- 如果获取无障碍快照失败，会在结果中包含错误信息但不影响主要操作。

## 应用场景
1. **自动化测试**: 自动化访问菜么么系统进行功能测试
2. **无障碍检测**: 获取页面的无障碍快照进行可访问性分析
3. **页面监控**: 定期检查菜么么系统的可用性和页面状态
4. **数据采集**: 作为数据采集流程的第一步，打开目标页面

## 相关技能
- `playwright_accessibility_snapshot`: 获取页面的无障碍快照
- `playwright_open`: 通用的Playwright页面打开功能
- `playwright_navigate`: 页面导航功能