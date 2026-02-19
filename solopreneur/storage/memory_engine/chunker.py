"""
Markdown 感知分块器 — 按标题层级智能分割文档。

核心特性:
1. 按 Markdown 标题层级 (# ~ ####) 分割文档为语义完整的块
2. 每个块携带标题上下文链（面包屑），例如 "# 项目 > ## 架构 > ### 数据库"
3. 支持最大块大小限制 — 超长段落自动按句分割
4. 代码块感知 — 不会在代码块中间分割
5. 为非 Markdown 纯文本提供回退的固定窗口分块

设计原则:
- 分块粒度不宜过细（避免召回碎片），也不宜过大（避免向量稀释）
- 目标: 每块 200~1500 字符，保留语义完整性
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


# ── 分块结果数据结构 ──────────────────────────────────────────────────

@dataclass
class Chunk:
    """一个分块结果。"""

    content: str
    """块的实际文本内容。"""

    heading_context: str
    """标题上下文链（面包屑），如 "# 项目概述 > ## 架构设计 > ### 数据层"。"""

    source: str
    """来源标识符（文件路径、日期等）。"""

    chunk_index: int
    """在同一来源中的序号 (0-based)。"""

    metadata: dict = field(default_factory=dict)
    """附加元数据（如日期、标签等）。"""

    @property
    def content_hash(self) -> str:
        """内容的 SHA-256 摘要，用于去重和缓存键。"""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()[:16]

    @property
    def search_text(self) -> str:
        """用于 FTS 索引的完整文本（标题上下文 + 内容）。"""
        if self.heading_context:
            return f"{self.heading_context}\n{self.content}"
        return self.content

    @property
    def char_count(self) -> int:
        return len(self.content)

    def __repr__(self) -> str:
        preview = self.content[:60].replace("\n", "↵")
        return f"Chunk(src={self.source!r}, idx={self.chunk_index}, chars={self.char_count}, heading={self.heading_context!r}, preview={preview!r})"


# ── Markdown 分块器 ───────────────────────────────────────────────────

# 匹配 # ~ #### 标题行
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# 匹配代码块起止
_CODE_FENCE_RE = re.compile(r"^```", re.MULTILINE)

# 用于按句子分割的正则
_SENTENCE_RE = re.compile(r"(?<=[.!?。！？\n])\s+")


class MarkdownChunker:
    """
    Markdown 感知分块器。

    用法:
        chunker = MarkdownChunker(max_chunk_size=1200, min_chunk_size=100)
        chunks = chunker.chunk(text, source="memory/2024-01-15.md")
    """

    def __init__(
        self,
        max_chunk_size: int = 1200,
        min_chunk_size: int = 100,
        overlap_chars: int = 50,
    ):
        """
        Args:
            max_chunk_size: 单块最大字符数。超过则按句分割。
            min_chunk_size: 单块最小字符数。低于则合并到前一块。
            overlap_chars: 相邻块之间的字符重叠量（提高召回连续性）。
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_chars = overlap_chars

    def chunk(
        self,
        text: str,
        source: str = "",
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """
        将 Markdown 文本分块。

        Args:
            text: 要分块的 Markdown 文本。
            source: 来源标识符。
            metadata: 附加到每个块的元数据。

        Returns:
            Chunk 列表。
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}

        # 检测是否是 Markdown（包含标题）
        if _HEADING_RE.search(text):
            return self._chunk_markdown(text, source, metadata)
        else:
            return self._chunk_plain(text, source, metadata)

    def _chunk_markdown(
        self,
        text: str,
        source: str,
        metadata: dict,
    ) -> list[Chunk]:
        """按 Markdown 标题层级分块。"""
        sections = self._split_by_headings(text)
        chunks: list[Chunk] = []
        chunk_idx = 0

        for heading_ctx, content in sections:
            content = content.strip()
            if not content:
                continue

            # 如果段落太短，尝试与前一个块合并
            if len(content) < self.min_chunk_size and chunks:
                prev = chunks[-1]
                merged = prev.content + "\n\n" + content
                if len(merged) <= self.max_chunk_size:
                    chunks[-1] = Chunk(
                        content=merged,
                        heading_context=prev.heading_context,
                        source=source,
                        chunk_index=prev.chunk_index,
                        metadata=metadata,
                    )
                    continue

            # 如果段落太长，按句分割
            if len(content) > self.max_chunk_size:
                sub_chunks = self._split_long_text(content)
                for sub in sub_chunks:
                    chunks.append(Chunk(
                        content=sub,
                        heading_context=heading_ctx,
                        source=source,
                        chunk_index=chunk_idx,
                        metadata=metadata,
                    ))
                    chunk_idx += 1
            else:
                chunks.append(Chunk(
                    content=content,
                    heading_context=heading_ctx,
                    source=source,
                    chunk_index=chunk_idx,
                    metadata=metadata,
                ))
                chunk_idx += 1

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """
        按标题层级分割文本，返回 (heading_context, content) 对。

        维护一个标题栈来生成面包屑:
        - 遇到 # 标题 → 清空栈，压入
        - 遇到 ## 标题 → 弹出 >= ## 的，压入
        - 以此类推
        """
        lines = text.split("\n")
        sections: list[tuple[str, str]] = []
        heading_stack: list[tuple[int, str]] = []  # (level, title)
        current_lines: list[str] = []
        in_code_block = False

        def flush():
            content = "\n".join(current_lines)
            ctx = self._build_heading_context(heading_stack)
            if content.strip():
                sections.append((ctx, content))
            current_lines.clear()

        for line in lines:
            # 代码块感知
            if _CODE_FENCE_RE.match(line):
                in_code_block = not in_code_block
                current_lines.append(line)
                continue

            if in_code_block:
                current_lines.append(line)
                continue

            heading_match = _HEADING_RE.match(line)
            if heading_match:
                # 遇到标题：先刷新当前块
                flush()

                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()

                # 更新标题栈：弹出同级或更低级的标题
                while heading_stack and heading_stack[-1][0] >= level:
                    heading_stack.pop()
                heading_stack.append((level, title))

                # 标题行本身也作为内容的一部分
                current_lines.append(line)
            else:
                current_lines.append(line)

        # 处理最后一个块
        flush()

        return sections

    @staticmethod
    def _build_heading_context(stack: list[tuple[int, str]]) -> str:
        """将标题栈转为面包屑字符串。"""
        if not stack:
            return ""
        parts = []
        for level, title in stack:
            prefix = "#" * level
            parts.append(f"{prefix} {title}")
        return " > ".join(parts)

    def _split_long_text(self, text: str) -> list[str]:
        """将超长文本按句子分割为多个子块。"""
        sentences = _SENTENCE_RE.split(text)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > self.max_chunk_size and current:
                chunk_text = " ".join(current)
                chunks.append(chunk_text)

                # 重叠：保留尾部一些内容
                if self.overlap_chars > 0 and chunk_text:
                    overlap = chunk_text[-self.overlap_chars :]
                    current = [overlap]
                    current_len = len(overlap)
                else:
                    current = []
                    current_len = 0

            current.append(sent)
            current_len += sent_len

        if current:
            chunks.append(" ".join(current))

        return chunks if chunks else [text]

    def _chunk_plain(
        self,
        text: str,
        source: str,
        metadata: dict,
    ) -> list[Chunk]:
        """对非 Markdown 纯文本进行固定窗口分块。"""
        chunks: list[Chunk] = []
        chunk_idx = 0
        pos = 0
        step = self.max_chunk_size - self.overlap_chars

        while pos < len(text):
            end = min(pos + self.max_chunk_size, len(text))
            segment = text[pos:end].strip()

            if segment and len(segment) >= self.min_chunk_size:
                chunks.append(Chunk(
                    content=segment,
                    heading_context="",
                    source=source,
                    chunk_index=chunk_idx,
                    metadata=metadata,
                ))
                chunk_idx += 1
            elif segment and chunks:
                # 尾部碎片合并到最后一块
                prev = chunks[-1]
                chunks[-1] = Chunk(
                    content=prev.content + "\n" + segment,
                    heading_context=prev.heading_context,
                    source=source,
                    chunk_index=prev.chunk_index,
                    metadata=metadata,
                )

            pos += step

        return chunks
