"""
企业微信回调端点
处理消息验证和消息接收，集成 AI 回复
"""
from fastapi import APIRouter, Query, Body, HTTPException, BackgroundTasks
from loguru import logger
from typing import Optional
import asyncio

from solopreneur.channels.wecom import (
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
    """确保配置已加载（使用组件管理器）"""
    global _wecom_config, _wecom_crypto

    if _wecom_config is None:
        # 从配置文件加载
        try:
            from solopreneur.core.dependencies import get_component_manager
            manager = get_component_manager()
            config = manager.get_config()

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


async def _process_message_async(message, chat_id: str, content: str) -> str:
    """
    异步处理消息并返回 AI 回复
    
    使用 AgentLoop 处理消息
    """
    try:
        from solopreneur.core.dependencies import get_component_manager
        from solopreneur.agent.core.loop import AgentLoop
        from solopreneur.bus.queue import MessageBus
        from pathlib import Path
        
        manager = get_component_manager()
        config = manager.get_config()
        
        # 获取 Provider
        provider = manager.get_llm_provider()
        
        # 获取工作空间
        workspace = Path(config.agents.defaults.workspace).expanduser()
        
        # 创建 AgentLoop
        agent = AgentLoop(
            bus=MessageBus(),
            provider=provider,
            workspace=workspace,
            model=config.agents.defaults.model,
            max_iterations=config.agents.defaults.max_tool_iterations,
        )
        
        # 处理消息（流式回调用于收集完整响应）
        response_parts = []
        
        async def on_chunk(text: str):
            response_parts.append(text)
        
        session_key = f"wecom:{chat_id}"
        
        result = await agent.process_message_stream(
            content=content,
            session_key=session_key,
            on_chunk=on_chunk,
        )
        
        return result
        
    except Exception as e:
        logger.error(f"处理消息失败: {e}")
        return f"抱歉，处理您的消息时出错: {str(e)}"


async def _send_wecom_message(user_id: str, content: str):
    """
    通过企业微信 API 主动发送消息
    
    Args:
        user_id: 接收者 UserID
        content: 消息内容
    """
    try:
        import httpx
        
        if not _wecom_config:
            logger.error("企业微信未配置，无法发送消息")
            return
        
        # 获取 access_token
        async with httpx.AsyncClient() as client:
            # 获取 token
            token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={_wecom_config.corp_id}&corpsecret={_wecom_config.secret}"
            token_resp = await client.get(token_url)
            token_data = token_resp.json()
            
            if token_data.get("errcode", 0) != 0:
                logger.error(f"获取 access_token 失败: {token_data}")
                return
            
            access_token = token_data["access_token"]
            
            # 发送消息
            send_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"
            send_data = {
                "touser": user_id,
                "msgtype": "text",
                "agentid": int(_wecom_config.agent_id),
                "text": {
                    "content": content
                },
                "safe": 0
            }
            
            send_resp = await client.post(send_url, json=send_data)
            send_result = send_resp.json()
            
            if send_result.get("errcode", 0) == 0:
                logger.info(f"消息发送成功: {user_id}")
            else:
                logger.error(f"消息发送失败: {send_result}")
                
    except Exception as e:
        logger.error(f"发送企业微信消息失败: {e}")


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
    background_tasks: BackgroundTasks,
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
    处理流程：
    1. 验证签名
    2. 解密消息
    3. 异步处理并返回 AI 回复
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
        
        # 只处理文本消息
        if message.msg_type != "text":
            # 非文本消息返回空响应
            return ""
        
        # 在后台处理消息并发送回复
        async def process_and_reply():
            try:
                # 获取 AI 回复
                ai_response = await _process_message_async(
                    message=message,
                    chat_id=message.from_user,
                    content=message.content
                )
                
                # 通过 API 发送回复（因为被动回复有 5 秒限制）
                await _send_wecom_message(message.from_user, ai_response)
                
            except Exception as e:
                logger.error(f"后台处理消息失败: {e}")
                # 发送错误提示
                await _send_wecom_message(message.from_user, "抱歉，处理您的消息时出现了问题。")
        
        # 添加后台任务
        background_tasks.add_task(process_and_reply)
        
        # 立即返回成功响应（告诉企业微信我们收到了）
        return "success"
        
    except Exception as e:
        logger.error(f"处理企业微信消息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wecom/send")
async def wecom_send_message(
    user_id: str = Query(..., description="接收者 UserID"),
    content: str = Body(..., embed=True, description="消息内容")
):
    """
    主动发送企业微信消息
    
    用于测试或主动推送消息
    """
    _ensure_config()
    
    if not _wecom_config:
        raise HTTPException(status_code=500, detail="WeChat Work not configured")
    
    await _send_wecom_message(user_id, content)
    
    return {"message": "发送成功", "user_id": user_id}
