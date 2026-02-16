"""管理并协调聊天通道�?""

import asyncio
from typing import Any

from loguru import logger

from solopreneur.bus.events import OutboundMessage
from solopreneur.bus.queue import MessageBus
from solopreneur.channels.base import BaseChannel
from solopreneur.config.schema import Config


class ChannelManager:
    """
    管理聊天通道并协调消息路由�?
    
    职责�?
    - 初始化启用的通道（Telegram、WhatsApp 等）
    - 启动/停止通道
    - 路由传出消息
    """
    
    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self._dispatch_task: asyncio.Task | None = None
        
        self._init_channels()
    
    def _init_channels(self) -> None:
        """根据配置初始化通道�?""

        # 企业微信通道
        if hasattr(self.config.channels, 'wecom') and self.config.channels.wecom.enabled:
            try:
                from solopreneur.channels.wecom import WeComChannel, WeComConfig

                wecom_config = WeComConfig(
                    corp_id=self.config.channels.wecom.corp_id,
                    agent_id=self.config.channels.wecom.agent_id,
                    secret=self.config.channels.wecom.secret,
                    token=self.config.channels.wecom.token,
                    aes_key=self.config.channels.wecom.aes_key
                )
                channel = WeComChannel(config=wecom_config, bus=self.bus)
                self.channels['wecom'] = channel
                logger.info("企业微信通道已启�?)
            except (ImportError, AttributeError) as e:
                logger.warning(f"企业微信通道不可�? {e}")

        # Telegram 通道
        if hasattr(self.config.channels, 'telegram') and self.config.channels.telegram.enabled:
            try:
                from solopreneur.channels.telegram import TelegramChannel

                channel = TelegramChannel(
                    config=self.config.channels.telegram,
                    bus=self.bus
                )
                self.channels['telegram'] = channel
                logger.info("Telegram 通道已启�?)
            except (ImportError, AttributeError) as e:
                logger.warning(f"Telegram 通道不可�? {e}")

        # WhatsApp 通道
        if hasattr(self.config.channels, 'whatsapp') and self.config.channels.whatsapp.enabled:
            try:
                from solopreneur.channels.whatsapp import WhatsAppChannel

                channel = WhatsAppChannel(
                    config=self.config.channels.whatsapp,
                    bus=self.bus
                )
                self.channels['whatsapp'] = channel
                logger.info("WhatsApp 通道已启�?)
            except (ImportError, AttributeError) as e:
                logger.warning(f"WhatsApp 通道不可�? {e}")
    
    async def start_all(self) -> None:
        """启动所有通道和传出调度器�?""
        if not self.channels:
            logger.warning("未启用任何通道")
            return
        
        # 启动传出调度�?
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())
        
        # 启动所有通道
        tasks = []
        for name, channel in self.channels.items():
            logger.info(f"正在启动 {name} 通道...")
            tasks.append(asyncio.create_task(channel.start()))
        
        # 等待所有通道完成（它们应该永远运行）
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def stop_all(self) -> None:
        """停止所有通道和调度器�?""
        logger.info("正在停止所有通道...")
        
        # 停止调度�?
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        
        # 停止所有通道
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"已停�?{name} 通道")
            except Exception as e:
                logger.error(f"停止 {name} 时出�? {e}")
    
    async def _dispatch_outbound(self) -> None:
        """将传出消息调度到相应的通道�?""
        logger.info("传出调度器已启动")
        
        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )
                
                channel = self.channels.get(msg.channel)
                if channel:
                    try:
                        await channel.send(msg)
                    except Exception as e:
                        logger.error(f"�?{msg.channel} 发送消息时出错: {e}")
                else:
                    logger.warning(f"未知通道: {msg.channel}")
                    
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
    
    def get_channel(self, name: str) -> BaseChannel | None:
        """通过名称获取通道�?""
        return self.channels.get(name)
    
    def get_status(self) -> dict[str, Any]:
        """获取所有通道的状态�?""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }
    
    @property
    def enabled_channels(self) -> list[str]:
        """获取启用的通道名称列表�?""
        return list(self.channels.keys())
