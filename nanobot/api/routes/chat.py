"""
聊天 API 端点
处理用户与 Agent 的对话
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from loguru import logger
from typing import Optional

from nanobot.api.routes.auth import get_copilot_provider

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求模型"""
    content: str = Field(
        ..., 
        min_length=1, 
        max_length=50000,
        description="消息内容，长度在1-50000字符之间"
    )
    model: Optional[str] = Field(
        default="gpt-5-mini",
        pattern=r"^[a-zA-Z0-9\-_.]+$",
        max_length=100,
        description="模型名称，只允许字母数字-_."
    )
    temperature: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="温度参数，范围0.0-2.0"
    )
    max_tokens: Optional[int] = Field(
        default=4096,
        ge=1,
        le=128000,
        description="最大token数，范围1-128000"
    )
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证消息内容"""
        # 去除首尾空白
        v = v.strip()
        if not v:
            raise ValueError("消息内容不能为空")
        
        # 检查是否包含过多重复字符（防止垃圾内容）
        if len(set(v)) < 3 and len(v) > 10:
            raise ValueError("消息内容无效：包含过多重复字符")
        
        return v


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str


# 简单的对话历史（实际应用应使用会话管理）
_conversation_history: list[dict] = []


@router.post("/chat", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    发送消息给 Agent
    
    Args:
        request: 包含消息内容的请求
        
    Returns:
        ChatResponse: Agent 的回复
    """
    logger.info(f"Received chat message: {request.content[:50]}...")
    
    try:
        # 获取 Copilot Provider
        provider = get_copilot_provider()
        
        # 检查是否已认证
        if not provider.session:
            logger.warning("Copilot not authenticated, returning auth prompt")
            return ChatResponse(
                response="⚠️ 请先在「配置」页面完成 GitHub Copilot 认证后再使用聊天功能。\n\n"
                         "1. 点击左侧菜单「配置」\n"
                         "2. 在「GitHub Copilot 认证」区域点击「开始认证」\n"
                         "3. 按提示完成 GitHub 授权"
            )
        
        # 构建消息列表
        global _conversation_history
        
        # 添加系统提示（如果是新对话）
        if not _conversation_history:
            _conversation_history = [{
                "role": "system",
                "content": "你是 NanoBot，一个友好、智能的 AI 助手。你可以帮助用户解答问题、编写代码、分析问题等。请用中文回复。"
            }]
        
        # 添加用户消息
        _conversation_history.append({
            "role": "user",
            "content": request.content
        })
        
        # 调用 Copilot Chat API
        logger.debug(f"Calling Copilot Chat API with model: {request.model}")
        logger.debug(f"Message history length: {len(_conversation_history)}")
        logger.debug(f"Current message: {request.content[:100]}...")
        
        try:
            result = await provider.chat(
                messages=_conversation_history,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False
            )
        except Exception as api_error:
            logger.error(f"Copilot API error: {api_error}")
            
            # 输出可读的消息内容（用于调试编码问题）
            for i, msg in enumerate(_conversation_history):
                logger.error(f"Message {i} ({msg['role']}): {repr(msg['content'][:100])}...")
            
            raise
        
        # 提取响应内容
        if isinstance(result, dict):
            # 非流式响应
            choices = result.get("choices", [])
            if choices:
                response_text = choices[0].get("message", {}).get("content", "")
            else:
                response_text = "抱歉，我无法生成回复。"
        else:
            response_text = "抱歉，响应格式异常。"
        
        # 保存助手回复到历史
        _conversation_history.append({
            "role": "assistant",
            "content": response_text
        })
        
        # 限制历史长度（保留最近 20 条消息）
        if len(_conversation_history) > 21:  # 1 system + 20 messages
            _conversation_history = _conversation_history[:1] + _conversation_history[-20:]
        
        logger.info(f"Chat response generated successfully")
        return ChatResponse(response=response_text)
        
    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/history")
async def clear_chat_history():
    """清空对话历史"""
    global _conversation_history
    _conversation_history = []
    logger.info("Chat history cleared")
    return {"status": "ok", "message": "对话历史已清空"}
