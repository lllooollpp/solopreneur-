"""
上下文压缩引�?�?�?Claude Code 三层压缩策略�?

三层设计:
1. Microcompaction (微压�? �?对大型工具输出即时落盘，仅保留热尾部引用
2. Auto-compaction (自动压缩) �?token 累计超阈值时，用 LLM 生成结构化摘要替换旧消息
3. Manual-compaction (手动压缩) �?未来可接�?/compact 命令

核心理念:
- 压缩 �?简单截断。是"摘要 + 恢复"：生成结构化工作状态，然后重新注入续接指令�?
- 保留意图、决策、错误、待办和下一步，确保 LLM 能无缝继续工作�?
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from solopreneur.providers.base import LLMProvider


# ── 常量 ───────────────────────────────────────────────────────────────

# 微压缩：工具结果超过此字符数时落盘，只保留摘要引�?
MICRO_COMPACT_THRESHOLD = 8000
# 微压缩：热尾部保留的最近工具结果数（不压缩�?
MICRO_HOT_TAIL = 6
# 自动压缩：保留最近的消息数量不被替换
AUTO_KEEP_RECENT = 4
# 字符→token 粗估比例 (中英混合�?1 token �?2-3 字符)
CHARS_PER_TOKEN = 2.5


# ── 结构化摘要提示词（核心） ──────────────────────────────────────────

COMPACTION_SYSTEM_PROMPT = """\
你是一个上下文压缩助手。你的任务是将以下对话压缩为一�?*结构化工作状态摘�?*�?

## 输出要求

请严格按以下 9 个章节输出，每个章节都必须包含（如果没有相关内容则写"�?）：

### 1. 用户意图
用户最初要求做什么？中间有过什么变更？

### 2. 当前任务状�?
目前进行到了什么阶段？哪些已完成？哪些正在进行�?

### 3. 关键技术决�?
做出了哪些重要的技术选型、架构决策？依据是什么？

### 4. 已修改的文件
列出所有被创建、修改或删除的文件，每个文件用一句话说明改动内容�?

### 5. 遇到的错误与解决方案
记录所有遇到的错误以及如何修复的�?

### 6. 重要的代码片段与数据
如果有关键的代码模式、配置值、API 接口等需要保留，简洁列出�?

### 7. 待完成事�?
列出尚未完成的任务，越具体越好�?

### 8. 下一步行�?
基于当前状态，下一步应该做什么？

### 9. 上下文恢复提�?
列出恢复工作时需要重新读取的文件路径（最�?5 个最相关的）�?

## 规则
- 输出必须是能让另一�?LLM 完全接手工作的状态快�?
- 不要遗漏任何关键信息
- 保持简洁，但不要丢失重要细�?
- 代码片段只保留关键部分（如函数签名、配置项），不要整段搬运
"""

CONTINUATION_MESSAGE = """\
本次会话从上一段对话的压缩摘要继续。以下摘要涵盖了之前的全部工作内容�?

{summary}

请根据摘要中�?下一步行�?继续工作，不要向用户确认，直接执行�?""


class CompactionEngine:
    """
    三层上下文压缩引擎�?

    层级:
    1. microcompact() �?即时处理大型工具输出，落�?+ 保留引用
    2. auto_compact() �?LLM 驱动的结构化摘要压缩
    3. estimate_tokens() �?token 估算，决定何时触发压�?

    Usage:
        engine = CompactionEngine(provider, workspace)

        # 每次工具结果返回后：
        messages = engine.microcompact(messages)

        # token 超限时：
        if engine.estimate_tokens(messages) > threshold:
            messages = await engine.auto_compact(messages)
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
    ):
        self.provider = provider
        self.workspace = workspace
        self.model = model
        self._compaction_count = 0
        self._compaction_dir = workspace / ".compaction"
        self._tool_result_index = 0  # 全局工具结果计数，用于文件名

    # ── 1. Microcompaction ──────────────────────────────────────────

    def microcompact(self, messages: list[dict]) -> list[dict]:
        """
        微压缩：将大型工具结果落盘，上下文中只保留引用�?

        策略�?
        - 最�?MICRO_HOT_TAIL 个工具结果保持内联（热尾部）
        - 更早的工具结果，如果超过 MICRO_COMPACT_THRESHOLD 字符�?
          则保存到磁盘并替换为引用

        Args:
            messages: 当前消息列表

        Returns:
            微压缩后的消息列�?
        """
        # 找出所�?tool result 的索�?
        tool_indices = [
            i for i, m in enumerate(messages) if m.get("role") == "tool"
        ]

        if len(tool_indices) <= MICRO_HOT_TAIL:
            return messages  # 工具结果太少，无需微压�?

        # 需要检查的旧工具结果（排除热尾部）
        cold_indices = set(tool_indices[:-MICRO_HOT_TAIL])
        compacted = False

        for i in cold_indices:
            msg = messages[i]
            content = msg.get("content", "")
            if len(content) > MICRO_COMPACT_THRESHOLD:
                # 落盘
                saved_path = self._save_tool_result_to_disk(
                    tool_name=msg.get("name", "unknown"),
                    content=content,
                )
                # 替换为引�?
                summary = self._make_tool_reference(
                    tool_name=msg.get("name", "unknown"),
                    content=content,
                    saved_path=saved_path,
                )
                messages[i] = {**msg, "content": summary}
                compacted = True

        if compacted:
            logger.info(f"微压缩完�? {len(cold_indices)} 个旧工具结果已检�?)

        return messages

    def _save_tool_result_to_disk(self, tool_name: str, content: str) -> str:
        """将工具结果保存到磁盘，返回文件路径�?""
        self._compaction_dir.mkdir(parents=True, exist_ok=True)
        self._tool_result_index += 1
        filename = f"tool_{self._tool_result_index}_{tool_name}_{int(time.time())}.txt"
        filepath = self._compaction_dir / filename
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    @staticmethod
    def _make_tool_reference(tool_name: str, content: str, saved_path: str) -> str:
        """生成工具结果的简短引用摘要�?""
        # 保留�?500 字符作为预览
        preview = content[:500]
        total_chars = len(content)

        return (
            f"[工具 `{tool_name}` 输出已保存到磁盘]\n"
            f"路径: {saved_path}\n"
            f"大小: {total_chars} 字符\n"
            f"预览:\n{preview}\n"
            f"...\n"
            f"如需完整内容，请使用 read_file 读取上述路径�?
        )

    # ── 2. Auto-compaction (LLM 驱动) ──────────────────────────────

    async def auto_compact(
        self,
        messages: list[dict],
        focus_hint: str = "",
    ) -> list[dict]:
        """
        自动压缩：使�?LLM 生成结构化摘要，替换旧消息�?

        流程�?
        1. 提取 system prompt（保留）
        2. 将旧消息发给 LLM 生成 9 段式结构化摘�?
        3. �?[system, continuation_message, recent_messages] 替换整个消息列表
        4. 重新注入最近访问的文件内容（如果在摘要中提到）

        Args:
            messages: 当前消息列表
            focus_hint: 可选的焦点提示，类�?/compact 的参�?

        Returns:
            压缩后的新消息列�?
        """
        self._compaction_count += 1
        logger.info(f"执行自动压缩 (�?{self._compaction_count} �?")

        if len(messages) <= AUTO_KEEP_RECENT + 2:
            logger.info("消息太少，跳过压�?)
            return messages

        # 分离 system prompt
        system_msg = None
        conversation = []
        for msg in messages:
            if msg.get("role") == "system" and system_msg is None:
                system_msg = msg
            else:
                conversation.append(msg)

        # 分离最近消息（保持完整�?
        if len(conversation) > AUTO_KEEP_RECENT:
            old_messages = conversation[:-AUTO_KEEP_RECENT]
            recent_messages = conversation[-AUTO_KEEP_RECENT:]
        else:
            # 对话太短则不压缩
            return messages

        # 构建摘要请求
        summary = await self._generate_summary(old_messages, focus_hint)

        # 组装新消息列�?
        compacted: list[dict] = []

        # 1. 保留原始 system prompt
        if system_msg:
            compacted.append(system_msg)

        # 2. 插入续接消息（包含压缩摘要）
        continuation = CONTINUATION_MESSAGE.format(summary=summary)
        compacted.append({
            "role": "user",
            "content": continuation,
        })

        # 3. 插入一�?assistant 确认消息
        compacted.append({
            "role": "assistant",
            "content": (
                "好的，我已阅读之前的工作摘要，了解当前进度�?
                "我将根据摘要中的待办事项和下一步行动继续工作�?
            ),
        })

        # 4. 附加最近的完整消息
        compacted.extend(recent_messages)

        # 保存摘要到磁盘（便于调试和审计）
        self._save_compaction_summary(summary)

        old_token_est = self.estimate_tokens(messages)
        new_token_est = self.estimate_tokens(compacted)
        logger.info(
            f"自动压缩完成: {len(messages)} �?{len(compacted)} 条消�? "
            f"token 估计: ~{old_token_est} �?~{new_token_est} "
            f"(节省 ~{old_token_est - new_token_est})"
        )

        return compacted

    async def _generate_summary(
        self,
        old_messages: list[dict],
        focus_hint: str = "",
    ) -> str:
        """
        使用 LLM 对旧消息生成结构化摘要�?

        Args:
            old_messages: 需要压缩的旧消息列�?
            focus_hint: 可选的焦点提示

        Returns:
            结构化摘要文�?
        """
        # 构建发给 LLM 的消�?
        summary_messages: list[dict[str, Any]] = [
            {"role": "system", "content": COMPACTION_SYSTEM_PROMPT},
        ]

        # 将旧的对话序列化为文�?
        conversation_text = self._serialize_messages(old_messages)

        user_prompt = f"请压缩以下对话为结构化工作状态摘要：\n\n{conversation_text}"
        if focus_hint:
            user_prompt += f"\n\n特别关注: {focus_hint}"

        summary_messages.append({"role": "user", "content": user_prompt})

        try:
            response = await self.provider.chat(
                messages=summary_messages,
                tools=None,
                model=self.model,
                max_tokens=4096,
                temperature=0.2,  # 低温度确保摘要准�?
            )
            summary = response.content or "压缩失败：LLM 未返回摘要内容�?
            logger.info(f"生成摘要成功: {len(summary)} 字符")
            return summary
        except Exception as e:
            logger.error(f"LLM 摘要生成失败: {e}")
            # 回退到简单截�?
            return self._fallback_summary(old_messages)

    @staticmethod
    def _serialize_messages(messages: list[dict]) -> str:
        """将消息列表序列化为可读文本�?""
        parts: list[str] = []

        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "assistant":
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    calls_desc = ", ".join(
                        tc.get("function", {}).get("name", "?")
                        for tc in tool_calls
                    )
                    parts.append(f"[Assistant] 调用工具: {calls_desc}")
                    if content:
                        # 截断过长�?assistant 文本
                        text = content[:2000] if len(content) > 2000 else content
                        parts.append(f"  文本: {text}")
                else:
                    text = content[:3000] if len(content) > 3000 else content
                    parts.append(f"[Assistant] {text}")

            elif role == "tool":
                name = msg.get("name", "unknown")
                # 工具结果截断保留关键信息
                text = content[:2000] if len(content) > 2000 else content
                parts.append(f"[Tool: {name}] {text}")

            elif role == "user":
                text = content[:2000] if isinstance(content, str) and len(content) > 2000 else content
                parts.append(f"[User] {text}")

            elif role == "system":
                parts.append(f"[System] (系统提示，已省略)")

        return "\n\n".join(parts)

    @staticmethod
    def _fallback_summary(old_messages: list[dict]) -> str:
        """�?LLM 摘要失败时的回退方案：提取关键信息的简单模板�?""
        tools_used: list[str] = []
        files_mentioned: set[str] = set()
        user_messages: list[str] = []

        for msg in old_messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and isinstance(content, str):
                user_messages.append(content[:200])

            if role == "assistant":
                for tc in msg.get("tool_calls", []):
                    func = tc.get("function", {})
                    name = func.get("name", "")
                    if name:
                        tools_used.append(name)
                    # 提取文件路径
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                        for key in ("path", "file_path", "filepath"):
                            if key in args:
                                files_mentioned.add(args[key])
                    except (json.JSONDecodeError, TypeError):
                        pass

        summary_parts = ["### 回退摘要（LLM 摘要生成失败）\n"]

        if user_messages:
            summary_parts.append("**用户请求:**")
            for m in user_messages[:5]:
                summary_parts.append(f"- {m}")

        if tools_used:
            unique_tools = list(dict.fromkeys(tools_used))  # 去重保序
            summary_parts.append(f"\n**使用的工�?** {', '.join(unique_tools[:20])}")

        if files_mentioned:
            summary_parts.append(f"\n**涉及的文�?**")
            for f in sorted(files_mentioned)[:10]:
                summary_parts.append(f"- {f}")

        return "\n".join(summary_parts)

    def _save_compaction_summary(self, summary: str) -> None:
        """将摘要保存到磁盘（审�?调试用）�?""
        try:
            self._compaction_dir.mkdir(parents=True, exist_ok=True)
            filename = f"summary_{self._compaction_count}_{int(time.time())}.md"
            filepath = self._compaction_dir / filename
            filepath.write_text(summary, encoding="utf-8")
            logger.debug(f"压缩摘要已保�? {filepath}")
        except Exception as e:
            logger.warning(f"保存压缩摘要失败: {e}")

    # ── 3. Token 估算 ───────────────────────────────────────────────

    @staticmethod
    def estimate_tokens(messages: list[dict]) -> int:
        """
        粗估消息列表�?token 数量�?

        使用 字符�?/ CHARS_PER_TOKEN 的简单估算�?
        对于中英混合文本�? token �?2-3 个字符�?

        Args:
            messages: 消息列表

        Returns:
            估算�?token �?
        """
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                # vision 格式
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        total_chars += len(item.get("text", ""))

            # tool_calls 中的参数也计�?
            for tc in msg.get("tool_calls", []):
                func = tc.get("function", {})
                total_chars += len(func.get("arguments", ""))
                total_chars += len(func.get("name", ""))

        return int(total_chars / CHARS_PER_TOKEN)

    # ── 4. 子代理增量摘�?──────────────────────────────────────────

    async def delta_summarize(
        self,
        prev_summary: str,
        new_messages: list[dict],
    ) -> str:
        """
        增量摘要（用于子代理/后台任务），类似 Claude Code �?background task summarization�?

        不会重新处理整段对话，而是基于上次摘要 + 新消息生成增�?1-2 句更新�?

        Args:
            prev_summary: 上次的摘�?
            new_messages: 自上次摘要以来的新消�?

        Returns:
            更新后的摘要
        """
        new_text = self._serialize_messages(new_messages)

        delta_prompt = (
            "你需要基于之前的摘要和新的对话内容，生成一个更新后的简短摘要。\n"
            "要求: 1-3 句话，聚焦最重要的进展。\n\n"
            f"之前的摘�?\n{prev_summary}\n\n"
            f"新的对话内容:\n{new_text}\n\n"
            "请输出更新后的摘要（1-3 句话�?"
        )

        try:
            response = await self.provider.chat(
                messages=[
                    {"role": "system", "content": "你是一个简洁的摘要助手�?},
                    {"role": "user", "content": delta_prompt},
                ],
                tools=None,
                model=self.model,
                max_tokens=500,
                temperature=0.2,
            )
            return response.content or prev_summary
        except Exception as e:
            logger.warning(f"增量摘要失败: {e}")
            return prev_summary

    # ── 便捷方法 ────────────────────────────────────────────────────

    @property
    def compaction_count(self) -> int:
        """已执行的自动压缩次数�?""
        return self._compaction_count

    def should_compact(
        self,
        messages: list[dict],
        token_threshold: int,
        usage_ratio: float = 0.78,
    ) -> bool:
        """
        判断是否应该触发自动压缩�?

        Args:
            messages: 当前消息列表
            token_threshold: token 上限
            usage_ratio: 使用率阈值（默认 78%，参�?Claude Code�?

        Returns:
            是否应该压缩
        """
        estimated = self.estimate_tokens(messages)
        threshold = int(token_threshold * usage_ratio)

        if estimated > threshold:
            logger.debug(
                f"上下文使用率: ~{estimated}/{token_threshold} "
                f"(>{usage_ratio*100:.0f}% = {threshold})，建议压�?
            )
            return True
        return False
