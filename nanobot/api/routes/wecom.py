"""
企业微信回调端点
处理消息验证和消息接收
"""
from fastapi import APIRouter, Query, Body, HTTPException
from loguru import logger
from typing import Optional

from nanobot.channels.wecom import (
    WeComConfig,
    WeComCrypto,
    parse_wecom_message,
    build_text_reply
)

router = APIRouter()

# 全局配置（实际从配置文件加载）
_wecom_config: Optional[WeComConfig] = None
_wecom_crypto: Optional[WeComCrypto] = None


def _ensure_config():
    """确保配置已加载"""
    global _wecom_config, _wecom_crypto
    
    if _wecom_config is None:
        # 从配置文件加载
        try:
            from nanobot.config.loader import load_config
            config = load_config()
            
            if config.channels.wecom.enabled:
                _wecom_config = WeComConfig(
                    corp_id=config.channels.wecom.corp_id,
                    agent_id=config.channels.wecom.agent_id,
                    secret=config.channels.wecom.secret,
                    token=config.channels.wecom.token,
                    aes_key=config.channels.wecom.aes_key
                )
                _wecom_crypto = WeComCrypto(
                    token=_wecom_config.token,
                    encoding_aes_key=_wecom_config.aes_key,
                    corp_id=_wecom_config.corp_id
                )
                logger.info("企业微信配置加载成功")
        except Exception as e:
            logger.warning(f"加载企业微信配置失败: {e}")


def init_wecom(config: WeComConfig):
    """初始化企业微信配置"""
    global _wecom_config, _wecom_crypto
    _wecom_config = config
    _wecom_crypto = WeComCrypto(
        token=config.token,
        encoding_aes_key=config.aes_key,
        corp_id=config.corp_id
    )


@router.get("/wecom/callback")
async def wecom_verify(
    msg_signature: str = Query(
        ..., 
        description="消息签名",
        pattern=r"^[a-zA-Z0-9]+$",
        max_length=200
    ),
    timestamp: str = Query(
        ..., 
        description="时间戳",
        pattern=r"^\d+$",
        max_length=20
    ),
    nonce: str = Query(
        ..., 
        description="随机字符串",
        pattern=r"^[a-zA-Z0-9]+$",
        max_length=200
    ),
    echostr: str = Query(
        ..., 
        description="验证字符串",
        max_length=1000
    )
):
    """
    企业微信回调 URL 验证
    
    企业微信首次配置回调地址时会发送 GET 请求进行验证
    """
    logger.info(f"收到企业微信验证请求: timestamp={timestamp}, nonce={nonce}")
    
    _ensure_config()
    
    if not _wecom_crypto:
        logger.error("企业微信未配置")
        raise HTTPException(status_code=500, detail="WeChat Work not configured")
    
    try:
        # 验证签名
        if not _wecom_crypto.verify_signature(msg_signature, timestamp, nonce, echostr):
            logger.error("企业微信验证签名失败")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # 解密 echostr
        decrypted = _wecom_crypto.decrypt_message(echostr)
        logger.info("企业微信验证成功")
        
        return decrypted
        
    except Exception as e:
        logger.error(f"企业微信验证失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wecom/callback")
async def wecom_receive_message(
    msg_signature: str = Query(
        ..., 
        description="消息签名",
        pattern=r"^[a-zA-Z0-9]+$",
        max_length=200
    ),
    timestamp: str = Query(
        ..., 
        description="时间戳",
        pattern=r"^\d+$",
        max_length=20
    ),
    nonce: str = Query(
        ..., 
        description="随机字符串",
        pattern=r"^[a-zA-Z0-9]+$",
        max_length=200
    ),
    body: dict = Body(..., description="加密的 XML 消息")
):
    """
    接收企业微信消息
    
    企业微信会 POST 加密的 XML 消息到此端点
    """
    logger.info(f"收到企业微信消息: timestamp={timestamp}, nonce={nonce}")
    
    _ensure_config()
    
    if not _wecom_crypto or not _wecom_config:
        logger.error("企业微信未配置")
        raise HTTPException(status_code=500, detail="WeChat Work not configured")
    
    try:
        # 提取加密消息
        encrypt_msg = body.get('Encrypt', '')
        if not encrypt_msg:
            logger.error("消息体中未找到 Encrypt 字段")
            raise HTTPException(status_code=400, detail="Missing Encrypt field")
        
        # 验证签名
        if not _wecom_crypto.verify_signature(msg_signature, timestamp, nonce, encrypt_msg):
            logger.error("消息签名验证失败")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # 解密消息
        xml_content = _wecom_crypto.decrypt_message(encrypt_msg)
        logger.debug(f"解密后的 XML: {xml_content}")
        
        # 解析消息
        message = parse_wecom_message(xml_content)
        logger.info(f"解析消息成功: from={message.from_user}, type={message.msg_type}, content={message.content}")
        
        # 将消息发送到总线（如果启用）
        try:
            from nanobot.bus.queue import MessageBus
            from nanobot.bus.events import InboundMessage
            
            bus = MessageBus()
            inbound_msg = InboundMessage(
                channel='wecom',
                chat_id=message.from_user,
                user_id=message.from_user,
                content=message.content,
                timestamp=message.create_time
            )
            await bus.publish_inbound(inbound_msg)
            logger.info("消息已发送到总线")
        except Exception as bus_error:
            logger.warning(f"发送消息到总线失败: {bus_error}")
        
        # 构建回复（暂时返回确认消息）
        reply_xml = build_text_reply(
            to_user=message.from_user,
            from_user=message.to_user,
            content=f"收到您的消息: {message.content}"
        )
        
        # 加密回复
        encrypted_reply = _wecom_crypto.encrypt_message(reply_xml, nonce)
        reply_signature = _wecom_crypto.generate_signature(timestamp, nonce, encrypted_reply)
        
        # 返回加密回复
        return {
            "Encrypt": encrypted_reply,
            "MsgSignature": reply_signature,
            "TimeStamp": timestamp,
            "Nonce": nonce
        }
        
    except Exception as e:
        logger.error(f"处理企业微信消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
