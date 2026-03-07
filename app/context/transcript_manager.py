"""
上下文管理器 - 完整的会话历史管理

功能：
1. JSONL transcript 存储
2. 完整的工具调用追踪（tool_calls + tool 消息）
3. 会话恢复机制
4. 自动压缩长历史
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path


class TranscriptManager:
    """管理会话的完整历史记录"""
    
    def __init__(self, session_id: str, data_dir: str = None):
        self.session_id = session_id
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data", "transcripts")
        
        self.data_dir = data_dir
        self.transcript_path = os.path.join(data_dir, f"{session_id}.jsonl")
        
        os.makedirs(data_dir, exist_ok=True)
        
        self.messages: List[Dict[str, Any]] = []
        self._load()
    
    def _load(self):
        """从文件加载历史记录"""
        if not os.path.exists(self.transcript_path):
            return
        
        try:
            with open(self.transcript_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            self.messages.append(msg)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"加载 transcript 失败：{e}")
    
    def _save(self, message: Dict[str, Any]):
        """追加消息到文件"""
        try:
            with open(self.transcript_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(message, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"保存 transcript 失败：{e}")
    
    def add_message(
        self,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        tool_call_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        添加消息到历史记录
        
        Args:
            role: 角色 (user/assistant/tool/system)
            content: 消息内容
            tool_calls: 工具调用列表（仅 assistant 使用）
            tool_call_id: 工具调用 ID（仅 tool 使用）
            metadata: 额外元数据
        
        Returns:
            添加的消息对象
        """
        message = {
            "id": f"msg_{int(time.time() * 1000)}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "role": role,
            "content": content,
        }
        
        if tool_calls:
            message["tool_calls"] = tool_calls
        
        if tool_call_id:
            message["tool_call_id"] = tool_call_id
        
        if metadata:
            message["metadata"] = metadata
        
        self.messages.append(message)
        self._save(message)
        
        return message
    
    def add_user_message(self, content: str, metadata: Optional[Dict] = None) -> Dict:
        """添加用户消息"""
        return self.add_message("user", content, metadata=metadata)
    
    def add_assistant_message(
        self,
        content: str,
        tool_calls: Optional[List[Dict]] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """添加助手消息"""
        return self.add_message("assistant", content, tool_calls=tool_calls, metadata=metadata)
    
    def add_tool_result(
        self,
        content: str,
        tool_call_id: str,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """添加工具执行结果"""
        return self.add_message("tool", content, tool_call_id=tool_call_id, metadata=metadata)
    
    def get_messages(
        self,
        limit: Optional[int] = None,
        include_system: bool = True
    ) -> List[Dict[str, Any]]:
        """
        获取历史记录
        
        Args:
            limit: 限制返回数量
            include_system: 是否包含 system 消息
        
        Returns:
            消息列表
        """
        messages = self.messages[:]
        
        if not include_system:
            messages = [m for m in messages if m.get("role") != "system"]
        
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    def to_langchain_format(self, limit: Optional[int] = None) -> List:
        """
        转换为 LangChain 格式
        
        Returns:
            LangChain 兼容的消息列表
        """
        messages = self.get_messages(limit=limit)
        result = []
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "assistant" and msg.get("tool_calls"):
                result.append({
                    "role": "assistant",
                    "content": content,
                    "tool_calls": msg["tool_calls"]
                })
            elif role == "tool":
                result.append({
                    "role": "tool",
                    "content": content,
                    "tool_call_id": msg.get("tool_call_id", "")
                })
            else:
                result.append({
                    "role": role,
                    "content": content
                })
        
        return result
    
    def clear(self):
        """清空历史记录"""
        self.messages = []
        if os.path.exists(self.transcript_path):
            backup_path = f"{self.transcript_path}.{int(time.time())}.bak"
            os.rename(self.transcript_path, backup_path)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        roles = {}
        total_chars = 0
        
        for msg in self.messages:
            role = msg.get("role", "unknown")
            roles[role] = roles.get(role, 0) + 1
            total_chars += len(msg.get("content", ""))
        
        return {
            "total_messages": len(self.messages),
            "messages_by_role": roles,
            "total_chars": total_chars,
            "session_id": self.session_id
        }


class SessionManager:
    """管理多个会话"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(base_dir, "data", "transcripts")
        
        self.data_dir = data_dir
        self.sessions: Dict[str, TranscriptManager] = {}
        self.current_session_id: Optional[str] = None
    
    def get_or_create_session(self, session_id: str) -> TranscriptManager:
        """获取或创建会话"""
        if session_id not in self.sessions:
            self.sessions[session_id] = TranscriptManager(session_id, self.data_dir)
        
        self.current_session_id = session_id
        return self.sessions[session_id]
    
    def get_current_session(self) -> Optional[TranscriptManager]:
        """获取当前会话"""
        if self.current_session_id:
            return self.sessions.get(self.current_session_id)
        return None
    
    def list_sessions(self) -> List[str]:
        """列出所有会话"""
        if not os.path.exists(self.data_dir):
            return []
        
        sessions = []
        for f in os.listdir(self.data_dir):
            if f.endswith('.jsonl'):
                sessions.append(f[:-6])
        
        return sessions


_default_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器"""
    global _default_session_manager
    if _default_session_manager is None:
        _default_session_manager = SessionManager()
    return _default_session_manager


def get_current_transcript() -> Optional[TranscriptManager]:
    """获取当前会话的 transcript"""
    manager = get_session_manager()
    return manager.get_current_session()
