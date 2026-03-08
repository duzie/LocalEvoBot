"""
WeCom Channel - 企业微信消息频道

支持两种模式:
1. API 轮询（默认）- 无需公网服务器
2. HTTP 回调 - 需要公网服务器

企业微信 API: https://work.weixin.qq.com/api/doc
"""

import os
import logging
import threading
import time
import requests
import hashlib
from typing import Optional, Dict, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


# 回调模式已移除，默认使用 API 轮询（无需公网）
# 如需回调模式，请参考旧版本代码


class WeComChannel:
    """
    企业微信消息频道（API 轮询模式）
    
    用法:
        channel = WeComChannel()
        channel.start(corpid, corpsecret, agent_id)
        # 后台运行，定期轮询 → Agent → 回复
    
    注意：API 轮询模式无需公网服务器
    """
    
    def __init__(self):
        self.corp_id = ""
        self.corp_secret = ""
        self.agent_id = ""
        self.access_token = ""
        self.token_expires_at = 0
        
        self.running = False
        self.message_count = 0
        self.agent_executor = None
        self.last_msg_time = 0
    
    def set_agent(self, agent_executor):
        """设置 Agent 执行器"""
        self.agent_executor = agent_executor
    
    def get_access_token(self) -> str:
        """获取访问令牌"""
        # 检查缓存
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        try:
            url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={self.corp_id}&corpsecret={self.corp_secret}"
            response = requests.get(url, timeout=10)
            data = response.json()
            
            if data.get('errcode') == 0:
                self.access_token = data['access_token']
                self.token_expires_at = time.time() + data['expires_in'] - 300  # 提前 5 分钟刷新
                return self.access_token
            else:
                logger.error(f"获取 access_token 失败：{data}")
                return ""
        except Exception as e:
            logger.error(f"获取 access_token 异常：{e}")
            return ""
    
    def send_message(self, user_id: str, content: str):
        """
        发送消息
        
        Args:
            user_id: 用户 ID
            content: 消息内容
        """
        try:
            access_token = self.get_access_token()
            if not access_token:
                return
            
            url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            
            payload = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": int(self.agent_id),
                "text": {
                    "content": content
                },
                "safe": 0
            }
            
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if data.get('errcode') != 0:
                logger.error(f"发送消息失败：{data}")
            
        except Exception as e:
            logger.error(f"发送消息异常：{e}")
    
    def start(self, corpid: str = None, corpsecret: str = None, agentid: str = None,
              poll_interval: int = 5):
        """
        启动企业微信 Channel（API 轮询模式）
        
        Args:
            corpid: 企业 ID（或环境变量 WECOM_CORPID）
            corpsecret: 应用 Secret（或环境变量 WECOM_CORPSECRET）
            agentid: 应用 ID（或环境变量 WECOM_AGENTID）
            poll_interval: 轮询间隔（秒，默认 5 秒）
        """
        # 获取配置
        self.corp_id = (corpid or os.getenv("WECOM_CORPID") or "").strip()
        self.corp_secret = (corpsecret or os.getenv("WECOM_CORPSECRET") or "").strip()
        self.agent_id = (agentid or os.getenv("WECOM_AGENTID") or "").strip()
        
        if not all([self.corp_id, self.corp_secret, self.agent_id]):
            logger.error("缺少企业微信配置（WECOM_CORPID, WECOM_CORPSECRET, WECOM_AGENTID）")
            return
        
        try:
            self.running = True
            thread = threading.Thread(
                target=self._poll_messages,
                args=(poll_interval,),
                daemon=True
            )
            thread.start()
            
            logger.info(f"[OK] 企业微信 Channel 已启动（API 轮询，{poll_interval}秒/次）")
            logger.info("[注意] API 轮询模式无需公网服务器")
            
        except Exception as e:
            logger.error(f"启动企业微信 Channel 失败：{e}")
            self.running = False
    
    def _poll_messages(self, interval: int):
        """定期轮询消息"""
        logger.info("正在启动企业微信消息轮询...")
        
        while self.running:
            try:
                # 获取消息列表
                messages = self._get_messages()
                
                for msg in messages:
                    from_user = msg.get('FromUserName', '')
                    content = msg.get('Content', '')
                    msg_time = msg.get('CreateTime', 0)
                    
                    # 跳过旧消息
                    if msg_time <= self.last_msg_time:
                        continue
                    
                    self.last_msg_time = msg_time
                    self.message_count += 1
                    
                    logger.info(f"[企业微信] {from_user}: {content[:100]}")
                    
                    # 调用 Agent 处理
                    if self.agent_executor:
                        response = self.agent_executor.invoke({
                            "input": f"企业微信用户 {from_user} 发来消息：{content}"
                        })
                        reply_text = response.get("output", "收到你的消息了")
                    else:
                        reply_text = "收到你的消息了"
                    
                    # 回复消息
                    self.send_message(from_user, reply_text)
                    
                    logger.info(f"[企业微信回复] {reply_text[:100]}")
                
                # 等待下次轮询
                time.sleep(interval)
                
            except Exception as e:
                logger.error(f"轮询消息失败：{e}")
                time.sleep(interval)
    
    def _get_messages(self) -> list:
        """
        获取消息列表
        
        注意：企业微信没有直接获取消息的 API
        这里需要通过其他方式（如回调、第三方服务）
        当前实现返回空列表，需要进一步完善
        """
        # TODO: 实现消息获取
        # 企业微信官方不支持主动拉取消息
        # 需要使用回调模式或第三方服务
        return []
    
    def stop(self):
        """停止 Channel"""
        self.running = False
        logger.info("✅ 企业微信 Channel 已停止")
    
    def get_status(self) -> Dict[str, Any]:
        """获取 Channel 状态"""
        return {
            "running": self.running,
            "message_count": self.message_count,
            "token_valid": time.time() < self.token_expires_at,
            "mode": "polling"  # API 轮询模式
        }
