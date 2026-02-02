# Usage

## Scope
PPT 生成技能，用于创建生动形象的演示文稿

## Tools
- create_ppt

## Examples
- 生成基础PPT
  - 调用:
    - title: "项目汇报"
    - content:
      - "目录"
      - {"title":"背景","paragraphs":["行业规模持续增长","用户需求快速变化"]}
      - {"title":"要点","bullets":["问题1","方案2"],"highlights":["关键结论"]}
    - output_path: "D:/outputs/project_brief.pptx"
    - theme: "professional"
- 图文混排与主题
  - 调用:
    - title: "市场洞察"
    - content:
      - {"title":"数据概览","bullets":["增长18%","渗透率提升"],"images":["D:/assets/chart.png"]}
      - {"title":"视觉展示","images":["https://example.com/hero.png"]}
    - output_path: "D:/outputs/market_insight.pptx"
    - theme: "vivid"

## Inputs
- title: PPT 标题
- content: 幻灯片列表，支持字符串或字典
  - 字符串:
    - 单行：作为幻灯片标题（仅标题页）
    - 多行：第一行作为标题，后续行自动拆分为段落/要点（见“纯文本自动拆分”）
  - 字典:
    - 标准字段:
      - title: 幻灯片标题
      - paragraphs: 段落列表（字符串或字符串列表）
      - bullets: 要点列表（字符串或字符串列表）
      - highlights: 重点结论列表（字符串或字符串列表）
      - images: 图片路径或URL（字符串或字符串列表）
    - 常见字段别名（为兼容 Agent 可能生成的结构）:
      - paragraphs 支持: content | text | body | desc | description
      - bullets 支持: points | items | outline | list
      - highlights 支持: key_points | keypoints | conclusion
      - images 支持: image | image_url | image_path | img
- output_path: 输出 .pptx 路径
- theme: professional | vivid | dark | fresh

## 纯文本自动拆分
- 当某一页传入字符串且包含多行时：
  - 第 1 行：作为该页标题
  - 后续行：
    - 以 `-` / `•` / `*` 开头：识别为要点 bullets
    - 以 `1.` / `1、` 这类序号开头：识别为要点 bullets
    - 其它：识别为段落 paragraphs

## 图片说明
- 本地图片：建议使用绝对路径，例如 `D:/assets/chart.png`
- 网络图片：支持 `http://` 或 `https://`，会先下载到临时文件再插入
  - 若运行环境无法访问外网，会在返回的 errors 中提示“图片下载失败”，此时建议改用本地图片路径

## Outputs
- success: 是否成功
- output_path: 输出文件路径
- slides_count: 幻灯片数量
- errors: 图片下载或插入失败信息列表
