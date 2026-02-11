# 心跳机制说明

本文档专门说明心跳机制的用途、如何注册任务、如何在配置页管理。

## 作用
- 提供统一的后台任务调度入口
- 让多个功能共享同一套调度机制
- 支持运行时调整间隔与暂停

## 核心入口
- 注册：`app.integrations.heartbeat.register_task`
- 查询：`/api/config/heartbeat/tasks`
- 更新：`/api/config/heartbeat/update`

## 快速上手

**1) 注册一个心跳任务**
```python
from app.integrations import heartbeat

def _my_tick():
    pass

def start_my_feature():
    heartbeat.register_task(
        "my_feature_heartbeat",
        _my_tick,
        interval=5.0
    )
```

**2) 在程序启动时调用**
```python
from app.integrations import my_feature

def main():
    my_feature.start_my_feature()
```

**3) 打开配置页管理**
- 进入 `/config.html`
- 找到 “心跳任务” 区域
- 可调整间隔或暂停/恢复

## 配置页行为说明
- 间隔留空：使用任务默认间隔
- 间隔填写：覆盖默认间隔
- 暂停：停止执行任务
- 恢复：重新开始调度
- 所有调整仅对当前进程有效，重启后恢复默认

