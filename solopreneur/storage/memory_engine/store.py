"""
SQLite 向量 + FTS5 存储层。

在同一个 SQLite 数据库中同时实现:
1. 向量存储 — BLOB 字段存放 float32 数组，纯 Python 余弦相似度
2. 全文检索 — FTS5 虚拟表 + BM25 排名
3. 嵌入缓存 — content_hash 去重，避免重复调用 embedding API
4. 安全重索引 — 原子性重建 FTS5 / 补嵌缺失向量

线程安全: 所有写操作持有 Lock（与现有 SQLiteStore 风格一致）。
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import struct
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

from loguru import logger

from solopreneur.storage.memory_engine.chunker import Chunk


# ── 搜索结果 ─────────────────────────────────────────────────────────

@dataclass
class SearchHit:
    """
    一条搜索结果。

    同时携带向量分数和 BM25 关键词分数，
    由上层 engine 进行加权融合。
    """

    chunk_id: int
    content: str
    heading_context: str
    source: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)
    vector_score: float = 0.0
    """余弦相似度得分 [0, 1]。"""
    keyword_score: float = 0.0
    """FTS5 BM25 得分（已归一化到 [0, 1]）。"""
    created_at: str = ""


# ── 向量序列化工具 ───────────────────────────────────────────────────

def _serialize_vector(vec: list[float]) -> bytes:
    """将浮点向量序列化为 BLOB (little-endian float32)。"""
    return struct.pack(f"<{len(vec)}f", *vec)


def _deserialize_vector(blob: bytes) -> list[float]:
    """将 BLOB 反序列化为浮点向量。"""
    n = len(blob) // 4  # float32 = 4 bytes
    return list(struct.unpack(f"<{n}f", blob))


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    纯 Python 余弦相似度。

    对于全零向量（NoopEmbedding），返回 0.0。
    """
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


# ── CJK 分词辅助 ────────────────────────────────────────────────────

_CJK_RE = re.compile(
    r"([\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff"
    r"\U00020000-\U0002a6df\U0002a700-\U0002b73f"
    r"\U0002b740-\U0002b81f\U0002b820-\U0002ceaf"
    r"\U0002ceb0-\U0002ebef\U00030000-\U0003134f])"
)


def _cjk_segment(text: str) -> str:
    """
    在 CJK 字符之间插入空格，使 FTS5 unicode61 能正确分词。

    unicode61 tokenizer 不会拆分连续的 CJK 字符
    （如 "编程语言" → 一个 token），
    插入空格后 → "编 程 语 言"（4 个 token），
    FTS5 才能对中文做子串级别的匹配。
    """
    return _CJK_RE.sub(r" \1 ", text)


# ── VectorStore ──────────────────────────────────────────────────────

class VectorStore:
    """
    基于 SQLite 的向量 + FTS5 混合存储。

    表结构:
    - memory_chunks: 主表，所有分块数据 + 嵌入 BLOB
    - memory_chunks_fts: FTS5 虚拟表（外部内容表），用于 BM25 关键词检索
    - memory_embed_cache: 嵌入缓存，content_hash → embedding BLOB

    用法:
        store = VectorStore(db_path)
        store.upsert_chunks(chunks, embeddings)
        hits = store.search_vector(query_embedding, top_k=10)
        hits = store.search_keyword(query_text, top_k=10)
    """

    def __init__(self, db_path: Path | str):
        """
        Args:
            db_path: SQLite 数据库文件路径。目录不存在会自动创建。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._init_db()

    # ── 初始化 ────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """创建表结构（幂等）。"""
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")

            conn.executescript(
                """
                -- 主表：分块数据 + 嵌入向量
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    heading_context TEXT NOT NULL DEFAULT '',
                    search_text TEXT NOT NULL DEFAULT '',
                    embedding BLOB,
                    content_hash TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                -- 复合唯一索引：同一来源 + 同一分块序号只保留一条
                CREATE UNIQUE INDEX IF NOT EXISTS idx_mc_source_chunk
                    ON memory_chunks(source, chunk_index);

                CREATE INDEX IF NOT EXISTS idx_mc_content_hash
                    ON memory_chunks(content_hash);

                CREATE INDEX IF NOT EXISTS idx_mc_source
                    ON memory_chunks(source);

                CREATE INDEX IF NOT EXISTS idx_mc_created
                    ON memory_chunks(created_at);

                -- 嵌入缓存：避免对相同内容重复调用 API
                CREATE TABLE IF NOT EXISTS memory_embed_cache (
                    content_hash TEXT PRIMARY KEY,
                    embedding BLOB NOT NULL,
                    dimension INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

            # FTS5 虚拟表（外部内容表模式，与 memory_chunks 同步）
            # 先检查 FTS5 表是否存在，不存在则创建
            fts_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_chunks_fts'"
            ).fetchone()

            if not fts_exists:
                conn.executescript(
                    """
                    CREATE VIRTUAL TABLE memory_chunks_fts
                    USING fts5(
                        search_text,
                        content='memory_chunks',
                        content_rowid='id',
                        tokenize='unicode61 remove_diacritics 2'
                    );

                    -- 触发器：主表增删改时同步 FTS5（使用 CJK 分词后的 search_text）
                    CREATE TRIGGER IF NOT EXISTS mc_fts_insert
                    AFTER INSERT ON memory_chunks
                    BEGIN
                        INSERT INTO memory_chunks_fts(rowid, search_text)
                        VALUES (new.id, new.search_text);
                    END;

                    CREATE TRIGGER IF NOT EXISTS mc_fts_delete
                    AFTER DELETE ON memory_chunks
                    BEGIN
                        INSERT INTO memory_chunks_fts(memory_chunks_fts, rowid, search_text)
                        VALUES ('delete', old.id, old.search_text);
                    END;

                    CREATE TRIGGER IF NOT EXISTS mc_fts_update
                    AFTER UPDATE ON memory_chunks
                    BEGIN
                        INSERT INTO memory_chunks_fts(memory_chunks_fts, rowid, search_text)
                        VALUES ('delete', old.id, old.search_text);
                        INSERT INTO memory_chunks_fts(rowid, search_text)
                        VALUES (new.id, new.search_text);
                    END;
                    """
                )

        logger.debug(f"VectorStore initialized: {self.db_path}")

    # ── 写入操作 ──────────────────────────────────────────────────

    def upsert_chunks(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]] | None = None,
    ) -> int:
        """
        批量写入/更新分块（含嵌入向量）。

        使用 (source, chunk_index) 作为唯一键进行 UPSERT。
        如果 content_hash 未变，跳过更新以减少写放大。

        Args:
            chunks: 分块列表。
            embeddings: 对应的嵌入向量列表，长度须与 chunks 一致。
                        如果为 None，则不写入嵌入（向量字段为 NULL）。

        Returns:
            实际写入/更新的行数。
        """
        if not chunks:
            return 0

        if embeddings and len(embeddings) != len(chunks):
            raise ValueError(
                f"embeddings length ({len(embeddings)}) != chunks length ({len(chunks)})"
            )

        now = datetime.now().isoformat()
        written = 0

        with self._lock, self._connect() as conn:
            for i, chunk in enumerate(chunks):
                emb_blob = _serialize_vector(embeddings[i]) if embeddings else None
                meta_json = json.dumps(chunk.metadata, ensure_ascii=False) if chunk.metadata else "{}"

                # 检查是否已存在且内容未变
                existing = conn.execute(
                    "SELECT id, content_hash FROM memory_chunks WHERE source = ? AND chunk_index = ?",
                    (chunk.source, chunk.chunk_index),
                ).fetchone()

                if existing and existing["content_hash"] == chunk.content_hash:
                    # 内容未变，如果缺嵌入且现在有嵌入则补上
                    if emb_blob:
                        conn.execute(
                            """
                            UPDATE memory_chunks SET embedding = ?, updated_at = ?
                            WHERE id = ? AND embedding IS NULL
                            """,
                            (emb_blob, now, existing["id"]),
                        )
                    continue

                # 生成 CJK 分词后的 search_text 供 FTS5 索引
                search_text = _cjk_segment(
                    f"{chunk.heading_context} {chunk.content}"
                )

                # UPSERT
                conn.execute(
                    """
                    INSERT INTO memory_chunks(
                        source, chunk_index, content, heading_context,
                        search_text, embedding, content_hash, metadata_json,
                        created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(source, chunk_index) DO UPDATE SET
                        content = excluded.content,
                        heading_context = excluded.heading_context,
                        search_text = excluded.search_text,
                        embedding = excluded.embedding,
                        content_hash = excluded.content_hash,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        chunk.source,
                        chunk.chunk_index,
                        chunk.content,
                        chunk.heading_context,
                        search_text,
                        emb_blob,
                        chunk.content_hash,
                        meta_json,
                        now,
                        now,
                    ),
                )
                written += 1

                # 缓存嵌入
                if emb_blob:
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO memory_embed_cache(
                            content_hash, embedding, dimension, created_at
                        )
                        VALUES (?, ?, ?, ?)
                        """,
                        (chunk.content_hash, emb_blob, len(embeddings[i]), now),
                    )

        if written > 0:
            logger.debug(f"VectorStore: upserted {written} chunks")
        return written

    def delete_source(self, source: str) -> int:
        """
        删除指定来源的所有分块。

        Args:
            source: 来源标识符（如文件路径）。

        Returns:
            删除的行数。
        """
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "DELETE FROM memory_chunks WHERE source = ?",
                (source,),
            )
            deleted = result.rowcount
            if deleted > 0:
                logger.debug(f"VectorStore: deleted {deleted} chunks from source={source!r}")
            return deleted

    def delete_all(self) -> int:
        """清除所有分块数据（保留表结构）。"""
        with self._lock, self._connect() as conn:
            result = conn.execute("DELETE FROM memory_chunks")
            conn.execute("DELETE FROM memory_embed_cache")
            deleted = result.rowcount
            logger.info(f"VectorStore: cleared all {deleted} chunks")
            return deleted

    # ── 向量搜索 ──────────────────────────────────────────────────

    def search_vector(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        source_filter: str | None = None,
    ) -> list[SearchHit]:
        """
        使用余弦相似度进行向量近邻搜索。

        全表扫描 + 内存排序，适合中小规模记忆库（< 100k chunks）。
        对于 NoopEmbedding（全零向量）会返回空列表。

        Args:
            query_embedding: 查询向量。
            top_k: 返回最相似的前 K 条。
            source_filter: 可选，仅搜索指定来源。

        Returns:
            按余弦相似度降序排列的 SearchHit 列表。
        """
        # 检查是否为零向量（NoopEmbedding）
        if all(v == 0.0 for v in query_embedding):
            return []

        with self._lock, self._connect() as conn:
            if source_filter:
                rows = conn.execute(
                    """
                    SELECT id, source, chunk_index, content, heading_context,
                           embedding, metadata_json, created_at
                    FROM memory_chunks
                    WHERE embedding IS NOT NULL AND source = ?
                    """,
                    (source_filter,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, source, chunk_index, content, heading_context,
                           embedding, metadata_json, created_at
                    FROM memory_chunks
                    WHERE embedding IS NOT NULL
                    """
                ).fetchall()

        # 计算相似度
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            emb = _deserialize_vector(row["embedding"])
            sim = _cosine_similarity(query_embedding, emb)
            if sim > 0.0:
                scored.append((sim, row))

        # 排序取 top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        return [
            SearchHit(
                chunk_id=row["id"],
                content=row["content"],
                heading_context=row["heading_context"],
                source=row["source"],
                chunk_index=row["chunk_index"],
                metadata=_safe_json_loads(row["metadata_json"]),
                vector_score=sim,
                created_at=row["created_at"],
            )
            for sim, row in top
        ]

    # ── 关键词搜索 (FTS5) ────────────────────────────────────────

    def search_keyword(
        self,
        query: str,
        top_k: int = 10,
        source_filter: str | None = None,
    ) -> list[SearchHit]:
        """
        使用 FTS5 + BM25 进行关键词全文检索。

        自动对查询做分词处理，支持中英文混合。

        Args:
            query: 搜索关键词（自然语言）。
            top_k: 返回前 K 条。
            source_filter: 可选，仅搜索指定来源。

        Returns:
            按 BM25 得分降序排列的 SearchHit 列表。
        """
        if not query or not query.strip():
            return []

        # 构建 FTS5 查询表达式
        fts_query = self._build_fts_query(query)
        if not fts_query:
            return []

        try:
            with self._lock, self._connect() as conn:
                if source_filter:
                    rows = conn.execute(
                        """
                        SELECT mc.id, mc.source, mc.chunk_index, mc.content,
                               mc.heading_context, mc.metadata_json, mc.created_at,
                               fts.rank AS bm25_rank
                        FROM memory_chunks_fts fts
                        JOIN memory_chunks mc ON mc.id = fts.rowid
                        WHERE memory_chunks_fts MATCH ?
                          AND mc.source = ?
                        ORDER BY fts.rank
                        LIMIT ?
                        """,
                        (fts_query, source_filter, top_k),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """
                        SELECT mc.id, mc.source, mc.chunk_index, mc.content,
                               mc.heading_context, mc.metadata_json, mc.created_at,
                               fts.rank AS bm25_rank
                        FROM memory_chunks_fts fts
                        JOIN memory_chunks mc ON mc.id = fts.rowid
                        WHERE memory_chunks_fts MATCH ?
                        ORDER BY fts.rank
                        LIMIT ?
                        """,
                        (fts_query, top_k),
                    ).fetchall()
        except sqlite3.OperationalError as e:
            logger.warning(f"FTS5 search failed: {e} (query={fts_query!r})")
            return []

        if not rows:
            return []

        # BM25 rank 是负数（越小越好），归一化到 [0, 1]
        raw_scores = [abs(row["bm25_rank"]) for row in rows]
        max_score = max(raw_scores) if raw_scores else 1.0
        if max_score == 0.0:
            max_score = 1.0

        return [
            SearchHit(
                chunk_id=row["id"],
                content=row["content"],
                heading_context=row["heading_context"],
                source=row["source"],
                chunk_index=row["chunk_index"],
                metadata=_safe_json_loads(row["metadata_json"]),
                keyword_score=abs(row["bm25_rank"]) / max_score,
                created_at=row["created_at"],
            )
            for row in rows
        ]

    @staticmethod
    def _build_fts_query(query: str) -> str:
        """
        将自然语言查询转换为 FTS5 MATCH 表达式。

        策略：
        1. 先做 CJK 字符级分词 — 与 upsert 时对 search_text 的处理一致
        2. 过滤掉特殊字符以防注入
        3. 用 OR 连接所有词（宽泛召回）
        4. 单 ASCII 字母忽略
        """
        # 1. CJK 字符级分词 — 与 upsert 时对 search_text 的处理一致
        segmented = _cjk_segment(query)

        # 2. 清理特殊字符
        cleaned = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', segmented)
        tokens = cleaned.split()

        # 3. 过滤过短的 token（单个 ASCII 字母）
        valid_tokens = []
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            # 中文单字也有意义，只过滤单个 ASCII 字母
            if len(t) == 1 and t.isascii() and t.isalpha():
                continue
            valid_tokens.append(f'"{t}"')

        if not valid_tokens:
            return ""

        return " OR ".join(valid_tokens)

    # ── 查询辅助 ──────────────────────────────────────────────────

    def get_chunk_by_id(self, chunk_id: int) -> SearchHit | None:
        """按 ID 获取单个分块。"""
        with self._lock, self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, source, chunk_index, content, heading_context,
                       metadata_json, created_at
                FROM memory_chunks
                WHERE id = ?
                """,
                (chunk_id,),
            ).fetchone()

        if not row:
            return None

        return SearchHit(
            chunk_id=row["id"],
            content=row["content"],
            heading_context=row["heading_context"],
            source=row["source"],
            chunk_index=row["chunk_index"],
            metadata=_safe_json_loads(row["metadata_json"]),
            created_at=row["created_at"],
        )

    def get_all_sources(self) -> list[dict[str, Any]]:
        """获取所有已索引的来源及其分块数。"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source,
                       COUNT(*) as chunk_count,
                       SUM(CASE WHEN embedding IS NOT NULL THEN 1 ELSE 0 END) as embedded_count,
                       MIN(created_at) as first_indexed,
                       MAX(updated_at) as last_updated
                FROM memory_chunks
                GROUP BY source
                ORDER BY last_updated DESC
                """
            ).fetchall()

        return [
            {
                "source": row["source"],
                "chunk_count": row["chunk_count"],
                "embedded_count": row["embedded_count"],
                "first_indexed": row["first_indexed"],
                "last_updated": row["last_updated"],
            }
            for row in rows
        ]

    def count_chunks(self, embedded_only: bool = False) -> int:
        """返回总分块数。"""
        with self._lock, self._connect() as conn:
            if embedded_only:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM memory_chunks WHERE embedding IS NOT NULL"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt FROM memory_chunks"
                ).fetchone()
            return row["cnt"]

    def get_chunks_missing_embedding(self, limit: int = 500) -> list[dict[str, Any]]:
        """获取缺少嵌入向量的分块（用于增量补嵌）。"""
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, source, chunk_index, content, heading_context,
                       content_hash, metadata_json
                FROM memory_chunks
                WHERE embedding IS NULL
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "id": row["id"],
                "source": row["source"],
                "chunk_index": row["chunk_index"],
                "content": row["content"],
                "heading_context": row["heading_context"],
                "content_hash": row["content_hash"],
                "metadata": _safe_json_loads(row["metadata_json"]),
            }
            for row in rows
        ]

    # ── 嵌入缓存 ─────────────────────────────────────────────────

    def get_cached_embeddings(
        self,
        content_hashes: list[str],
    ) -> dict[str, list[float]]:
        """
        批量查询嵌入缓存。

        Args:
            content_hashes: 内容哈希列表。

        Returns:
            {content_hash: embedding} 字典（仅包含命中的）。
        """
        if not content_hashes:
            return {}

        result: dict[str, list[float]] = {}
        with self._lock, self._connect() as conn:
            # SQLite 参数上限 999，分批查询
            batch_size = 900
            for i in range(0, len(content_hashes), batch_size):
                batch = content_hashes[i : i + batch_size]
                placeholders = ",".join("?" * len(batch))
                rows = conn.execute(
                    f"SELECT content_hash, embedding FROM memory_embed_cache WHERE content_hash IN ({placeholders})",
                    batch,
                ).fetchall()

                for row in rows:
                    result[row["content_hash"]] = _deserialize_vector(row["embedding"])

        return result

    def cache_embeddings(
        self,
        items: list[tuple[str, list[float]]],
    ) -> None:
        """
        批量写入嵌入缓存。

        Args:
            items: [(content_hash, embedding), ...] 列表。
        """
        if not items:
            return

        now = datetime.now().isoformat()
        with self._lock, self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO memory_embed_cache(
                    content_hash, embedding, dimension, created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                [
                    (h, _serialize_vector(emb), len(emb), now)
                    for h, emb in items
                ],
            )

    def update_chunk_embeddings(
        self,
        updates: list[tuple[int, list[float]]],
    ) -> int:
        """
        批量更新分块的嵌入向量（用于增量补嵌）。

        Args:
            updates: [(chunk_id, embedding), ...] 列表。

        Returns:
            实际更新的行数。
        """
        if not updates:
            return 0

        now = datetime.now().isoformat()
        updated = 0
        with self._lock, self._connect() as conn:
            for chunk_id, emb in updates:
                result = conn.execute(
                    "UPDATE memory_chunks SET embedding = ?, updated_at = ? WHERE id = ?",
                    (_serialize_vector(emb), now, chunk_id),
                )
                updated += result.rowcount

        if updated > 0:
            logger.debug(f"VectorStore: updated embeddings for {updated} chunks")
        return updated

    # ── 重索引操作 ────────────────────────────────────────────────

    def rebuild_fts(self) -> None:
        """
        原子性重建 FTS5 索引。

        当 FTS5 索引与主表不一致时使用。
        """
        t0 = time.time()
        with self._lock, self._connect() as conn:
            try:
                # FTS5 rebuild 命令
                conn.execute(
                    "INSERT INTO memory_chunks_fts(memory_chunks_fts) VALUES('rebuild')"
                )
                elapsed = time.time() - t0
                logger.info(f"VectorStore: FTS5 rebuild completed in {elapsed:.2f}s")
            except sqlite3.OperationalError as e:
                logger.error(f"VectorStore: FTS5 rebuild failed: {e}")
                raise

    def vacuum(self) -> None:
        """压缩数据库文件。"""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("VACUUM")
                logger.info("VectorStore: VACUUM completed")
            finally:
                conn.close()

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计信息。"""
        with self._lock, self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) as cnt FROM memory_chunks").fetchone()["cnt"]
            embedded = conn.execute(
                "SELECT COUNT(*) as cnt FROM memory_chunks WHERE embedding IS NOT NULL"
            ).fetchone()["cnt"]
            sources = conn.execute(
                "SELECT COUNT(DISTINCT source) as cnt FROM memory_chunks"
            ).fetchone()["cnt"]
            cache_size = conn.execute(
                "SELECT COUNT(*) as cnt FROM memory_embed_cache"
            ).fetchone()["cnt"]

            # 数据库文件大小
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return {
            "total_chunks": total,
            "embedded_chunks": embedded,
            "missing_embeddings": total - embedded,
            "unique_sources": sources,
            "cache_entries": cache_size,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "db_path": str(self.db_path),
        }


# ── 辅助函数 ─────────────────────────────────────────────────────────

def _safe_json_loads(s: str | None) -> dict:
    """安全解析 JSON，失败返回空字典。"""
    if not s:
        return {}
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return {}
