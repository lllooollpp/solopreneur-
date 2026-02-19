"""
Embedding 抽象层 — 可插拔的向量嵌入提供商。

支持五种后端:
1. LocalEmbedding     — 本地 sentence-transformers 模型，CPU 即可运行
2. OpenAIEmbedding    — 直接调用 OpenAI embeddings API
3. LiteLLMEmbedding   — 通过 LiteLLM 统一调用任何嵌入模型
4. CustomURLEmbedding — 自定义 OpenAI 兼容 URL
5. NoopEmbedding      — 零向量占位（纯关键词模式，不消耗 API）

设计要求:
- 批量嵌入（减少 API 往返）
- 维度自动探测
- 线程安全
- 本地模型首次懒加载，后续复用
"""

from __future__ import annotations

import hashlib
import struct
import time
from abc import ABC, abstractmethod
from threading import Lock
from typing import Any

from loguru import logger


class EmbeddingProvider(ABC):
    """嵌入提供商抽象基类。"""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        将文本列表转换为向量列表。

        Args:
            texts: 待嵌入的文本列表。

        Returns:
            对应的浮点数向量列表，每个向量维度相同。
        """
        ...

    @abstractmethod
    def dimension(self) -> int:
        """返回嵌入向量维度。"""
        ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


class LocalEmbedding(EmbeddingProvider):
    """
    本地 sentence-transformers 嵌入后端。

    使用 CPU 运行，无需任何 API Key 或网络请求（首次需下载模型）。
    默认模型: all-MiniLM-L6-v2 (384d, ~80MB, 英文+中文够用)
    中文推荐: shibing624/text2vec-base-chinese (768d, ~400MB)

    特性:
    - 懒加载：首次 embed() 时才加载模型
    - 线程安全：内部锁保护模型加载
    - 支持 GPU 自动检测：有 CUDA 自动用，没有走 CPU
    """

    # 类级别缓存：同一模型名跨实例共享
    _model_cache: dict[str, Any] = {}
    _cache_lock = Lock()

    # 常见本地模型维度映射
    _KNOWN_DIMS: dict[str, int] = {
        "all-MiniLM-L6-v2": 384,
        "all-MiniLM-L12-v2": 384,
        "all-mpnet-base-v2": 768,
        "paraphrase-multilingual-MiniLM-L12-v2": 384,
        "shibing624/text2vec-base-chinese": 768,
        "BAAI/bge-small-zh-v1.5": 512,
        "BAAI/bge-base-zh-v1.5": 768,
        "BAAI/bge-small-en-v1.5": 384,
    }

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
        device: str = "auto",
        batch_size: int = 64,
    ):
        """
        Args:
            model: sentence-transformers 模型名称或本地路径。
            device: "cpu" / "cuda" / "auto"（自动检测）。
            batch_size: 每次 encode 的批量大小。
        """
        self.model_name = model
        self._device = device
        self.batch_size = batch_size
        self._model: Any = None
        self._dimension: int | None = self._KNOWN_DIMS.get(model)
        self._load_lock = Lock()

    def _get_device(self) -> str:
        """解析实际设备。"""
        if self._device != "auto":
            return self._device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _ensure_model(self) -> Any:
        """懒加载模型（线程安全，类级别缓存）。"""
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model

            # 类级别缓存检查
            with LocalEmbedding._cache_lock:
                if self.model_name in LocalEmbedding._model_cache:
                    self._model = LocalEmbedding._model_cache[self.model_name]
                    logger.info(f"LocalEmbedding reusing cached model: {self.model_name}")
                    return self._model

            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers 未安装。请运行:\n"
                    "  pip install sentence-transformers\n"
                    "或改用其他 embedding provider (openai / litellm / custom)。"
                )

            device = self._get_device()
            t0 = time.time()
            logger.info(
                f"Loading local embedding model: {self.model_name} "
                f"(device={device}) ..."
            )
            model = SentenceTransformer(self.model_name, device=device)
            elapsed = time.time() - t0
            dim = model.get_sentence_embedding_dimension()
            logger.info(
                f"Local embedding model loaded in {elapsed:.1f}s — "
                f"dim={dim}, device={device}"
            )

            self._model = model
            self._dimension = dim

            # 写入类级别缓存
            with LocalEmbedding._cache_lock:
                LocalEmbedding._model_cache[self.model_name] = model

            return self._model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        model = self._ensure_model()

        # sentence-transformers encode 是同步的，放到线程池避免阻塞事件循环
        def _encode() -> list[list[float]]:
            embeddings = model.encode(
                texts,
                batch_size=self.batch_size,
                show_progress_bar=False,
                normalize_embeddings=True,  # L2 归一化，方便 cosine 直接用内积
            )
            return [vec.tolist() for vec in embeddings]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _encode)

    def dimension(self) -> int:
        if self._dimension is not None:
            return self._dimension
        # 触发加载以获取维度
        self._ensure_model()
        return self._dimension or 384


class OpenAIEmbedding(EmbeddingProvider):
    """
    OpenAI Embeddings API 后端。

    使用 text-embedding-3-small (1536d) 或 text-embedding-3-large (3072d)。
    支持 api_base 覆盖（兼容 Azure OpenAI / 第三方代理）。
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        api_base: str | None = None,
        batch_size: int = 64,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base or "https://api.openai.com/v1"
        self.batch_size = batch_size
        self._dimension: int | None = None
        self._lock = Lock()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        all_embeddings: list[list[float]] = []
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.api_base.rstrip('/')}/embeddings"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                payload = {"model": self.model, "input": batch}

                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                batch_embeds = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(batch_embeds)

                # 自动探测维度
                if self._dimension is None and batch_embeds:
                    with self._lock:
                        self._dimension = len(batch_embeds[0])
                    logger.info(
                        f"OpenAIEmbedding dimension auto-detected: {self._dimension} "
                        f"(model={self.model})"
                    )

        return all_embeddings

    def dimension(self) -> int:
        if self._dimension is not None:
            return self._dimension
        # 常见默认值
        defaults = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return defaults.get(self.model, 1536)


class LiteLLMEmbedding(EmbeddingProvider):
    """
    通过 LiteLLM 调用嵌入模型，自动适配多种 Provider。

    支持: OpenAI, Cohere, HuggingFace, Bedrock, Azure, Vertex AI 等。
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        api_base: str | None = None,
        batch_size: int = 64,
    ):
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.batch_size = batch_size
        self._dimension: int | None = None
        self._lock = Lock()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        from litellm import aembedding

        all_embeddings: list[list[float]] = []
        kwargs: dict[str, Any] = {"model": self.model}
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            response = await aembedding(input=batch, **kwargs)

            batch_embeds = [item["embedding"] for item in response.data]
            all_embeddings.extend(batch_embeds)

            if self._dimension is None and batch_embeds:
                with self._lock:
                    self._dimension = len(batch_embeds[0])
                logger.info(
                    f"LiteLLMEmbedding dimension auto-detected: {self._dimension} "
                    f"(model={self.model})"
                )

        return all_embeddings

    def dimension(self) -> int:
        if self._dimension is not None:
            return self._dimension
        defaults = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return defaults.get(self.model, 1536)


class CustomURLEmbedding(EmbeddingProvider):
    """
    自定义 OpenAI 兼容 URL 嵌入后端。

    适用于自建嵌入服务（如 infinity, TEI, vLLM embed 等）。
    """

    def __init__(
        self,
        url: str,
        model: str = "default",
        api_key: str = "",
        dim: int = 1024,
        batch_size: int = 64,
    ):
        self.url = url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self._dim = dim
        self.batch_size = batch_size

    async def embed(self, texts: list[str]) -> list[list[float]]:
        import httpx

        all_embeddings: list[list[float]] = []
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.url}/embeddings"

        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(0, len(texts), self.batch_size):
                batch = texts[i : i + self.batch_size]
                payload = {"model": self.model, "input": batch}

                resp = await client.post(endpoint, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                batch_embeds = [item["embedding"] for item in data["data"]]
                all_embeddings.extend(batch_embeds)

                if batch_embeds and len(batch_embeds[0]) != self._dim:
                    self._dim = len(batch_embeds[0])
                    logger.info(f"CustomURLEmbedding dimension updated: {self._dim}")

        return all_embeddings

    def dimension(self) -> int:
        return self._dim


class NoopEmbedding(EmbeddingProvider):
    """
    零向量嵌入 — 纯关键词模式。

    不消耗任何 API 调用，返回全零向量。
    当用户未配置嵌入 provider 时使用，记忆引擎退化为纯 FTS5 关键词搜索。
    """

    def __init__(self, dim: int = 64):
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]

    def dimension(self) -> int:
        return self._dim


# ── Provider 自动解析 ─────────────────────────────────────────────────


def _check_sentence_transformers_available() -> bool:
    """检查 sentence-transformers 是否可用。"""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _resolve_from_providers(
    config: dict[str, Any],
) -> tuple[str, str, str]:
    """
    从已有 LLM providers 配置中自动推断 embedding 的 provider / api_key / api_base。

    解析优先级:
        local(如已安装 sentence-transformers) → vllm → zhipu → openrouter → openai → groq → gemini

    Returns:
        (resolved_provider, api_key, api_base)
    """
    # 优先本地：如果 sentence-transformers 已安装，走 local
    if _check_sentence_transformers_available():
        return ("local", "", "")

    providers: dict[str, Any] = config.get("providers", {})
    if not providers:
        return ("noop", "", "")

    # 注意: vLLM 跑的是聊天模型，通常不提供 /embeddings 端点，故跳过自动推断
    # 如需用 vLLM 做 embedding，请显式设置 embedding_provider=custom + embedding_api_base

    # 智谱 — 走 custom（OpenAI 兼容接口）
    zhipu = providers.get("zhipu", {})
    if zhipu.get("api_key"):
        return ("custom", zhipu["api_key"], zhipu.get("api_base", "https://open.bigmodel.cn/api/paas/v4/"))

    # OpenRouter — 走 litellm（litellm 原生支持 openrouter）
    openrouter = providers.get("openrouter", {})
    if openrouter.get("api_key"):
        return ("litellm", openrouter["api_key"], openrouter.get("api_base", "https://openrouter.ai/api/v1"))

    # OpenAI — 走 openai 原生
    openai = providers.get("openai", {})
    if openai.get("api_key"):
        return ("openai", openai["api_key"], openai.get("api_base", ""))

    # Gemini — 走 litellm
    gemini = providers.get("gemini", {})
    if gemini.get("api_key"):
        return ("litellm", gemini["api_key"], gemini.get("api_base", ""))

    # Groq — 走 litellm
    groq = providers.get("groq", {})
    if groq.get("api_key"):
        return ("litellm", groq["api_key"], groq.get("api_base", ""))

    return ("noop", "", "")


# ── 工厂函数 ──────────────────────────────────────────────────────────


def create_embedding_provider(config: dict[str, Any] | None = None) -> EmbeddingProvider:
    """
    根据配置创建嵌入提供商。

    配置格式:
        {
            "provider": "local" | "auto" | "openai" | "litellm" | "custom" | "noop",
            "model": "all-MiniLM-L6-v2",
            "device": "auto",      # local 模式专用: cpu / cuda / auto
            "api_key": "sk-...",
            "api_base": "https://...",
            "dimension": 384,
            "batch_size": 64,
            # "auto" 模式需要:
            "providers": { ... }  # 原始 LLM providers 配置
        }

    provider 说明:
    - "local": 本地 CPU 运行 sentence-transformers 模型（推荐，零 API 开销）
    - "auto": 优先本地 → 远程 providers 自动推断
    - "openai": 直接使用 OpenAI embeddings API
    - "litellm": 通过 LiteLLM 调用（支持 OpenRouter 等）
    - "custom": OpenAI 兼容的自建服务（vLLM / TEI / infinity）
    - "noop": 不使用向量嵌入，纯关键词搜索

    如果配置为空或 provider 为 "noop"，返回 NoopEmbedding。
    """
    if not config:
        logger.info("No embedding config provided, using NoopEmbedding (keyword-only mode)")
        return NoopEmbedding()

    provider_type = config.get("provider", "local").lower()
    model = config.get("model", "all-MiniLM-L6-v2")
    device = config.get("device", "auto")
    api_key = config.get("api_key", "")
    api_base = config.get("api_base", "")
    dim = config.get("dimension", 384)
    batch_size = config.get("batch_size", 64)

    # ── auto 模式：从 providers 配置中推断 ──
    if provider_type == "auto":
        resolved_type, resolved_key, resolved_base = _resolve_from_providers(config)
        # 显式配置的 api_key / api_base 优先（允许用户覆盖）
        api_key = api_key or resolved_key
        api_base = api_base or resolved_base
        provider_type = resolved_type
        logger.info(
            f"Auto-resolved embedding provider: {provider_type} "
            f"(model={model}, has_key={bool(api_key)})"
        )

    if provider_type == "local":
        return LocalEmbedding(
            model=model,
            device=device,
            batch_size=batch_size,
        )

    elif provider_type == "openai":
        if not api_key:
            logger.warning("OpenAI embedding configured but no api_key, falling back to NoopEmbedding")
            return NoopEmbedding()
        return OpenAIEmbedding(
            api_key=api_key,
            model=model,
            api_base=api_base or None,
            batch_size=batch_size,
        )

    elif provider_type == "litellm":
        return LiteLLMEmbedding(
            model=model,
            api_key=api_key or None,
            api_base=api_base or None,
            batch_size=batch_size,
        )

    elif provider_type == "custom":
        if not api_base:
            logger.warning("Custom embedding configured but no api_base, falling back to NoopEmbedding")
            return NoopEmbedding()
        return CustomURLEmbedding(
            url=api_base,
            model=model,
            api_key=api_key,
            dim=dim,
            batch_size=batch_size,
        )

    else:
        return NoopEmbedding(dim=dim)
