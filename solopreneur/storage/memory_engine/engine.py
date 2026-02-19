"""
混合记忆搜索引擎 — 统一 API 层。

将向量搜索、关键词搜索、分块、嵌入全部编排为一个简洁的接口:

    engine = MemorySearchEngine(workspace=Path("/path/to/workspace"), config={...})
    await engine.index_file(path)          # 索引一个文件
    await engine.index_text(text, source)  # 索引一段文本
    results = await engine.search("关键词或语义查询", top_k=5)

混合搜索策略:
- 如果有嵌入 provider（非 Noop）：向量分数 × α + 关键词分数 × (1-α)
- 如果仅关键词模式（NoopEmbedding）：纯 FTS5 BM25
- 结果按融合分数降序排列后去重

增量索引:
- 基于 content_hash 跳过未变更的分块（写放大 → 0）
- 嵌入缓存：相同内容不重复调用 API
- 缺嵌补嵌：后台对 embedding IS NULL 的分块进行补嵌
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from solopreneur.storage.memory_engine.chunker import Chunk, MarkdownChunker
from solopreneur.storage.memory_engine.embeddings import (
    EmbeddingProvider,
    NoopEmbedding,
    create_embedding_provider,
)
from solopreneur.storage.memory_engine.store import SearchHit, VectorStore


# ── 搜索结果（融合后） ───────────────────────────────────────────────

@dataclass
class MemorySearchResult:
    """一条融合后的搜索结果。"""

    content: str
    """分块内容。"""

    heading_context: str
    """标题上下文链（面包屑）。"""

    source: str
    """来源标识符。"""

    score: float
    """融合评分 [0, 1]。"""

    vector_score: float = 0.0
    """向量相似度分数。"""

    keyword_score: float = 0.0
    """关键词 BM25 分数。"""

    chunk_id: int = 0
    """内部分块 ID。"""

    metadata: dict = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """用于注入上下文的显示文本。"""
        if self.heading_context:
            return f"[{self.heading_context}]\n{self.content}"
        return self.content

    def __repr__(self) -> str:
        preview = self.content[:50].replace("\n", "↵")
        return f"MemorySearchResult(score={self.score:.3f}, src={self.source!r}, preview={preview!r})"


# ── 混合搜索引擎 ─────────────────────────────────────────────────────

class MemorySearchEngine:
    """
    完全自定义的语义记忆引擎。

    用法:
        engine = MemorySearchEngine(
            workspace=Path("./my-project"),
            embedding_config={"provider": "litellm", "model": "text-embedding-3-small"},
        )

        # 索引
        await engine.index_file(Path("memory/2024-01-15.md"))
        await engine.index_text("重要的项目决策...", source="decision-log")

        # 搜索
        results = await engine.search("数据库架构设计", top_k=5)
        for r in results:
            print(r.score, r.display_text)

        # 全量重索引
        await engine.reindex_all()
    """

    def __init__(
        self,
        workspace: Path,
        embedding_config: dict[str, Any] | None = None,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
        max_chunk_size: int = 1200,
        min_chunk_size: int = 100,
        db_name: str = "memory_search.db",
    ):
        """
        Args:
            workspace: 工作区根目录。
            embedding_config: 嵌入提供商配置（传给 create_embedding_provider）。
            vector_weight: 向量搜索在混合评分中的权重 (α)。
            keyword_weight: 关键词搜索在混合评分中的权重 (1-α)。
            max_chunk_size: 单块最大字符数。
            min_chunk_size: 单块最小字符数。
            db_name: 数据库文件名（存放在 workspace/memory/ 下）。
        """
        self.workspace = workspace
        self.memory_dir = workspace / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # 核心组件
        self.embedder: EmbeddingProvider = create_embedding_provider(embedding_config)
        self.chunker = MarkdownChunker(
            max_chunk_size=max_chunk_size,
            min_chunk_size=min_chunk_size,
        )
        self.store = VectorStore(self.memory_dir / db_name)

        # 混合搜索权重
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

        # 是否为关键词模式（NoopEmbedding）
        self._keyword_only = isinstance(self.embedder, NoopEmbedding)
        # 连续 embedding 失败计数，超过阈值后自动降级为关键词模式
        self._embed_fail_count: int = 0
        self._EMBED_FAIL_THRESHOLD: int = 3

        logger.info(
            f"MemorySearchEngine initialized: "
            f"embedder={self.embedder.name}, "
            f"keyword_only={self._keyword_only}, "
            f"weights=({self.vector_weight:.1f}v/{self.keyword_weight:.1f}k), "
            f"db={self.store.db_path}"
        )

    # ── 索引操作 ──────────────────────────────────────────────────

    async def index_text(
        self,
        text: str,
        source: str,
        metadata: dict | None = None,
    ) -> int:
        """
        索引一段文本。

        流程: 分块 → 查缓存 → 嵌入缺失部分 → 写入存储

        Args:
            text: 要索引的文本。
            source: 来源标识符。
            metadata: 附加元数据。

        Returns:
            实际写入/更新的分块数。
        """
        if not text or not text.strip():
            return 0

        t0 = time.time()

        # 1. 分块
        chunks = self.chunker.chunk(text, source=source, metadata=metadata)
        if not chunks:
            return 0

        # 2. 获取嵌入（带缓存）
        embeddings = await self._embed_chunks_cached(chunks)

        # 3. 写入存储
        written = self.store.upsert_chunks(chunks, embeddings)

        elapsed = time.time() - t0
        logger.debug(
            f"Indexed {len(chunks)} chunks from {source!r} "
            f"({written} new/updated) in {elapsed:.2f}s"
        )
        return written

    async def index_file(
        self,
        file_path: Path,
        metadata: dict | None = None,
    ) -> int:
        """
        索引一个文件。

        Args:
            file_path: 文件路径。
            metadata: 附加元数据。

        Returns:
            实际写入/更新的分块数。
        """
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return 0

        text = self._read_file_safe(file_path)
        if not text:
            return 0

        # 使用相对于 workspace 的路径作为 source
        try:
            source = str(file_path.relative_to(self.workspace))
        except ValueError:
            source = str(file_path)

        file_meta = {
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            **(metadata or {}),
        }

        return await self.index_text(text, source=source, metadata=file_meta)

    async def index_memory_dir(self) -> dict[str, int]:
        """
        索引 workspace/memory/ 目录下的所有 Markdown 文件。

        包括:
        - 每日笔记 (YYYY-MM-DD.md)
        - 长期记忆 (MEMORY.md)
        - 其他 .md 文件

        Returns:
            {source: written_count} 字典。
        """
        results: dict[str, int] = {}

        if not self.memory_dir.exists():
            return results

        md_files = sorted(self.memory_dir.glob("*.md"))
        for f in md_files:
            written = await self.index_file(f)
            try:
                source = str(f.relative_to(self.workspace))
            except ValueError:
                source = str(f)
            results[source] = written

        total_written = sum(results.values())
        total_files = len(md_files)
        if total_files == 0:
            logger.warning(
                f"Indexed memory dir: 0 files found. "
                f"Make sure .md files exist in: {self.memory_dir}"
            )
        else:
            logger.info(
                f"Indexed memory dir: {total_files} files, "
                f"{total_written} chunks written/updated"
            )
        return results

    async def reindex_all(self) -> dict[str, Any]:
        """
        全量重索引。

        流程:
        1. 重新扫描 memory 目录下所有 .md 文件
        2. 对每个文件重新分块+嵌入+写入
        3. 删除数据库中已不存在的 source
        4. 重建 FTS5 索引

        Returns:
            重索引统计信息。
        """
        t0 = time.time()

        # 1. 索引所有文件
        index_results = await self.index_memory_dir()

        # 2. 清理不存在的 source
        existing_sources = {
            str(f.relative_to(self.workspace))
            for f in self.memory_dir.glob("*.md")
            if f.exists()
        }
        db_sources = self.store.get_all_sources()
        cleaned = 0
        for src_info in db_sources:
            if src_info["source"] not in existing_sources:
                self.store.delete_source(src_info["source"])
                cleaned += 1

        # 3. 补嵌缺失的向量
        backfilled = await self._backfill_embeddings()

        # 4. 重建 FTS5
        self.store.rebuild_fts()

        elapsed = time.time() - t0
        stats = {
            "files_indexed": len(index_results),
            "chunks_written": sum(index_results.values()),
            "sources_cleaned": cleaned,
            "embeddings_backfilled": backfilled,
            "elapsed_seconds": round(elapsed, 2),
            **self.store.get_stats(),
        }

        logger.info(
            f"Reindex completed: {stats['files_indexed']} files, "
            f"{stats['chunks_written']} chunks, "
            f"{stats['sources_cleaned']} cleaned, "
            f"{elapsed:.2f}s"
        )
        return stats

    # ── 搜索操作 ──────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        top_k: int = 5,
        source_filter: str | None = None,
        min_score: float = 0.1,
    ) -> list[MemorySearchResult]:
        """
        混合搜索：向量 + 关键词融合。

        Args:
            query: 搜索查询文本。
            top_k: 返回前 K 条结果。
            source_filter: 可选，仅搜索指定来源。
            min_score: 最低融合分数阈值。

        Returns:
            按融合分数降序排列的搜索结果。
        """
        if not query or not query.strip():
            return []

        t0 = time.time()

        if self._keyword_only:
            # 纯关键词模式
            results = await self._search_keyword_only(query, top_k, source_filter)
        else:
            # 混合模式
            results = await self._search_hybrid(query, top_k, source_filter)

        # 过滤低分结果
        results = [r for r in results if r.score >= min_score]

        elapsed = time.time() - t0
        if results:
            logger.debug(
                f"Search '{query[:30]}...' → {len(results)} results "
                f"(top={results[0].score:.3f}) in {elapsed:.3f}s"
            )

        return results

    async def _search_hybrid(
        self,
        query: str,
        top_k: int,
        source_filter: str | None,
    ) -> list[MemorySearchResult]:
        """向量 + 关键词混合搜索。"""
        # 并行执行向量搜索和关键词搜索
        try:
            query_embedding = await self._embed_single(query)
            self._embed_fail_count = 0
        except Exception as e:
            self._embed_fail_count += 1
            logger.warning(f"Query embedding failed ({type(e).__name__}: {e}), falling back to keyword search")
            if self._embed_fail_count >= self._EMBED_FAIL_THRESHOLD:
                self._keyword_only = True
                logger.warning(
                    f"Embedding failed {self._embed_fail_count} times in a row, "
                    f"auto-degrading to keyword-only mode."
                )
            return await self._search_keyword_only(query, top_k, source_filter)

        # 向量搜索（扩大召回范围以供融合）
        vector_k = min(top_k * 3, 50)
        keyword_k = min(top_k * 3, 50)

        vector_hits = self.store.search_vector(
            query_embedding, top_k=vector_k, source_filter=source_filter
        )
        keyword_hits = self.store.search_keyword(
            query, top_k=keyword_k, source_filter=source_filter
        )

        # 融合
        return self._fuse_results(vector_hits, keyword_hits, top_k)

    async def _search_keyword_only(
        self,
        query: str,
        top_k: int,
        source_filter: str | None,
    ) -> list[MemorySearchResult]:
        """纯关键词搜索（NoopEmbedding 模式）。"""
        hits = self.store.search_keyword(
            query, top_k=top_k, source_filter=source_filter
        )

        return [
            MemorySearchResult(
                content=hit.content,
                heading_context=hit.heading_context,
                source=hit.source,
                score=hit.keyword_score,
                keyword_score=hit.keyword_score,
                chunk_id=hit.chunk_id,
                metadata=hit.metadata,
            )
            for hit in hits
        ]

    def _fuse_results(
        self,
        vector_hits: list[SearchHit],
        keyword_hits: list[SearchHit],
        top_k: int,
    ) -> list[MemorySearchResult]:
        """
        加权融合向量搜索和关键词搜索的结果。

        策略: score = α × vector_score + (1-α) × keyword_score
        对同一 chunk_id 的结果进行合并。
        """
        # 按 chunk_id 聚合
        merged: dict[int, MemorySearchResult] = {}

        for hit in vector_hits:
            if hit.chunk_id not in merged:
                merged[hit.chunk_id] = MemorySearchResult(
                    content=hit.content,
                    heading_context=hit.heading_context,
                    source=hit.source,
                    score=0.0,
                    vector_score=hit.vector_score,
                    chunk_id=hit.chunk_id,
                    metadata=hit.metadata,
                )
            else:
                merged[hit.chunk_id].vector_score = max(
                    merged[hit.chunk_id].vector_score, hit.vector_score
                )

        for hit in keyword_hits:
            if hit.chunk_id not in merged:
                merged[hit.chunk_id] = MemorySearchResult(
                    content=hit.content,
                    heading_context=hit.heading_context,
                    source=hit.source,
                    score=0.0,
                    keyword_score=hit.keyword_score,
                    chunk_id=hit.chunk_id,
                    metadata=hit.metadata,
                )
            else:
                merged[hit.chunk_id].keyword_score = max(
                    merged[hit.chunk_id].keyword_score, hit.keyword_score
                )

        # 计算融合分数
        for result in merged.values():
            result.score = (
                self.vector_weight * result.vector_score
                + self.keyword_weight * result.keyword_score
            )

        # 排序取 top_k
        sorted_results = sorted(
            merged.values(), key=lambda r: r.score, reverse=True
        )
        return sorted_results[:top_k]

    # ── 嵌入辅助 ──────────────────────────────────────────────────

    async def _embed_single(self, text: str) -> list[float]:
        """嵌入单条文本。"""
        results = await self.embedder.embed([text])
        return results[0]

    async def _embed_chunks_cached(
        self,
        chunks: list[Chunk],
    ) -> list[list[float]] | None:
        """
        对分块进行嵌入，带缓存。

        流程:
        1. 提取所有 content_hash
        2. 批量查缓存
        3. 仅对缓存未命中的分块调用 embedding API
        4. 将新嵌入写入缓存
        """
        if self._keyword_only:
            return None

        hashes = [c.content_hash for c in chunks]
        cached = self.store.get_cached_embeddings(hashes)

        # 分离命中和未命中
        embeddings: list[list[float] | None] = [None] * len(chunks)
        to_embed_indices: list[int] = []
        to_embed_texts: list[str] = []

        for i, chunk in enumerate(chunks):
            if chunk.content_hash in cached:
                embeddings[i] = cached[chunk.content_hash]
            else:
                to_embed_indices.append(i)
                to_embed_texts.append(chunk.search_text)

        cache_hits = len(chunks) - len(to_embed_indices)
        if cache_hits > 0:
            logger.debug(f"Embedding cache: {cache_hits}/{len(chunks)} hits")

        # 嵌入缓存未命中的
        if to_embed_texts:
            try:
                new_embeddings = await self.embedder.embed(to_embed_texts)
                self._embed_fail_count = 0  # 成功则重置计数
            except Exception as e:
                self._embed_fail_count += 1
                logger.error(f"Embedding failed: {type(e).__name__}: {e}")
                if self._embed_fail_count >= self._EMBED_FAIL_THRESHOLD:
                    self._keyword_only = True
                    logger.warning(
                        f"Embedding failed {self._embed_fail_count} times in a row, "
                        f"auto-degrading to keyword-only mode. "
                        f"Fix the embedding service or set embedding_provider=noop to suppress this."
                    )
                # 降级为 None（不写入嵌入，后续可补嵌）
                return None

            # 填充结果
            cache_items: list[tuple[str, list[float]]] = []
            for idx, emb in zip(to_embed_indices, new_embeddings):
                embeddings[idx] = emb
                cache_items.append((chunks[idx].content_hash, emb))

            # 写入缓存
            self.store.cache_embeddings(cache_items)

        return embeddings  # type: ignore[return-value]

    async def _backfill_embeddings(self, batch_size: int = 100) -> int:
        """
        为缺失嵌入的分块补嵌。

        Returns:
            补嵌的分块数。
        """
        if self._keyword_only:
            return 0

        total_backfilled = 0

        while True:
            missing = self.store.get_chunks_missing_embedding(limit=batch_size)
            if not missing:
                break

            hashes = [m["content_hash"] for m in missing]

            # 先查缓存
            cached = self.store.get_cached_embeddings(hashes)
            to_embed_map: dict[int, int] = {}  # missing_idx → embed_batch_idx
            to_embed_texts: list[str] = []

            updates: list[tuple[int, list[float]]] = []

            for i, m in enumerate(missing):
                if m["content_hash"] in cached:
                    updates.append((m["id"], cached[m["content_hash"]]))
                else:
                    to_embed_map[i] = len(to_embed_texts)
                    to_embed_texts.append(m["content"])

            # 嵌入新的
            if to_embed_texts:
                try:
                    new_embeddings = await self.embedder.embed(to_embed_texts)
                except Exception as e:
                    logger.error(f"Backfill embedding failed: {e}")
                    break

                cache_items: list[tuple[str, list[float]]] = []
                for missing_idx, embed_idx in to_embed_map.items():
                    m = missing[missing_idx]
                    emb = new_embeddings[embed_idx]
                    updates.append((m["id"], emb))
                    cache_items.append((m["content_hash"], emb))

                self.store.cache_embeddings(cache_items)

            # 批量更新
            if updates:
                self.store.update_chunk_embeddings(updates)
                total_backfilled += len(updates)

            # 如果本批次少于 batch_size，说明处理完了
            if len(missing) < batch_size:
                break

        if total_backfilled > 0:
            logger.info(f"Backfilled embeddings for {total_backfilled} chunks")
        return total_backfilled

    # ── 管理操作 ──────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取引擎统计信息。"""
        stats = self.store.get_stats()
        stats.update({
            "embedder": self.embedder.name,
            "keyword_only": self._keyword_only,
            "vector_weight": self.vector_weight,
            "keyword_weight": self.keyword_weight,
        })
        return stats

    def get_sources(self) -> list[dict[str, Any]]:
        """获取所有已索引的来源。"""
        return self.store.get_all_sources()

    def clear(self) -> int:
        """清除所有索引数据。"""
        return self.store.delete_all()

    # ── 辅助 ──────────────────────────────────────────────────────

    @staticmethod
    def _read_file_safe(path: Path) -> str:
        """安全读取文件，支持多种编码。"""
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        return ""
