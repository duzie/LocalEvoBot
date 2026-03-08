# Channels - 消息输入输出接口
# 与 OpenClaw 架构一致

from .feishu.channel import FeishuChannel
from .dingtalk.channel import DingtalkChannel
from .wecom.channel import WeComChannel

__all__ = ['FeishuChannel', 'DingtalkChannel', 'WeComChannel']
