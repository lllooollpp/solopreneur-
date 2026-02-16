"""
聊天 API 端点
处理用户�?Agent 的对�?
"""
from loguru import logger
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from solopreneur.session.cache import get_session_cache

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
        description="温度参数，范�?.0-2.0"
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
        description="是否启用工具调用（AgentLoop 模式�?
    )
    max_history: Optional[int] = Field(
        default=20,
        ge=1,
        le=100,
        description="保留的最大历史消息数"
    )
    clear_history: Optional[bool] = Field(
        default=False,
        description="是否清空会话历史后开始对�?
    )

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证消息内容"""
        # 去除首尾空白
        v = v.strip()
        if not v:
            raise ValueError("消息内容不能为空")

        # 检查是否包含过多重复字符（防止垃圾内容�?
        if len(set(v)) < 3 and len(v) > 10:
            raise ValueError("消息内容无效：包含过多重复字�?)

        return v


class ChatResponse(BaseModel):
    """聊天响应模型"""
    response: str
    session_id: str


# 默认系统提示�?
DEFAULT_SYSTEM_PROMPT = "你是 NanoBot，一个友好、智能的 AI 助手。你可以帮助用户解答问题、编写代码、分析问题等。请用中文回复�?


@router.post("/chat", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    发送消息给 Agent

    Args:
        request: 包含消息内容的请�?

    Returns:
        ChatResponse: Agent 的回�?
    """
    logger.info(f"Received chat message: {request.content[:50]}... (session: {request.session_id})")

    try:
        # 使用组件管理器获取配置的 Provider
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        provider = manager.get_llm_provider()

        # 检�?Provider 是否可用
        if provider is None:
            logger.warning("No LLM provider configured, returning config prompt")
            return ChatResponse(
                response="⚠️ 请先在「配置」页面配�?LLM Provider 后再使用聊天功能。\n\n"
                         "1. 点击左侧菜单「配置」\n"
                         "2. 在「LLM Providers」区域选择并配置一�?Provider\n"
                         "   - GitHub Copilot（账号池管理页面登录）\n"
                         "   - 本地 OpenAI 标准接口（vLLM, Ollama 等）\n"
                         "   - 火山引擎\n"
                         "   - 其他 Provider（OpenAI, Anthropic 等）\n"
                         "3. 点击「保存配置�?,
                session_id=request.session_id
            )

        # 获取或创建会�?
        session_cache = get_session_cache()
        session = session_cache.get_or_create(
            session_id=request.session_id,
            system_prompt=DEFAULT_SYSTEM_PROMPT
        )

        # 添加用户消息
        session.add_message("user", request.content)

        # 调用 LLM Provider
        logger.debug(f"Calling LLM Provider with model: {request.model}")
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
            logger.error(f"LLM API error: {api_error}")

            # 输出可读的消息内容（用于调试编码问题�?
            for i, msg in enumerate(session.to_messages()):
                logger.error(f"Message {i} ({msg['role']}): {repr(msg['content'][:100])}...")

            raise

        # 提取响应内容（统一处理不同 Provider 的返回格式）
        if hasattr(result, 'content'):
            # LiteLLM 和其他使�?LLMResponse �?Provider
            response_text = result.content or "抱歉，我无法生成回复�?
        elif isinstance(result, dict):
            # 旧的 Copilot 返回格式（兼容）
            choices = result.get("choices", [])
            if choices:
                response_text = choices[0].get("message", {}).get("content", "")
            else:
                response_text = "抱歉，我无法生成回复�?
        elif isinstance(result, str):
            # 直接返回字符�?
            response_text = result
        else:
            response_text = "抱歉，响应格式异常�?

        # 保存助手回复到历�?
        session.add_message("assistant", response_text)

        # 限制历史长度（保留最�?20 条消息）
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
            return {"status": "ok", message: f"会话 {session_id} 的对话历史已清空"}
        else:
            return {"status": "ok", message: f"会话 {session_id} 不存�?}


@router.get("/chat/sessions")
async def list_sessions():
    """列出所有会�?""
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
