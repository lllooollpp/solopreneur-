"""
企业微信通道实现
"""
import json
import hashlib
import xml.etree.ElementTree as ET
from typing import Any, Dict, Optional
from loguru import logger

from nanobot.channels.base import BaseChannel
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus


class WeComConfig:
    """企业微信配置"""

    def __init__(
        self,
        corp_id: str,
        agent_id: str,
        secret: str,
        token: str = "",
        aes_key: str = ""
    ):
        self.corp_id = corp_id
        self.agent_id = agent_id
        self.secret = secret
        self.token = token
        self.aes_key = aes_key


class WeComChannel(BaseChannel):
    """
    企业微信通道

    通过 Webhook 接收消息，通过 API 发送消息
    """

    name = "wecom"

    def __init__(self, config: WeComConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config = config
        self._running = False

    async def start(self) -> None:
        """启动通道（企业微信通过 FastAPI 路由处理，这里无需启动）"""
        self._running = True
        logger.info("WeCom channel started (waiting for webhooks)")

    async def stop(self) -> None:
        """停止通道"""
        self._running = False
        logger.info("WeCom channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """发送消息到企业微信"""
        # 实际实现需要调用企业微信 API
        # 这里只是占位符
        logger.info(f"Sending WeCom message to {msg.chat_id}: {msg.content[:50]}...")
        # TODO: 实现企业微信 API 调用

    async def handle_webhook(
        self,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        echostr: Optional[str] = None,
        body: Optional[str] = None
    ) -> str:
        """
        处理企业微信 Webhook

        验证 URL 时：
        - 返回 echostr

        接收消息时：
        - 解析消息并发送到消息总线
        - 返回 "success"
        """
        # 验证签名
        if not self._verify_signature(msg_signature, timestamp, nonce, echostr or ""):
            logger.warning("Invalid WeCom webhook signature")
            return ""

        # URL 验证
        if echostr:
            logger.debug("WeCom URL verification")
            return echostr

        # 处理消息
        if body:
            try:
                xml_data = ET.fromstring(body)
                msg_type = xml_data.find("MsgType").text
                content = xml_data.find("Content").text if xml_data.find("Content") is not None else ""
                sender_id = xml_data.find("FromUserName").text
                chat_id = xml_data.find("ToUserName").text

                logger.info(f"Received WeCom message: {msg_type} from {sender_id}")

                await self._handle_message(
                    sender_id=sender_id,
                    chat_id=chat_id,
                    content=content
                )
            except Exception as e:
                logger.error(f"Error parsing WeCom message: {e}")

        return "success"

    def _verify_signature(
        self,
        signature: str,
        timestamp: str,
        nonce: str,
        echostr: str
    ) -> bool:
        """验证企业微信签名"""
        if not self.config.token:
            return False

        # 排序并加密
        tmp_arr = [self.config.token, timestamp, nonce, echostr]
        tmp_arr.sort()
        tmp_str = "".join(tmp_arr)

        sha1 = hashlib.sha1()
        sha1.update(tmp_str.encode("utf-8"))
        hashcode = sha1.hexdigest()

        return hashcode == signature
