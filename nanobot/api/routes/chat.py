"""
聊天 API 端点
处理用户与 Agent 的对话
"""
from loguru import logger
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from nanobot.api.routes.auth import get_copilot_provider
from nanobot.session.cache import get_session_cache

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求模型"""
    content: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="消息内容，长度在1-50000字符之间"
    )
    session_id: Optional[str] = Field(
        default="default",
        description="会话ID，用于保持对话上下文"
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
        description="单次响应最大token数，范围1-128000"
    )
    max_iterations: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="最大工具迭代次数（AgentLoop 模式下）"
    )
    max_session_tokens: Optional[int] = Field(
        default=None,
        ge=10000,
        le=10000000,
        description="会话累计最大token数（AgentLoop 模式下）"
    )
    use_tools: Optional[bool] = Field(
        default=False,
        description="是否启用工具调用（AgentLoop 模式）"
    )
    max_history: Optional[int] = Field(
        default=20,
        ge=1,
        le=100,
        description="保留的最大历史消息数"
    )
    clear_history: Optional[bool] = Field(
        default=False,
        description="是否清空会话历史后开始对话"
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
    session_id: str


# 默认系统提示词
DEFAULT_SYSTEM_PROMPT = "你是 NanoBot，一个友好、智能的 AI 助手。你可以帮助用户解答问题、编写代码、分析问题等。请用中文回复。"


@router.post("/chat", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    发送消息给 Agent

    Args:
        request: 包含消息内容的请求

    Returns:
        ChatResponse: Agent 的回复
    """
    logger.info(f"Received chat message: {request.content[:50]}... (session: {request.session_id})")

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
                         "3. 按提示完成 GitHub 授权",
                session_id=request.session_id
            )

        # 获取或创建会话
        session_cache = get_session_cache()
        session = session_cache.get_or_create(
            session_id=request.session_id,
            system_prompt=DEFAULT_SYSTEM_PROMPT
        )

        # 添加用户消息
        session.add_message("user", request.content)

        # 调用 Copilot Chat API
        logger.debug(f"Calling Copilot Chat API with model: {request.model}")
        logger.debug(f"Message history length: {len(session.messages)}")
        logger.debug(f"Current message: {request.content[:100]}...")

        try:
            result = await provider.chat(
                messages=session.to_messages(),
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                stream=False
            )
        except Exception as api_error:
            logger.error(f"Copilot API error: {api_error}")

            # 输出可读的消息内容（用于调试编码问题）
            for i, msg in enumerate(session.to_messages()):
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
        session.add_message("assistant", response_text)

        # 限制历史长度（保留最近 20 条消息）
        session.truncate(20)

        logger.info(f"Chat response generated successfully")
        return ChatResponse(response=response_text, session_id=request.session_id)

    except Exception as e:
        logger.error(f"Chat processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/chat/history")
async def clear_chat_history(session_id: Optional[str] = "default"):
    """清空对话历史"""
    session_cache = get_session_cache()

    if session_id == "all":
        session_cache.clear()
        logger.info("All chat histories cleared")
        return {"status": "ok", "message": "所有对话历史已清空"}
    else:
        deleted = session_cache.delete(session_id)
        if deleted:
            logger.info(f"Chat history cleared for session: {session_id}")
            return {"status": "ok", "message": f"会话 {session_id} 的对话历史已清空"}
        else:
            return {"status": "ok", "message": f"会话 {session_id} 不存在"}


@router.get("/chat/sessions")
async def list_sessions():
    """列出所有会话"""
    session_cache = get_session_cache()
    sessions = [
        {
            "session_id": s.session_id,
            "message_count": len(s.messages),
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in session_cache.list_sessions()
    ]
    return {"sessions": sessions, "total": len(sessions)}
