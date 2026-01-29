# 继续开发文档：Web 可视化控制台

## 目标
构建一个适配移动端的 Web 控制台，用于管理 Agent、配置环境变量、监控运行状态以及直接调用 API。

## 技术栈选择
- **后端**: FastAPI (轻量、高性能、易于集成现有 Python 代码)
- **前端**: React + Tailwind CSS (响应式设计，完美适配手机端)
- **通信**: REST API + WebSocket (实时日志流)

## 功能模块规划

### 1. 配置管理 (Configuration)
- **环境变量编辑器**: 
  - 可视化编辑 `.env` 文件
  - 支持添加/修改/删除 API Key、模型参数等
  - 修改后自动重载配置
- **技能管理**:
  - 查看已加载的 Skills
  - 手动触发 `reload_skills`

### 2. 运行监控 (Monitoring)
- **实时日志**: 通过 WebSocket 推送 Agent 运行日志
- **任务状态**: 查看当前任务计划 (`task_plan`) 及其进度
- **系统资源**: 简单监控 CPU/内存占用

### 3. API 调试 (API Playground)
- **对话接口**: 类似 ChatGPT 的对话框，直接向 Agent 发送指令
- **工具测试**: 单独调用某个 Skill 工具进行测试

## 目录结构规划
```
langchain/
  web/              # 新增 Web 模块
    backend/        # FastAPI 后端
      main.py
      routers/
    frontend/       # React 前端
      src/
      public/
  main.py           # 集成启动逻辑
```

## 开发步骤

### 第一阶段：后端基础
1. 创建 FastAPI 应用
2. 实现 `.env` 读写接口
3. 实现 Agent 交互接口 (Run/Stop)

### 第二阶段：前端开发
1. 初始化 React 项目 (Vite)
2. 构建移动端适配的 UI 布局
3. 对接后端 API

### 第三阶段：集成与测试
1. 在 `main.py` 中集成 Web 服务启动
2. 局域网访问测试 (手机访问)

## 启动方式
```bash
# 启动 Web 控制台 (默认端口 8000，可通过 WEB_PORT 环境变量配置)
python web_server.py
```

## 配置项 (新增)
- `WEB_PORT`: Web 服务监听端口 (默认 5010)
- `WEB_HOST`: Web 服务监听地址 (默认 0.0.0.0 以支持局域网访问)
