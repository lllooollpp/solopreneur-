"""
Memory Search Engine — 完全自定义的语义记忆引擎。

零外部向量数据库依赖，全部基于 SQLite 实现：
- 向量存储: SQLite BLOB + 余弦相似度
- 关键词搜索: FTS5 虚拟表 + BM25
- 混合搜索: 加权向量 + 关键词融合
- 嵌入: Local(sentence-transformers) / OpenAI / LiteLLM / 自定义URL / noop
- 分块: Markdown 感知 + 标题上下文
- 缓存: 嵌入缓存 + LRU 重索引
- 安全重索引: 原子性重建 FTS5 和重新嵌入缺失向量
"""

from solopreneur.storage.memory_engine.engine import MemorySearchEngine, MemorySearchResult
from solopreneur.storage.memory_engine.chunker import MarkdownChunker, Chunk
from solopreneur.storage.memory_engine.embeddings import (
    EmbeddingProvider,
    OpenAIEmbedding,
    LiteLLMEmbedding,
    LocalEmbedding,
    NoopEmbedding,
    create_embedding_provider,
)
from solopreneur.storage.memory_engine.store import VectorStore, SearchHit

__all__ = [
    "MemorySearchEngine",
    "MemorySearchResult",
    "MarkdownChunker",
    "Chunk",
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "LiteLLMEmbedding",
    "LocalEmbedding",
    "NoopEmbedding",
    "create_embedding_provider",
    "VectorStore",
    "SearchHit",
]
