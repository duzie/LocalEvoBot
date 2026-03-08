"""
公告板技能 - UI 适配器

将公告板的状态和消息实时推送到前端协作卡片
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional


class BoardUIAdapter:
    """公告板 UI 适配器"""
    
    def __init__(self, broadcast_func=None):
        self.broadcast_func = broadcast_func
        self.collaboration_id = 0
        self.active_collaborations = {}
    
    def create_collaboration_card(
        self,
        title: str,
        goal: str = "",
        roles: List[str] = None,
        auto_expand: bool = True
    ) -> Dict[str, Any]:
        """创建协作卡片"""
        self.collaboration_id += 1
        collab_id = self.collaboration_id
        
        card_data = {
            "id": collab_id,
            "title": title,
            "icon": "🤖",
            "status": "running",
            "statusText": "⏳ 创建中...",
            "autoExpand": auto_expand,
            "stages": [
                {
                    "time": datetime.now().strftime("%H:%M"),
                    "name": "📋 创建公告板",
                    "icon": "✓",
                    "status": "success",
                    "agents": [
                        {"icon": "✓", "name": role} for role in (roles or [])
                    ]
                }
            ],
            "meta": f"目标：{goal}" if goal else ""
        }
        
        self.active_collaborations[collab_id] = card_data
        
        # 发送到前端
        self._broadcast_collaboration(card_data)
        
        return card_data
    
    def update_stage(
        self,
        collab_id: int,
        stage_name: str,
        status: str = "running",
        agents: List[Dict] = None,
        time_str: str = None
    ):
        """更新阶段状态"""
        if collab_id not in self.active_collaborations:
            return
        
        card = self.active_collaborations[collab_id]
        
        # 添加新阶段
        new_stage = {
            "time": time_str or datetime.now().strftime("%H:%M"),
            "name": stage_name,
            "icon": "⏳" if status == "running" else "✓",
            "status": status,
            "agents": agents or []
        }
        
        card["stages"].append(new_stage)
        card["statusText"] = self._generate_status_text(card)
        
        # 更新广播
        self._broadcast_collaboration(card)
    
    def complete_collaboration(
        self,
        collab_id: int,
        files_created: List[str] = None,
        duration: str = None
    ):
        """完成协作"""
        if collab_id not in self.active_collaborations:
            return
        
        card = self.active_collaborations[collab_id]
        card["status"] = "success"
        card["statusText"] = "✓ 完成"
        card["icon"] = "✅"
        
        # 生成元信息
        meta_parts = []
        if duration:
            meta_parts.append(f"耗时：{duration}")
        if files_created:
            meta_parts.append(f"生成文件：{', '.join(files_created)}")
        
        card["meta"] = " • ".join(meta_parts) if meta_parts else ""
        
        # 从活动列表移除
        del self.active_collaborations[collab_id]
        
        # 广播完成状态
        self._broadcast_collaboration(card)
    
    def fail_collaboration(
        self,
        collab_id: int,
        error_message: str
    ):
        """失败协作"""
        if collab_id not in self.active_collaborations:
            return
        
        card = self.active_collaborations[collab_id]
        card["status"] = "failed"
        card["statusText"] = "❌ 失败"
        card["icon"] = "❌"
        card["meta"] = f"错误：{error_message}"
        
        del self.active_collaborations[collab_id]
        self._broadcast_collaboration(card)
    
    def _generate_status_text(self, card: Dict) -> str:
        """生成状态文本"""
        total = len(card["stages"])
        completed = sum(1 for s in card["stages"] if s["status"] == "success")
        running = sum(1 for s in card["stages"] if s["status"] == "running")
        
        if running > 0:
            return f"⏳ 执行中 ({completed}/{total})"
        elif completed == total:
            return "✓ 完成"
        else:
            return f"◐ 进行中 ({completed}/{total})"
    
    def _broadcast_collaboration(self, card_data: Dict):
        """Broadcast collaboration card to frontend"""
        if not self.broadcast_func:
            print("DEBUG [adapter]: broadcast_func is None, skipping")
            return
        
        # 格式化为前端可识别的消息
        message = {
            "type": "collaboration_card",
            "data": card_data
        }
        
        try:
            self.broadcast_func(message)
        except Exception as e:
            print(f"Broadcast error: {e}")


# 全局实例
_board_adapter: Optional[BoardUIAdapter] = None


def get_board_adapter(broadcast_func=None) -> BoardUIAdapter:
    """获取公告板 UI 适配器"""
    global _board_adapter
    if _board_adapter is None:
        _board_adapter = BoardUIAdapter(broadcast_func)
    return _board_adapter


# 测试
if __name__ == "__main__":
    def mock_broadcast(msg):
        print(f"Broadcast: {msg}")
    
    adapter = get_board_adapter(mock_broadcast)
    
    # 测试创建协作
    card = adapter.create_collaboration_card(
        title="代码审查",
        goal="审查 main.py 的代码质量",
        roles=["审查者", "开发者"]
    )
    
    # 测试更新阶段
    time.sleep(1)
    adapter.update_stage(
        card["id"],
        "🔍 代码审查",
        "running",
        [{"icon": "⏳", "name": "审查者"}]
    )
    
    # 测试完成
    time.sleep(1)
    adapter.complete_collaboration(
        card["id"],
        files_created=["review_report.md"],
        duration="2 分钟"
    )
