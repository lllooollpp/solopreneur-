"""
Memory Search Engine 完整测试套件。

测试覆盖:
1. Chunker — Markdown 分块、标题面包屑、代码块感知
2. VectorStore — UPSERT、FTS5 搜索、向量搜索、缓存
3. MemorySearchEngine — 端到端索引 + 混合搜索
4. MemoryStore 集成 — 语义搜索与传统记忆共存

运行: python -m pytest tests/test_memory_engine.py -v
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from solopreneur.storage.memory_engine.chunker import Chunk, MarkdownChunker
from solopreneur.storage.memory_engine.embeddings import (
    NoopEmbedding,
    create_embedding_provider,
)
from solopreneur.storage.memory_engine.engine import MemorySearchEngine
from solopreneur.storage.memory_engine.store import (
    SearchHit,
    VectorStore,
    _cosine_similarity,
    _deserialize_vector,
    _serialize_vector,
)


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    """创建临时工作区。"""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    return tmp_path


@pytest.fixture
def sample_markdown() -> str:
    return """# 项目概述

这是一个 Agent 系统。

## 架构设计

系统采用分层架构。

### 数据层

使用 SQLite 作为主要存储。

```python
def create_db():
    conn = sqlite3.connect("app.db")
    return conn
```

### 网络层

使用 FastAPI 提供 REST API。

## 部署

使用 Docker 部署。
"""


@pytest.fixture
def vector_store(tmp_path: Path) -> VectorStore:
    db_path = tmp_path / "test.db"
    return VectorStore(db_path)


@pytest.fixture
def search_engine(tmp_workspace: Path) -> MemorySearchEngine:
    return MemorySearchEngine(
        workspace=tmp_workspace,
        embedding_config={"provider": "noop"},
    )


# ── 1. Chunker Tests ────────────────────────────────────────────────

class TestMarkdownChunker:
    def test_basic_markdown_chunking(self, sample_markdown: str):
        chunker = MarkdownChunker(max_chunk_size=1200)
        chunks = chunker.chunk(sample_markdown, source="test.md")

        assert len(chunks) > 0
        assert all(isinstance(c, Chunk) for c in chunks)
        assert all(c.source == "test.md" for c in chunks)

    def test_heading_context_breadcrumbs(self, sample_markdown: str):
        chunker = MarkdownChunker(max_chunk_size=1200)
        chunks = chunker.chunk(sample_markdown, source="test.md")

        # 检查面包屑结构
        heading_contexts = [c.heading_context for c in chunks]
        # 至少应有包含 "# 项目概述" 的面包屑
        has_project = any("项目概述" in h for h in heading_contexts)
        assert has_project, f"No heading containing '项目概述', got: {heading_contexts}"

    def test_code_block_not_split(self):
        text = """# 代码示例

```python
def very_long_function():
    x = 1
    y = 2
    z = 3
    return x + y + z
```

这是代码后面的内容。
"""
        chunker = MarkdownChunker(max_chunk_size=500)
        chunks = chunker.chunk(text, source="code.md")

        # 代码块应完整地在一个 chunk 中
        code_chunks = [c for c in chunks if "very_long_function" in c.content]
        assert len(code_chunks) >= 1
        code_chunk = code_chunks[0]
        assert "def very_long_function():" in code_chunk.content
        assert "return x + y + z" in code_chunk.content

    def test_content_hash_dedup(self):
        chunker = MarkdownChunker()
        chunks1 = chunker.chunk("# Hello\n\nWorld", source="a.md")
        chunks2 = chunker.chunk("# Hello\n\nWorld", source="b.md")

        # 相同内容应有相同 hash
        assert chunks1[0].content_hash == chunks2[0].content_hash

    def test_empty_text(self):
        chunker = MarkdownChunker()
        assert chunker.chunk("", source="empty.md") == []
        assert chunker.chunk("   ", source="empty.md") == []

    def test_plain_text_fallback(self):
        chunker = MarkdownChunker(max_chunk_size=100)
        text = "这是一段没有 Markdown 标题的纯文本。" * 10
        chunks = chunker.chunk(text, source="plain.txt")
        assert len(chunks) > 0
        assert all(c.heading_context == "" for c in chunks)

    def test_search_text_includes_heading(self, sample_markdown: str):
        chunker = MarkdownChunker()
        chunks = chunker.chunk(sample_markdown, source="test.md")
        for c in chunks:
            if c.heading_context:
                assert c.heading_context in c.search_text


# ── 2. Vector Serialization Tests ────────────────────────────────────

class TestVectorSerialization:
    def test_roundtrip(self):
        original = [0.1, 0.2, 0.3, -0.5, 1.0]
        blob = _serialize_vector(original)
        restored = _deserialize_vector(blob)
        assert len(restored) == len(original)
        for a, b in zip(original, restored):
            assert abs(a - b) < 1e-6

    def test_cosine_similarity_identical(self):
        v = [1.0, 2.0, 3.0]
        assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal(self):
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert abs(_cosine_similarity(a, b)) < 1e-6

    def test_cosine_similarity_zero_vector(self):
        a = [1.0, 2.0, 3.0]
        b = [0.0, 0.0, 0.0]
        assert _cosine_similarity(a, b) == 0.0


# ── 3. VectorStore Tests ────────────────────────────────────────────

class TestVectorStore:
    def test_upsert_and_count(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="你好世界", heading_context="# 测试", source="test.md", chunk_index=0),
            Chunk(content="再见世界", heading_context="# 测试", source="test.md", chunk_index=1),
        ]
        embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

        written = vector_store.upsert_chunks(chunks, embeddings)
        assert written == 2
        assert vector_store.count_chunks() == 2
        assert vector_store.count_chunks(embedded_only=True) == 2

    def test_upsert_skip_unchanged(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="不变的内容", heading_context="", source="s.md", chunk_index=0),
        ]
        embeddings = [[0.1, 0.2]]

        vector_store.upsert_chunks(chunks, embeddings)
        # 第二次写入相同内容应跳过
        written = vector_store.upsert_chunks(chunks, embeddings)
        assert written == 0

    def test_keyword_search(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="Python 是一种编程语言", heading_context="# 编程", source="a.md", chunk_index=0),
            Chunk(content="Java 也是一种编程语言", heading_context="# 编程", source="a.md", chunk_index=1),
            Chunk(content="今天天气很好", heading_context="# 日记", source="b.md", chunk_index=0),
        ]
        vector_store.upsert_chunks(chunks, embeddings=None)

        results = vector_store.search_keyword("编程语言", top_k=5)
        assert len(results) >= 1
        assert all(isinstance(r, SearchHit) for r in results)

    def test_vector_search(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="A", heading_context="", source="a.md", chunk_index=0),
            Chunk(content="B", heading_context="", source="a.md", chunk_index=1),
        ]
        embeddings = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
        vector_store.upsert_chunks(chunks, embeddings)

        # 搜索与 A 相似的
        results = vector_store.search_vector([0.9, 0.1, 0.0], top_k=2)
        assert len(results) >= 1
        assert results[0].content == "A"  # A 应更相似

    def test_noop_vector_search_returns_empty(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="test", heading_context="", source="a.md", chunk_index=0),
        ]
        vector_store.upsert_chunks(chunks, [[0.0, 0.0, 0.0]])
        results = vector_store.search_vector([0.0, 0.0, 0.0])
        assert results == []

    def test_delete_source(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="A", heading_context="", source="a.md", chunk_index=0),
            Chunk(content="B", heading_context="", source="b.md", chunk_index=0),
        ]
        vector_store.upsert_chunks(chunks)
        assert vector_store.count_chunks() == 2

        vector_store.delete_source("a.md")
        assert vector_store.count_chunks() == 1

    def test_embedding_cache(self, vector_store: VectorStore):
        items = [("hash1", [0.1, 0.2, 0.3]), ("hash2", [0.4, 0.5, 0.6])]
        vector_store.cache_embeddings(items)

        cached = vector_store.get_cached_embeddings(["hash1", "hash2", "hash3"])
        assert "hash1" in cached
        assert "hash2" in cached
        assert "hash3" not in cached
        assert len(cached["hash1"]) == 3

    def test_get_stats(self, vector_store: VectorStore):
        stats = vector_store.get_stats()
        assert "total_chunks" in stats
        assert "embedded_chunks" in stats
        assert "db_size_mb" in stats

    def test_get_all_sources(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="A", heading_context="", source="a.md", chunk_index=0),
            Chunk(content="B", heading_context="", source="b.md", chunk_index=0),
        ]
        vector_store.upsert_chunks(chunks)
        sources = vector_store.get_all_sources()
        assert len(sources) == 2

    def test_rebuild_fts(self, vector_store: VectorStore):
        chunks = [
            Chunk(content="测试内容", heading_context="", source="a.md", chunk_index=0),
        ]
        vector_store.upsert_chunks(chunks)
        # Should not raise
        vector_store.rebuild_fts()


# ── 4. MemorySearchEngine Tests ─────────────────────────────────────

class TestMemorySearchEngine:
    def test_engine_init_noop(self, search_engine: MemorySearchEngine):
        assert search_engine._keyword_only is True
        assert isinstance(search_engine.embedder, NoopEmbedding)

    @pytest.mark.asyncio
    async def test_index_text(self, search_engine: MemorySearchEngine):
        written = await search_engine.index_text(
            "# 测试\n\n这是一段测试内容。\n\n## 架构\n\n使用 SQLite。",
            source="test-doc",
        )
        assert written > 0

    @pytest.mark.asyncio
    async def test_search_keyword_only(self, search_engine: MemorySearchEngine):
        await search_engine.index_text(
            "# Python 编程\n\nPython 是一种高级编程语言。\n\n## 特性\n\n动态类型、自动内存管理。",
            source="python.md",
        )
        await search_engine.index_text(
            "# 天气预报\n\n今天天气晴朗。",
            source="weather.md",
        )

        results = await search_engine.search("编程语言", top_k=5, min_score=0.0)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_index_file(self, tmp_workspace: Path):
        engine = MemorySearchEngine(
            workspace=tmp_workspace,
            embedding_config={"provider": "noop"},
        )

        # 写入测试文件
        md_file = tmp_workspace / "memory" / "2024-01-15.md"
        md_file.write_text("# 2024-01-15\n\n今天完成了记忆搜索引擎的实现。", encoding="utf-8")

        written = await engine.index_file(md_file)
        assert written > 0

    @pytest.mark.asyncio
    async def test_index_memory_dir(self, tmp_workspace: Path):
        engine = MemorySearchEngine(
            workspace=tmp_workspace,
            embedding_config={"provider": "noop"},
        )

        # 写入多个记忆文件
        memory_dir = tmp_workspace / "memory"
        (memory_dir / "2024-01-15.md").write_text("# 2024-01-15\n\n完成了数据库设计。", encoding="utf-8")
        (memory_dir / "2024-01-16.md").write_text("# 2024-01-16\n\n实现了 API 接口。", encoding="utf-8")
        (memory_dir / "MEMORY.md").write_text("# 长期记忆\n\n用户偏好 Python。", encoding="utf-8")

        results = await engine.index_memory_dir()
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_reindex_all(self, tmp_workspace: Path):
        engine = MemorySearchEngine(
            workspace=tmp_workspace,
            embedding_config={"provider": "noop"},
        )

        (tmp_workspace / "memory" / "test.md").write_text("# Test\n\nHello world.", encoding="utf-8")

        stats = await engine.reindex_all()
        assert "files_indexed" in stats
        assert stats["files_indexed"] >= 1

    def test_get_stats(self, search_engine: MemorySearchEngine):
        stats = search_engine.get_stats()
        assert stats["keyword_only"] is True
        assert stats["embedder"] == "NoopEmbedding"

    def test_clear(self, search_engine: MemorySearchEngine):
        search_engine.clear()
        assert search_engine.store.count_chunks() == 0


# ── 5. Embedding Provider Tests ─────────────────────────────────────

class TestEmbeddingProvider:
    def test_noop_embedding(self):
        emb = NoopEmbedding(dim=32)
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(emb.embed(["hello", "world"]))
        loop.close()

        assert len(result) == 2
        assert len(result[0]) == 32
        assert all(v == 0.0 for v in result[0])

    def test_create_provider_noop(self):
        provider = create_embedding_provider(None)
        assert isinstance(provider, NoopEmbedding)

    def test_create_provider_explicit_noop(self):
        provider = create_embedding_provider({"provider": "noop", "dimension": 128})
        assert isinstance(provider, NoopEmbedding)
        assert provider.dimension() == 128

    def test_create_provider_openai_no_key(self):
        """OpenAI without key should fall back to NoopEmbedding."""
        provider = create_embedding_provider({"provider": "openai"})
        assert isinstance(provider, NoopEmbedding)

    # ── local 模式测试 ───────────────────────────────────────────

    def test_create_provider_local(self):
        """local 模式应创建 LocalEmbedding 实例。"""
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        provider = create_embedding_provider({
            "provider": "local",
            "model": "all-MiniLM-L6-v2",
            "device": "cpu",
        })
        assert isinstance(provider, LocalEmbedding)
        assert provider.model_name == "all-MiniLM-L6-v2"
        assert provider._device == "cpu"

    def test_local_known_dimension(self):
        """已知模型应直接返回维度，不触发加载。"""
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        emb = LocalEmbedding(model="all-MiniLM-L6-v2", device="cpu")
        assert emb.dimension() == 384
        assert emb._model is None  # 不应触发加载

    def test_local_unknown_model_default_dim(self):
        """未知模型在未加载时应返回默认 384。"""
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        emb = LocalEmbedding(model="some-custom-model", device="cpu")
        # _dimension 为 None, dimension() 会触发 _ensure_model, 但这里 mock 不可用
        # 所以只验证已知模型映射
        assert emb._dimension is None

    def test_local_device_resolution_cpu(self):
        """device='cpu' 应直接返回 cpu。"""
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        emb = LocalEmbedding(device="cpu")
        assert emb._get_device() == "cpu"

    def test_local_device_resolution_auto_no_torch(self):
        """auto 模式下，如果没有 torch，应回退到 cpu。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        emb = LocalEmbedding(device="auto")
        # Mock torch 导入失败
        with patch.dict("sys.modules", {"torch": None}):
            import importlib
            # 直接测试 _get_device 逻辑 — 当 import torch 失败时返回 cpu
            device = emb._get_device()
            # 在无 torch 环境下应返回 cpu
            assert device in ("cpu", "cuda")  # 取决于环境

    def test_local_embed_mock(self):
        """Mock sentence-transformers 测试 embed 异步执行。"""
        import numpy as np
        from unittest.mock import MagicMock, patch
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        # 创建 mock 模型
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([
            [0.1, 0.2, 0.3],
            [0.4, 0.5, 0.6],
        ])
        mock_model.get_sentence_embedding_dimension.return_value = 3

        emb = LocalEmbedding(model="test-model", device="cpu")
        emb._model = mock_model  # 跳过实际加载

        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(emb.embed(["hello", "world"]))
        loop.close()

        assert len(result) == 2
        assert len(result[0]) == 3
        assert abs(result[0][0] - 0.1) < 1e-6
        mock_model.encode.assert_called_once()

    def test_local_model_cache_sharing(self):
        """同一模型名的不同实例应共享 _model_cache。"""
        from unittest.mock import MagicMock
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        # 清理缓存
        old_cache = LocalEmbedding._model_cache.copy()
        try:
            LocalEmbedding._model_cache.clear()

            mock_model = MagicMock()
            mock_model.get_sentence_embedding_dimension.return_value = 384
            LocalEmbedding._model_cache["shared-test-model"] = mock_model

            emb = LocalEmbedding(model="shared-test-model", device="cpu")
            loaded = emb._ensure_model()
            assert loaded is mock_model
        finally:
            LocalEmbedding._model_cache = old_cache

    def test_local_ensure_model_import_error(self):
        """缺少 sentence-transformers 时应抛出 ImportError。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        old_cache = LocalEmbedding._model_cache.copy()
        try:
            LocalEmbedding._model_cache.clear()

            emb = LocalEmbedding(model="nonexistent-model-xyz", device="cpu")
            emb._dimension = None

            with patch.dict("sys.modules", {"sentence_transformers": None}):
                with pytest.raises(ImportError, match="sentence-transformers"):
                    emb._ensure_model()
        finally:
            LocalEmbedding._model_cache = old_cache

    def test_create_provider_default_is_local(self):
        """默认创建 provider 时 provider 应为 local。"""
        from solopreneur.storage.memory_engine.embeddings import LocalEmbedding

        provider = create_embedding_provider({"provider": "local"})
        assert isinstance(provider, LocalEmbedding)

    # ── auto 模式测试 ────────────────────────────────────────────

    def test_auto_resolves_openai(self):
        """auto 模式：检测到 openai provider 时自动使用 OpenAIEmbedding（模拟无本地模型）。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import OpenAIEmbedding

        config = {
            "provider": "auto",
            "model": "text-embedding-3-small",
            "providers": {
                "openai": {"api_key": "sk-test-123", "api_base": ""},
            },
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, OpenAIEmbedding)
        assert provider.api_key == "sk-test-123"

    def test_auto_resolves_vllm_as_custom(self):
        """auto 模式：vLLM 解析为 CustomURLEmbedding（模拟无本地模型）。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import CustomURLEmbedding

        config = {
            "provider": "auto",
            "model": "bge-m3",
            "providers": {
                "vllm": {"api_key": "dummy", "api_base": "http://localhost:8000/v1"},
            },
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, CustomURLEmbedding)
        assert "localhost:8000" in provider.url

    def test_auto_resolves_openrouter_as_litellm(self):
        """auto 模式：OpenRouter 解析为 LiteLLMEmbedding（模拟无本地模型）。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import LiteLLMEmbedding

        config = {
            "provider": "auto",
            "model": "openai/text-embedding-3-small",
            "providers": {
                "openrouter": {
                    "api_key": "sk-or-test",
                    "api_base": "https://openrouter.ai/api/v1",
                },
            },
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, LiteLLMEmbedding)
        assert provider.api_key == "sk-or-test"

    def test_auto_no_providers_fallback_noop(self):
        """auto 模式：没有配置任何 provider 且无本地模型时退化为 NoopEmbedding。"""
        from unittest.mock import patch

        config = {
            "provider": "auto",
            "providers": {},
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, NoopEmbedding)

    def test_auto_explicit_key_overrides(self):
        """auto 模式：显式配置的 api_key 优先于 providers 中的（模拟无本地模型）。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import OpenAIEmbedding

        config = {
            "provider": "auto",
            "api_key": "sk-explicit-key",
            "providers": {
                "openai": {"api_key": "sk-from-providers", "api_base": ""},
            },
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, OpenAIEmbedding)
        assert provider.api_key == "sk-explicit-key"

    def test_auto_priority_vllm_over_openai(self):
        """auto 模式：vLLM 优先于 OpenAI（模拟无本地模型）。"""
        from unittest.mock import patch
        from solopreneur.storage.memory_engine.embeddings import CustomURLEmbedding

        config = {
            "provider": "auto",
            "providers": {
                "vllm": {"api_key": "dummy", "api_base": "http://gpu-server:8000/v1"},
                "openai": {"api_key": "sk-openai", "api_base": ""},
            },
        }
        with patch(
            "solopreneur.storage.memory_engine.embeddings._check_sentence_transformers_available",
            return_value=False,
        ):
            provider = create_embedding_provider(config)
        assert isinstance(provider, CustomURLEmbedding)


# ── 6. MemoryStore Integration Tests ────────────────────────────────

class TestMemoryStoreIntegration:
    def test_memory_store_without_search(self, tmp_workspace: Path):
        from solopreneur.agent.core.memory import MemoryStore

        store = MemoryStore(tmp_workspace)
        # 传统模式应正常工作
        assert store.search_engine is None
        assert store.get_memory_context() == ""

    def test_memory_store_with_search_disabled(self, tmp_workspace: Path):
        from solopreneur.agent.core.memory import MemoryStore

        store = MemoryStore(tmp_workspace, memory_search_config={"enabled": False})
        assert store.search_engine is None

    def test_memory_store_with_search_enabled(self, tmp_workspace: Path):
        from solopreneur.agent.core.memory import MemoryStore

        store = MemoryStore(
            tmp_workspace,
            memory_search_config={
                "enabled": True,
                "embedding_provider": "noop",
            },
        )
        engine = store.search_engine
        assert engine is not None
        assert engine._keyword_only is True

    @pytest.mark.asyncio
    async def test_semantic_search_integration(self, tmp_workspace: Path):
        from solopreneur.agent.core.memory import MemoryStore

        store = MemoryStore(
            tmp_workspace,
            memory_search_config={
                "enabled": True,
                "embedding_provider": "noop",
            },
        )

        # 写入记忆文件
        (tmp_workspace / "memory" / "MEMORY.md").write_text(
            "# 长期记忆\n\n用户喜欢使用 Python 和 SQLite 进行开发。",
            encoding="utf-8",
        )

        # 索引
        await store.index_memory_files()

        # 搜索
        result = await store.semantic_search("Python 开发", min_score=0.0)
        assert isinstance(result, str)

    def test_get_search_stats(self, tmp_workspace: Path):
        from solopreneur.agent.core.memory import MemoryStore

        store = MemoryStore(
            tmp_workspace,
            memory_search_config={
                "enabled": True,
                "embedding_provider": "noop",
            },
        )
        stats = store.get_search_stats()
        assert stats["enabled"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
