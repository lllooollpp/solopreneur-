"""
GitHub Copilot LLM Provider
通过 OAuth 设备流获取访问令牌，使用 GitHub Copilot API
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional, AsyncIterator
import httpx
import json
from pathlib import Path
from loguru import logger

try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning(
        "cryptography not installed. Tokens will be stored in plaintext. Install: pip install cryptography"
    )

from nanobot.providers.base import (
    BaseProvider,
    ProviderConfig,
    LLMProvider,
    LLMResponse,
    ToolCallRequest,
)
from nanobot.providers.exceptions import LLMInvalidResponseError, LLMRateLimitError
from nanobot.providers.token_pool import TokenPool, TokenSlot, SlotState


def _get_or_create_encryption_key() -> bytes:
    """获取或创建加密密钥。"""
    key_file = Path.home() / ".nanobot" / ".token_key"

    if key_file.exists():
        return key_file.read_bytes()
    else:
        # 生成新密钥
        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        key_file.chmod(0o600)  # 仅所有者可读写
        logger.info(f"Generated new encryption key at {key_file}")
        return key


def _encrypt_token(token: str) -> str:
    """加密token。如果crypto不可用，返回原文。"""
    if not CRYPTO_AVAILABLE:
        return token

    key = _get_or_create_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(token.encode())
    return encrypted.decode()


def _decrypt_token(encrypted_token: str) -> str:
    """解密token。如果crypto不可用，返回原文。"""
    if not CRYPTO_AVAILABLE:
        return encrypted_token

    try:
        key = _get_or_create_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt token: {e}")
        return encrypted_token  # 返回原文作为回退


@dataclass
class CopilotSession:
    """Copilot 会话信息"""

    github_access_token: str  # GitHub OAuth Token
    copilot_token: str  # Copilot API Token
    expires_at: datetime  # Token 过期时间


@dataclass
class DeviceFlowResponse:
    """设备流启动响应"""

    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class GitHubCopilotProvider(LLMProvider):
    """GitHub Copilot Provider 实现 - 使用 VS Code 官方 Client ID"""

    # VS Code GitHub Copilot 官方配置
    # 使用 VS Code Copilot 扩展的 Client ID 来模拟官方客户端
    CLIENT_ID = "01ab8ac9400c4e429b23"  # VS Code Copilot 官方 Client ID
    DEVICE_AUTH_URL = "https://github.com/login/device/code"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    COPILOT_TOKEN_URL = "https://api.github.com/copilot_internal/v2/token"
    COPILOT_CHAT_URL = "https://api.githubcopilot.com/chat/completions"

    # VS Code 模拟配置
    VSCODE_VERSION = "1.96.0"
    COPILOT_VERSION = "1.254.0"

    # 池调度：429 重试次数上限
    MAX_POOL_RETRIES = 5

    def __init__(self, api_key: str | None = None, api_base: str | None = None):
        super().__init__(api_key=api_key or "", api_base=api_base)
        # 添加 VS Code User-Agent
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
            headers={
                "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
                "Accept": "application/json",
            },
        )

        # ── Token Pool（多账号负载均衡） ──
        self._pool = TokenPool()

        # 兼容旧单文件 token：自动迁移到 slot 1
        legacy_token_file = Path.home() / ".nanobot" / ".copilot_token.json"
        self._pool.migrate_from_legacy(legacy_token_file)

        # Token 持久化文件路径（保留用于兼容）
        self._token_file = legacy_token_file

    @property
    def pool(self) -> TokenPool:
        """暴露 TokenPool 以供外部使用（CLI / API）"""
        return self._pool

    @property
    def session(self) -> Optional[CopilotSession]:
        """兼容旧代码：从池中获取一个可用的 session 视图"""
        return self._pool.get_legacy_session()

    @session.setter
    def session(self, value: Optional[CopilotSession]):
        """兼容旧代码：设置 session 时写入 slot 1"""
        if value is not None:
            self._pool.add_slot(
                slot_id=1,
                github_access_token=value.github_access_token,
                copilot_token=value.copilot_token,
                expires_at=value.expires_at,
                label="主账号",
            )

    async def __aenter__(self):
        """异步上下文管理器入口。"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口，确保资源清理。"""
        await self.close()

    # litellm 格式 -> Copilot API 格式 的模型名映射
    MODEL_ALIASES: dict[str, str] = {
        "anthropic/claude-opus-4-5": "claude-opus-4.5",
        "anthropic/claude-opus-4.5": "claude-opus-4.5",
        "anthropic/claude-opus-4.6": "claude-opus-4.6",
        "anthropic/claude-sonnet-4": "claude-sonnet-4",
        "anthropic/claude-sonnet-4.5": "claude-sonnet-4.5",
        "anthropic/claude-haiku-4.5": "claude-haiku-4.5",
        "openai/gpt-4o": "gpt-4o",
        "openai/gpt-4o-mini": "gpt-4o-mini",
        "openai/gpt-5": "gpt-5",
        "openai/gpt-5-mini": "gpt-5-mini",
    }

    def _normalize_model_name(self, model: str) -> str:
        """将 litellm 格式的模型名转换为 Copilot API 兼容名称。

        Examples:
            'anthropic/claude-opus-4-5' -> 'claude-opus-4.5'
            'openai/gpt-4o' -> 'gpt-4o'
            'gpt-4o' -> 'gpt-4o' (不变)
        """
        # 直接查映射表
        if model in self.MODEL_ALIASES:
            return self.MODEL_ALIASES[model]
        # 去掉 provider/ 前缀
        if "/" in model:
            stripped = model.split("/", 1)[1]
            if stripped in self.MODEL_ALIASES:
                return self.MODEL_ALIASES[stripped]
            return stripped
        return model

    def get_default_model(self) -> str:
        """获取默认模型"""
        return "claude-sonnet-4"

    async def start_device_flow(self) -> DeviceFlowResponse:
        """
        启动 OAuth 设备流认证

        Returns:
            DeviceFlowResponse: 包含 device_code、user_code 和验证 URL
        """
        logger.info("Starting GitHub Copilot device flow authentication")
        logger.debug(f"Device Auth URL: {self.DEVICE_AUTH_URL}")
        logger.debug(f"Client ID: {self.CLIENT_ID} (VS Code Copilot)")
        logger.debug(
            f"Simulating VS Code {self.VSCODE_VERSION} with Copilot {self.COPILOT_VERSION}"
        )

        response = await self._http_client.post(
            self.DEVICE_AUTH_URL,
            headers={
                "Accept": "application/json",
                "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
                "Editor-Version": f"vscode/{self.VSCODE_VERSION}",
            },
            data={"client_id": self.CLIENT_ID, "scope": "read:user"},
        )

        logger.debug(f"Device flow response status: {response.status_code}")
        logger.debug(f"Device flow response headers: {dict(response.headers)}")

        response.raise_for_status()
        data = response.json()

        logger.info(f"Device flow started successfully")
        logger.debug(f"Device code: {data['device_code'][:10]}...")
        logger.debug(f"User code: {data['user_code']}")
        logger.debug(f"Verification URI: {data['verification_uri']}")
        logger.debug(f"Expires in: {data['expires_in']} seconds")
        logger.debug(f"Interval: {data['interval']} seconds")

        return DeviceFlowResponse(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_uri=data["verification_uri"],
            expires_in=data["expires_in"],
            interval=data["interval"],
        )

    async def poll_for_token(self, device_code: str, interval: int = 5) -> str:
        """
        轮询等待用户完成授权

        Args:
            device_code: 设备代码
            interval: 轮询间隔（秒）

        Returns:
            str: GitHub Access Token
        """
        import asyncio

        logger.info("Waiting for user authorization...")

        while True:
            await asyncio.sleep(interval)

            response = await self._http_client.post(
                self.TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
                    "Editor-Version": f"vscode/{self.VSCODE_VERSION}",
                },
                data={
                    "client_id": self.CLIENT_ID,
                    "device_code": device_code,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                },
            )

            data = response.json()
            logger.debug(f"Token poll response: {data}")

            if "access_token" in data:
                logger.info("GitHub authorization successful!")
                return data["access_token"]

            error = data.get("error")
            if error == "authorization_pending":
                logger.debug("Authorization pending, continuing to poll...")
                continue
            elif error == "slow_down":
                interval += 5
                logger.debug(f"Slow down requested, new interval: {interval}s")
                continue
            elif error in ["expired_token", "access_denied"]:
                logger.error(f"Authorization failed: {error}")
                raise Exception(f"Authorization failed: {error}")
            else:
                logger.warning(f"Unknown error: {error}")
                continue

    async def get_copilot_token(self, github_token: str) -> tuple[str, datetime]:
        """
        使用 GitHub Token 获取 Copilot Token

        Args:
            github_token: GitHub Access Token

        Returns:
            tuple: (copilot_token, expires_at)
        """
        logger.info("Fetching Copilot Token")
        logger.debug(f"Copilot Token URL: {self.COPILOT_TOKEN_URL}")
        logger.debug(f"GitHub Token (first 10 chars): {github_token[:10]}...")

        # 使用 VS Code Copilot 扩展的请求头
        request_headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/json",
            "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
            "Editor-Version": f"vscode/{self.VSCODE_VERSION}",
            "Editor-Plugin-Version": f"copilot/{self.COPILOT_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        logger.debug(f"Request headers: {request_headers}")

        try:
            response = await self._http_client.get(self.COPILOT_TOKEN_URL, headers=request_headers)

            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")

            # 记录响应内容（成功或失败都记录）
            try:
                response_body = response.json()
                logger.debug(f"Response body (JSON): {response_body}")
            except:
                logger.debug(f"Response body (text): {response.text}")

            response.raise_for_status()
            data = response.json()

            token = data["token"]
            expires_at = datetime.fromtimestamp(data["expires_at"])

            logger.info(f"Copilot Token fetched successfully")
            logger.debug(f"Copilot Token (first 10 chars): {token[:10]}...")
            logger.debug(f"Token expires at: {expires_at}")

            return token, expires_at
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error: {e.response.status_code}")
            logger.error(f"Response headers: {dict(e.response.headers)}")

            # 记录详细的响应信息以便调试
            try:
                error_detail = e.response.json()
                logger.error(f"Response body (JSON): {error_detail}")
            except:
                logger.error(f"Response body (text): {e.response.text}")

            if e.response.status_code == 403:
                # 解析错误详情
                try:
                    error_json = e.response.json()
                    error_msg = error_json.get("error_details", {}).get("message", "")
                    if "approved clients" in error_msg.lower():
                        logger.error("GitHub Copilot API restriction detected")
                        logger.error(
                            "The Copilot internal API only allows official approved clients (VS Code, JetBrains, GitHub CLI)"
                        )
                        logger.error("Third-party applications cannot directly access Copilot API")
                        raise Exception(
                            "GitHub Copilot API only allows official clients (VS Code, JetBrains IDE, GitHub CLI). "
                            "Third-party applications cannot access Copilot directly. "
                            "Please use OpenAI API or other LLM providers instead."
                        )
                except Exception as parse_error:
                    if "approved clients" in str(parse_error):
                        raise

                logger.error("Cannot access Copilot API - 403 Forbidden")
                raise Exception(
                    "Cannot access GitHub Copilot API (403 Forbidden). "
                    "This may be due to API restrictions or subscription issues."
                )
            else:
                raise

    async def authenticate(self, github_token: Optional[str] = None) -> CopilotSession:
        """
        完成认证流程

        Args:
            github_token: 可选的 GitHub Token（如果已有）

        Returns:
            CopilotSession: 会话信息
        """
        if not github_token:
            # 启动设备流
            device_flow = await self.start_device_flow()

            logger.info(f"请访问: {device_flow.verification_uri}")
            logger.info(f"并输入代码: {device_flow.user_code}")

            # 轮询等待授权
            github_token = await self.poll_for_token(device_flow.device_code, device_flow.interval)

        # 获取 Copilot Token
        copilot_token, expires_at = await self.get_copilot_token(github_token)

        self.session = CopilotSession(
            github_access_token=github_token, copilot_token=copilot_token, expires_at=expires_at
        )

        return self.session

    async def refresh_token_if_needed(self):
        """如果 Token 即将过期或已过期，自动刷新（兼容旧接口）"""
        # 使用池刷新逻辑，刷新所有过期/即将过期的 slot
        await self._refresh_expired_slots()

    async def _refresh_expired_slots(self):
        """刷新池中所有过期的 slot"""
        for slot in self._pool.all_slots:
            if slot.state == SlotState.DEAD:
                continue
            if slot.is_token_expired:
                logger.info(f"[TokenPool] Slot {slot.slot_id} Token 过期，正在刷新...")
                try:
                    copilot_token, expires_at = await self.get_copilot_token(
                        slot.github_access_token
                    )
                    self._pool.update_copilot_token(slot.slot_id, copilot_token, expires_at)
                except Exception as e:
                    logger.error(f"[TokenPool] Slot {slot.slot_id} Token 刷新失败: {e}")
                    self._pool.report_auth_error(slot.slot_id)

    async def refresh_slot_token(self, slot: TokenSlot):
        """刷新单个 slot 的 Copilot Token"""
        try:
            copilot_token, expires_at = await self.get_copilot_token(slot.github_access_token)
            self._pool.update_copilot_token(slot.slot_id, copilot_token, expires_at)
        except Exception as e:
            logger.error(f"[TokenPool] Slot {slot.slot_id} Token 刷新失败: {e}")
            self._pool.report_auth_error(slot.slot_id)
            raise

    async def get_available_models(self) -> list[str]:
        """
        获取可用的模型列表

        Returns:
            list[str]: 可用模型列表
        """
        await self.refresh_token_if_needed()

        if not self.session:
            raise Exception("未认证，请先调用 authenticate()")

        # 调用 GitHub Copilot API 获取可用模型
        try:
            models_url = "https://api.githubcopilot.com/models"

            headers = {
                "Authorization": f"Bearer {self.session.copilot_token}",
                "Content-Type": "application/json",
                "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
                "Editor-Version": f"vscode/{self.VSCODE_VERSION}",
                "Editor-Plugin-Version": f"copilot/{self.COPILOT_VERSION}",
                "Copilot-Integration-Id": "vscode-chat",  # 关键头部！
            }

            logger.debug(f"Fetching models from {models_url}")
            response = await self._http_client.get(models_url, headers=headers)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Models API response: {data}")

            # 解析模型列表 - API 返回格式: {"data": [{"id": "gpt-4o", ...}, ...]}
            if "data" in data and isinstance(data["data"], list):
                # 只保留支持 /chat/completions 的聊天模型
                models = []
                for m in data["data"]:
                    mid = m.get("id", "")
                    cap_type = m.get("capabilities", {}).get("type", "")
                    endpoints = m.get("supported_endpoints", [])
                    # 跳过 embedding 模型
                    if cap_type == "embeddings":
                        continue
                    # 如果有 supported_endpoints 字段，只保留支持 /chat/completions 的
                    if endpoints and "/chat/completions" not in endpoints:
                        continue
                    models.append(mid)
                logger.info(f"Available chat models from API: {models}")
                return models
            else:
                logger.warning(f"Unexpected API response format: {data}")
                # 如果 API 格式不同，返回默认列表
                return ["gpt-5-mini", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

        except Exception as e:
            logger.error(f"Failed to fetch models from API: {e}")
            # 如果获取失败，返回默认列表
            return ["gpt-5-mini", "gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]

    def _build_headers(self, copilot_token: str) -> dict:
        """构建 Copilot API 请求头"""
        return {
            "Authorization": f"Bearer {copilot_token}",
            "Content-Type": "application/json",
            "User-Agent": f"GithubCopilot/{self.COPILOT_VERSION}",
            "Editor-Version": f"vscode/{self.VSCODE_VERSION}",
            "Editor-Plugin-Version": f"copilot-chat/{self.COPILOT_VERSION}",
            "Openai-Organization": "github-copilot",
            "Copilot-Integration-Id": "vscode-chat",
        }

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> AsyncIterator[str] | LLMResponse:
        """
        调用 Copilot Chat API（带 Token 池负载均衡与 429 自动重试）

        Args:
            messages: 消息历史
            tools: 可选的工具列表
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大令牌数
            stream: 是否流式输出

        Returns:
            流式输出时返回 AsyncIterator[str]，否则返回 LLMResponse
        """
        # 刷新过期 Token
        await self._refresh_expired_slots()

        model = self._normalize_model_name(model or self.get_default_model())

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
            "n": 1,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        logger.debug(
            f"Messages (repr): {[{k: repr(v) if k == 'content' else v for k, v in msg.items()} for msg in messages]}"
        )

        # ── 池调度循环：自动切换 slot 重试 ──
        last_error = None
        for attempt in range(self.MAX_POOL_RETRIES):
            # 从池中获取一个可用 slot
            slot = await self._pool.acquire()

            # 如果 slot 的 copilot token 过期，先刷新
            if slot.is_token_expired:
                await self.refresh_slot_token(slot)

            headers = self._build_headers(slot.copilot_token)

            if stream:
                return self._stream_response(headers, payload)

            try:
                response = await self._http_client.post(
                    self.COPILOT_CHAT_URL, headers=headers, json=payload
                )

                logger.debug(f"Chat response status: {response.status_code} (Slot {slot.slot_id})")

                if response.status_code == 429:
                    # 触发熔断，切换到下一个 slot 重试
                    retry_after = None
                    try:
                        retry_after = int(response.headers.get("retry-after", 0))
                    except (ValueError, TypeError):
                        pass
                    self._pool.report_rate_limit(slot.slot_id, retry_after)
                    last_error = LLMRateLimitError(
                        f"Slot {slot.slot_id} 触发 429，正在切换...",
                        retry_after=retry_after,
                        provider="GitHubCopilotProvider",
                    )
                    logger.warning(
                        f"[Pool] Slot {slot.slot_id} → 429, 第{attempt + 1}次重试, "
                        f"剩余可用: {self._pool.active_count}/{self._pool.size}"
                    )
                    continue

                if response.status_code in (401, 403):
                    self._pool.report_auth_error(slot.slot_id)
                    last_error = Exception(f"Slot {slot.slot_id} 认证失败 ({response.status_code})")
                    continue

                if response.status_code != 200:
                    logger.error(f"Chat API error response: {response.text}")

                response.raise_for_status()
                self._pool.report_success(slot.slot_id)
                return self._parse_response(response.json())

            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Status Error: {e}")
                logger.error(f"Response status: {e.response.status_code}")
                try:
                    error_detail = e.response.json()
                    logger.error(f"API error detail (JSON): {error_detail}")
                except Exception:
                    logger.error(f"API error detail (TEXT): {e.response.text}")
                last_error = e
                # 非 429 错误不重试
                raise

        # 所有重试耗尽
        raise last_error or RuntimeError("[TokenPool] 所有重试均失败")

    def _parse_response(self, data: dict) -> LLMResponse:
        """解析 API 响应"""
        if "choices" not in data or not data["choices"]:
            raise LLMInvalidResponseError(
                "API响应缺少choices字段或为空", provider="GitHubCopilotProvider"
            )

        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")

        tool_calls = []
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                # 解析参数
                args = tc["function"].get("arguments", "{}")
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}

                tool_calls.append(
                    ToolCallRequest(id=tc["id"], name=tc["function"]["name"], arguments=args)
                )

        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=usage,
        )

    async def _stream_response(self, headers: dict, payload: dict) -> AsyncIterator[str]:
        """处理流式响应"""
        async with self._http_client.stream(
            "POST", self.COPILOT_CHAT_URL, headers=headers, json=payload
        ) as response:
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                try:
                    await response.aread()
                except Exception:
                    pass
                error_body = response.text
                logger.error(f"Stream response error: {e.response.status_code} {error_body}")
                raise Exception(
                    f"Copilot stream error {e.response.status_code}: {error_body}"
                ) from e

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break

                    import json

                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk and len(chunk["choices"]) > 0:
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta:
                                content = delta.get("content")
                                if isinstance(content, str) and content:
                                    yield content
                    except json.JSONDecodeError:
                        continue

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        on_chunk=None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """
        流式调用 Copilot Chat API（带 Token 池负载均衡与 429 自动重试）

        Args:
            messages: 消息历史
            tools: 可选的工具列表
            model: 模型名称
            on_chunk: 异步回调 async def on_chunk(text: str)，收到文本片段时调用
            temperature: 温度参数
            max_tokens: 最大令牌数

        Returns:
            LLMResponse 包含完整内容和/或 tool calls
        """
        await self._refresh_expired_slots()

        model = self._normalize_model_name(model or self.get_default_model())

        payload = {
            "messages": messages,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "n": 1,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # ── 池调度循环：429 自动切换 slot 重试 ──
        last_error = None
        for attempt in range(self.MAX_POOL_RETRIES):
            slot = await self._pool.acquire()

            if slot.is_token_expired:
                await self.refresh_slot_token(slot)

            headers = self._build_headers(slot.copilot_token)

            content_parts: list[str] = []
            tool_calls_data: dict[int, dict] = {}
            finish_reason = "stop"
            usage: dict = {}
            got_429 = False

            async with self._http_client.stream(
                "POST", self.COPILOT_CHAT_URL, headers=headers, json=payload
            ) as response:
                # 检查 429
                if response.status_code == 429:
                    retry_after = None
                    try:
                        retry_after = int(response.headers.get("retry-after", 0))
                    except (ValueError, TypeError):
                        pass
                    self._pool.report_rate_limit(slot.slot_id, retry_after)
                    last_error = LLMRateLimitError(
                        f"Slot {slot.slot_id} 触发 429 (stream)，正在切换...",
                        retry_after=retry_after,
                        provider="GitHubCopilotProvider",
                    )
                    logger.warning(
                        f"[Pool] Slot {slot.slot_id} → 429 (stream), 第{attempt + 1}次重试, "
                        f"剩余可用: {self._pool.active_count}/{self._pool.size}"
                    )
                    got_429 = True
                    # 需要消费掉 response body 才能关闭连接
                    try:
                        await response.aread()
                    except Exception:
                        pass

                if got_429:
                    continue

                # 检查其他错误
                if response.status_code in (401, 403):
                    self._pool.report_auth_error(slot.slot_id)
                    try:
                        await response.aread()
                    except Exception:
                        pass
                    last_error = Exception(f"Slot {slot.slot_id} 认证失败 ({response.status_code})")
                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    try:
                        await response.aread()
                    except Exception:
                        pass
                    error_body = response.text
                    logger.error(f"Stream error: {e.response.status_code} {error_body}")
                    raise Exception(
                        f"Copilot stream error {e.response.status_code}: {error_body}"
                    ) from e

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    if "usage" in chunk:
                        usage = chunk["usage"]

                    if "choices" not in chunk or not chunk["choices"]:
                        continue

                    choice = chunk["choices"][0]
                    if choice.get("finish_reason"):
                        finish_reason = choice["finish_reason"]

                    delta = choice.get("delta", {})

                    if "content" in delta and delta["content"]:
                        text = delta["content"]
                        content_parts.append(text)
                        if on_chunk:
                            await on_chunk(text)

                    if "tool_calls" in delta:
                        for tc_delta in delta["tool_calls"]:
                            idx = tc_delta.get("index", 0)
                            if idx not in tool_calls_data:
                                tool_calls_data[idx] = {"id": "", "name": "", "arguments": ""}
                            if "id" in tc_delta and tc_delta["id"]:
                                tool_calls_data[idx]["id"] = tc_delta["id"]
                            if "function" in tc_delta:
                                fn = tc_delta["function"]
                                if "name" in fn and fn["name"]:
                                    tool_calls_data[idx]["name"] = fn["name"]
                                if "arguments" in fn:
                                    tool_calls_data[idx]["arguments"] += fn["arguments"]

            # 如果是 429 重试，继续循环（got_429 已在上面 continue）
            if got_429:
                continue

            # 成功完成
            self._pool.report_success(slot.slot_id)

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
                tool_calls.append(ToolCallRequest(id=tc["id"], name=tc["name"], arguments=args))

            return LLMResponse(
                content="".join(content_parts) or None,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                usage=usage,
            )

        # 所有重试耗尽
        raise last_error or RuntimeError("[TokenPool] 所有 stream 重试均失败")

    def _save_session_to_file(self):
        """兼容旧接口：保存当前 session 到池的 slot 1"""
        sess = self.session
        if not sess:
            return
        # 写入 pool 即自动持久化
        self._pool.add_slot(
            slot_id=1,
            github_access_token=sess.github_access_token,
            copilot_token=sess.copilot_token,
            expires_at=sess.expires_at,
            label="主账号",
        )
        logger.info("Session saved via TokenPool (slot 1)")

    def _load_session_from_file(self):
        """兼容旧接口：池在 __init__ 中已自动加载，此处为空操作"""
        pass  # TokenPool.__init__ 已自动加载所有 slot

    def _clear_session_file(self):
        """兼容旧接口：清除 slot 1"""
        self._pool.remove_slot(1)

    async def close(self):
        """关闭 HTTP 客户端"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            logger.debug("GitHub Copilot HTTP client closed")
