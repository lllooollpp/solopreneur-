"""Agent 持久化记忆系统。

支持两种记忆模式:
1. 传统模式: 文件读取 (daily notes + MEMORY.md)
2. 语义搜索模式: 基于 MemorySearchEngine 的向量 + 关键词混合搜索

当配置了 memory_search 且 enabled=True 时自动启用语义搜索。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from datetime import datetime
from typing import Any

from loguru import logger

from solopreneur.utils.helpers import ensure_dir, today_date


class MemoryStore:
    """
    Agent 的记忆系统。
    
    支持每日笔记 (memory/YYYY-MM-DD.md) 和长期记忆 (MEMORY.md)。
    可选启用语义搜索引擎（MemorySearchEngine）进行基于相似度的记忆召回。
    """
    
    def __init__(self, workspace: Path, memory_search_config: dict[str, Any] | None = None):
        self.workspace = workspace
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self._search_engine = None
        self._search_config = memory_search_config
        self._engine_initialized = False
    
    def get_today_file(self) -> Path:
        """获取当天记忆文件的路径。"""
        return self.memory_dir / f"{today_date()}.md"
    
    def read_today(self) -> str:
        """读取当天的记忆笔记。"""
        today_file = self.get_today_file()
        if today_file.exists():
            return self._read_file_safe(today_file)
        return ""

    def _read_file_safe(self, path: Path) -> str:
        """安全读取文件，支持多种编码。"""
        encodings = ["utf-8", "utf-8-sig", "gbk", "gb2312", "latin1"]
        for enc in encodings:
            try:
                return path.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
        return ""

    def append_today(self, content: str) -> None:
        """向当天的记忆笔记追加内容。"""
        today_file = self.get_today_file()
        
        if today_file.exists():
            existing = self._read_file_safe(today_file)
            content = existing + "\n" + content
        else:
            # 为新的一天添加标题
            header = f"# {today_date()}\n\n"
            content = header + content
        
        today_file.write_text(content, encoding="utf-8")
    
    def read_long_term(self) -> str:
        """读取长期记忆 (MEMORY.md)。"""
        if self.memory_file.exists():
            return self._read_file_safe(self.memory_file)
        return ""
    
    def write_long_term(self, content: str) -> None:
        """写入长期记忆 (MEMORY.md)。"""
        self.memory_file.write_text(content, encoding="utf-8")
    
    def get_recent_memories(self, days: int = 7) -> str:
        """
        获取最近 N 天的记忆。
        
        参数:
            days: 回溯的天数。
        
        返回:
            合并后的记忆内容。
        """
        from datetime import timedelta
        
        memories = []
        today = datetime.now().date()
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = self.memory_dir / f"{date_str}.md"
            
            if file_path.exists():
                content = self._read_file_safe(file_path)
                memories.append(content)
        
        return "\n\n---\n\n".join(memories)
    
    def list_memory_files(self) -> list[Path]:
        """列出所有记忆文件，按日期排序（最新的在前）。"""
        if not self.memory_dir.exists():
            return []
        
        files = list(self.memory_dir.glob("????-??-??.md"))
        return sorted(files, reverse=True)
    
    def get_memory_context(self) -> str:
        """
        获取 Agent 的记忆上下文。
        
        返回:
            格式化的记忆上下文，包括长期记忆和近期记忆。
        """
        parts = []
        
        # 长期记忆
        long_term = self.read_long_term()
        if long_term:
            parts.append("## 长期记忆\n" + long_term)
        
        # 今日笔记
        today = self.read_today()
        if today:
            parts.append("## 今日笔记\n" + today)
        
        return "\n\n".join(parts) if parts else ""

    # ── 语义搜索引擎集成 ─────────────────────────────────────────

    def _ensure_search_engine(self) -> bool:
        """
        确保搜索引擎已初始化（懒加载）。

        Returns:
            True 如果引擎可用。
        """
        if self._engine_initialized:
            return self._search_engine is not None

        self._engine_initialized = True

        if not self._search_config:
            return False

        enabled = self._search_config.get("enabled", True)
        if not enabled:
            logger.debug("MemoryStore: search engine disabled by config")
            return False

        try:
            from solopreneur.storage.memory_engine.engine import MemorySearchEngine

            # 构建 embedding 配置
            embedding_config = {
                "provider": self._search_config.get("embedding_provider", "auto"),
                "model": self._search_config.get("embedding_model", "all-MiniLM-L6-v2"),
                "device": self._search_config.get("embedding_device", "auto"),
                "api_key": self._search_config.get("embedding_api_key", ""),
                "api_base": self._search_config.get("embedding_api_base", ""),
                "dimension": self._search_config.get("embedding_dimension", 384),
                "batch_size": self._search_config.get("embedding_batch_size", 64),
                "providers": self._search_config.get("providers", {}),
            }

            self._search_engine = MemorySearchEngine(
                workspace=self.workspace,
                embedding_config=embedding_config,
                vector_weight=self._search_config.get("vector_weight", 0.6),
                keyword_weight=self._search_config.get("keyword_weight", 0.4),
                max_chunk_size=self._search_config.get("max_chunk_size", 1200),
                min_chunk_size=self._search_config.get("min_chunk_size", 100),
            )

            logger.info(
                f"MemoryStore: search engine initialized "
                f"(embedder={self._search_engine.embedder.name})"
            )
            return True

        except Exception as e:
            logger.warning(f"MemoryStore: failed to initialize search engine: {e}")
            self._search_engine = None
            return False

    @property
    def search_engine(self):
        """获取搜索引擎实例（如果可用）。"""
        if self._ensure_search_engine():
            return self._search_engine
        return None

    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> str:
        """
        执行语义搜索，返回格式化的记忆片段。

        Args:
            query: 搜索查询。
            top_k: 返回条数。
            min_score: 最低分数阈值。

        Returns:
            格式化的搜索结果文本，可直接注入 system prompt。
            如果搜索引擎不可用，返回空字符串。
        """
        if not self._ensure_search_engine():
            return ""

        try:
            results = await self._search_engine.search(
                query=query,
                top_k=top_k,
                min_score=min_score,
            )

            if not results:
                return ""

            parts = []
            for i, r in enumerate(results, 1):
                score_label = f"[相关度: {r.score:.0%}]"
                src_label = f"(来源: {r.source})" if r.source else ""
                heading = f"{r.heading_context}" if r.heading_context else ""
                parts.append(
                    f"### 记忆片段 {i} {score_label} {src_label}\n"
                    f"{heading}\n{r.content}" if heading
                    else f"### 记忆片段 {i} {score_label} {src_label}\n{r.content}"
                )

            return "\n\n".join(parts)

        except Exception as e:
            logger.warning(f"MemoryStore: semantic search failed: {type(e).__name__}: {e}")
            return ""

    def semantic_search_sync(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.1,
    ) -> str:
        """
        语义搜索的同步包装（用于不在 async 上下文中的场景）。
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已在 async 上下文中，创建 task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.semantic_search(query, top_k, min_score),
                    )
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(
                    self.semantic_search(query, top_k, min_score)
                )
        except Exception as e:
            logger.debug(f"MemoryStore: sync semantic search failed: {e}")
            return ""

    async def index_memory_files(self) -> dict[str, int]:
        """
        索引所有记忆文件到搜索引擎。

        Returns:
            {source: written_count} 字典。
        """
        if not self._ensure_search_engine():
            return {}

        try:
            return await self._search_engine.index_memory_dir()
        except Exception as e:
            logger.warning(f"MemoryStore: index failed: {e}")
            return {}

    async def index_text(self, text: str, source: str) -> int:
        """
        索引一段文本到搜索引擎。

        Returns:
            写入的分块数。
        """
        if not self._ensure_search_engine():
            return 0

        try:
            return await self._search_engine.index_text(text, source=source)
        except Exception as e:
            logger.warning(f"MemoryStore: index_text failed: {e}")
            return 0

    def get_search_stats(self) -> dict[str, Any]:
        """获取搜索引擎统计信息。"""
        if not self._ensure_search_engine():
            return {"enabled": False}

        try:
            stats = self._search_engine.get_stats()
            stats["enabled"] = True
            return stats
        except Exception:
            return {"enabled": False, "error": "stats unavailable"}
