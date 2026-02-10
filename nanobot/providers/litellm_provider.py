"""LiteLLM provider implementation for multi-provider support."""

import json
import os
from typing import Any

import litellm
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.providers.exceptions import (
    LLMAPIError,
    LLMAuthenticationError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMInvalidResponseError
)


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, and many other providers through
    a unified interface.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5"
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        
        # Detect OpenRouter by api_key prefix or explicit api_base
        self.is_openrouter = (
            (api_key and api_key.startswith("sk-or-")) or
            (api_base and "openrouter" in api_base)
        )
        
        # Track if using custom endpoint (vLLM, etc.)
        self.is_vllm = bool(api_base) and not self.is_openrouter
        
        # Configure LiteLLM based on provider
        if api_key:
            if self.is_openrouter:
                # OpenRouter mode - set key
                os.environ["OPENROUTER_API_KEY"] = api_key
            elif self.is_vllm:
                # vLLM/custom endpoint - uses OpenAI-compatible API
                os.environ["OPENAI_API_KEY"] = api_key
            elif "anthropic" in default_model:
                os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
            elif "openai" in default_model or "gpt" in default_model:
                os.environ.setdefault("OPENAI_API_KEY", api_key)
            elif "gemini" in default_model.lower():
                os.environ.setdefault("GEMINI_API_KEY", api_key)
            elif "zhipu" in default_model or "glm" in default_model or "zai" in default_model:
                os.environ.setdefault("ZHIPUAI_API_KEY", api_key)
            elif "groq" in default_model:
                os.environ.setdefault("GROQ_API_KEY", api_key)
        
        if api_base:
            litellm.api_base = api_base
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
        # 自动丢弃模型不支持的参数（如gpt-5不支持temperature）
        litellm.drop_params = True
    
    def _prepare_model_name(self, model: str) -> str:
        """准备模型名称，添加必要的 provider 前缀。"""
        if self.is_openrouter and not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        if ("glm" in model.lower() or "zhipu" in model.lower()) and not (
            model.startswith("zhipu/") or
            model.startswith("zai/") or
            model.startswith("openrouter/")
        ):
            model = f"zai/{model}"
        if self.is_vllm:
            model = f"hosted_vllm/{model}"
        if "gemini" in model.lower() and not model.startswith("gemini/"):
            model = f"gemini/{model}"
        return model

    def _build_kwargs(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        temperature: float,
        stream: bool = False,
    ) -> dict[str, Any]:
        """构建 acompletion 调用参数。"""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if stream:
            kwargs["stream"] = True
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    def _handle_error(self, e: Exception, model: str):
        """统一错误处理。"""
        error_msg = str(e).lower()
        if "authentication" in error_msg or "unauthorized" in error_msg or "invalid api key" in error_msg:
            raise LLMAuthenticationError(
                f"认证失败: {str(e)}",
                provider=self.__class__.__name__,
                model=model,
            )
        elif "rate limit" in error_msg or "quota" in error_msg:
            raise LLMRateLimitError(
                f"速率限制: {str(e)}",
                provider=self.__class__.__name__,
                model=model,
            )
        elif "timeout" in error_msg:
            raise LLMTimeoutError(
                f"请求超时: {str(e)}",
                provider=self.__class__.__name__,
                model=model,
            )
        else:
            raise LLMAPIError(
                f"API调用失败: {str(e)}",
                provider=self.__class__.__name__,
                model=model,
            )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.
        """
        model = self._prepare_model_name(model or self.default_model)
        kwargs = self._build_kwargs(model, messages, tools, max_tokens, temperature)
        
        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            self._handle_error(e, model)

    async def chat_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        on_chunk=None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        流式发送 chat completion 请求，支持 tool calls 和实时文本回调。

        Args:
            messages: 消息列表
            tools: 工具定义列表
            model: 模型标识符
            on_chunk: 异步回调 async def on_chunk(text: str)
            max_tokens: 最大令牌数
            temperature: 采样温度

        Returns:
            LLMResponse 包含完整内容和/或 tool calls
        """
        model = self._prepare_model_name(model or self.default_model)
        kwargs = self._build_kwargs(model, messages, tools, max_tokens, temperature, stream=True)

        content_parts: list[str] = []
        tool_calls_data: dict[int, dict] = {}
        finish_reason = "stop"
        usage: dict = {}

        try:
            response = await acompletion(**kwargs)
            async for chunk in response:
                # 处理没有 choices 的 chunk（可能只有 usage）
                if not chunk.choices:
                    if hasattr(chunk, "usage") and chunk.usage:
                        usage = {
                            "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0) or 0,
                            "completion_tokens": getattr(chunk.usage, "completion_tokens", 0) or 0,
                            "total_tokens": getattr(chunk.usage, "total_tokens", 0) or 0,
                        }
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if choice.finish_reason:
                    finish_reason = choice.finish_reason

                # 文本内容 - 实时回调
                if hasattr(delta, "content") and delta.content:
                    content_parts.append(delta.content)
                    if on_chunk:
                        await on_chunk(delta.content)

                # Tool calls 增量累积
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = getattr(tc_delta, "index", 0) or 0
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {"id": "", "name": "", "arguments": ""}
                        if getattr(tc_delta, "id", None):
                            tool_calls_data[idx]["id"] = tc_delta.id
                        fn = getattr(tc_delta, "function", None)
                        if fn:
                            if getattr(fn, "name", None):
                                tool_calls_data[idx]["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                tool_calls_data[idx]["arguments"] += fn.arguments

                # Usage
                if hasattr(chunk, "usage") and chunk.usage:
                    usage = {
                        "prompt_tokens": getattr(chunk.usage, "prompt_tokens", 0) or 0,
                        "completion_tokens": getattr(chunk.usage, "completion_tokens", 0) or 0,
                        "total_tokens": getattr(chunk.usage, "total_tokens", 0) or 0,
                    }
        except Exception as e:
            self._handle_error(e, model)

        # 构建 tool calls
        tool_calls = []
        for idx in sorted(tool_calls_data.keys()):
            tc = tool_calls_data[idx]
            args = tc["arguments"]
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args else {}
                except json.JSONDecodeError:
                    args = {"raw": args}
            tool_calls.append(ToolCallRequest(
                id=tc["id"], name=tc["name"], arguments=args,
            ))

        return LLMResponse(
            content="".join(content_parts) or None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = {}
        if hasattr(response, "usage") and response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
