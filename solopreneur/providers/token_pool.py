"""
GitHub Copilot 多账�?Token 池管理器
支持多账号负载均衡、熔断冷却、自动恢�?
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from loguru import logger

try:
    from solopreneur.providers.github_copilot import _encrypt_token, _decrypt_token, CRYPTO_AVAILABLE
except ImportError:
    CRYPTO_AVAILABLE = False
    _encrypt_token = _decrypt_token = lambda t: t


class SlotState(str, Enum):
    """Token 槽位状�?""
    ACTIVE = "active"        # 正常可用
    COOLING = "cooling"      # 触发 429，冷却中
    EXPIRED = "expired"      # Copilot Token 过期，需刷新
    DEAD = "dead"            # GitHub token 失效，需重新登录


@dataclass
class TokenSlot:
    """单个账号�?Token 槽位"""
    slot_id: int
    github_access_token: str
    copilot_token: str
    expires_at: datetime
    state: SlotState = SlotState.ACTIVE
    cooling_until: float = 0.0          # 冷却截止时间 (unix timestamp)
    consecutive_errors: int = 0          # 连续错误计数
    total_requests: int = 0              # 总请求计�?
    total_429s: int = 0                  # �?429 计数
    last_used_at: float = 0.0           # 上次使用时间
    label: str = ""                      # 可选标签（�?"账号A"�?

    # Token 限制配置
    max_tokens_per_day: int = 0           # 每日最�?Token 限制�?=无限制）
    max_requests_per_day: int = 0         # 每日最大请求次数限制（0=无限制）
    max_requests_per_hour: int = 0        # 每小时最大请求次数限制（0=无限制）

    # 使用统计
    tokens_used_today: int = 0           # 今日已使�?Token
    tokens_used_history: list[dict] = field(default_factory=list)  # 历史使用记录
    requests_today: int = 0               # 今日请求�?
    requests_hour: int = 0                # 当前小时请求�?
    last_reset_date: str = ""             # 上次重置日期
    last_reset_hour: int = -1             # 上次重置小时

    @property
    def is_available(self) -> bool:
        """当前是否可用于请�?""
        if self.state == SlotState.ACTIVE:
            return True
        if self.state == SlotState.COOLING:
            # 冷却期已过，自动恢复
            if time.time() >= self.cooling_until:
                return True
        return False

    @property
    def is_token_expired(self) -> bool:
        """Copilot token 是否已过期或即将过期"""
        return datetime.now() + timedelta(minutes=5) >= self.expires_at

    def check_rate_limit(self) -> tuple[bool, str | None]:
        """
        检查是否达到自定义速率限制

        Returns:
            (是否允许, 拒绝原因)
        """
        self._reset_counters_if_needed()

        # 检查每�?Token 限制
        if self.max_tokens_per_day > 0 and self.tokens_used_today >= self.max_tokens_per_day:
            return False, f"达到每日 Token 限制 ({self.tokens_used_today}/{self.max_tokens_per_day})"

        # 检查每日请求限�?
        if self.max_requests_per_day > 0 and self.requests_today >= self.max_requests_per_day:
            return False, f"达到每日请求限制 ({self.requests_today}/{self.max_requests_per_day})"

        # 检查每小时请求限制
        if self.max_requests_per_hour > 0 and self.requests_hour >= self.max_requests_per_hour:
            return False, f"达到每小时请求限�?({self.requests_hour}/{self.max_requests_per_hour})"

        return True, None

    def record_usage(self, tokens_used: int = 0):
        """记录 Token 使用"""
        self._reset_counters_if_needed()

        if tokens_used > 0:
            self.tokens_used_today += tokens_used

            # 记录历史
            self.tokens_used_history.append({
                "timestamp": datetime.now().isoformat(),
                "tokens": tokens_used,
            })
            # 保留最�?7 天的记录
            cutoff = datetime.now() - timedelta(days=7)
            self.tokens_used_history = [
                h for h in self.tokens_used_history
                if datetime.fromisoformat(h["timestamp"]) > cutoff
            ]

        self.requests_today += 1
        self.requests_hour += 1

    def get_usage_summary(self) -> dict:
        """获取使用统计摘要"""
        self._reset_counters_if_needed()
        return {
            "tokens_used_today": self.tokens_used_today,
            "requests_today": self.requests_today,
            "requests_hour": self.requests_hour,
            "tokens_limit": self.max_tokens_per_day or "无限�?,
            "requests_day_limit": self.max_requests_per_day or "无限�?,
            "requests_hour_limit": self.max_requests_per_hour or "无限�?,
        }

    def _reset_counters_if_needed(self):
        """重置计数器（按日期和小时�?""
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        current_hour = now.hour

        # 日重�?
        if self.last_reset_date != today:
            self.last_reset_date = today
            self.requests_today = 0
            self.tokens_used_today = 0
            logger.debug(f"[TokenPool] Slot {self.slot_id} 计数器日重置")

        # 小时重置
        if self.last_reset_hour != current_hour:
            self.last_reset_hour = current_hour
            self.requests_hour = 0
            logger.debug(f"[TokenPool] Slot {self.slot_id} 计数器小时重�?)


class TokenPool:
    """
    多账�?Token 池管理器

    特性：
    - 轮询 (Round-Robin) 负载均衡
    - 熔断�?(Circuit Breaker)�?29 �?自动冷却
    - 指数退避冷却时间：30s �?60s �?120s �?最�?300s
    - 自动 Token 刷新
    - 全部冷却时智能等�?
    - 支持从配置文件读取全局默认�?
    """

    # 默认冷却策略常量（可被配置覆盖）
    BASE_COOLDOWN_S = 30           # 基础冷却时间（秒�?
    MAX_COOLDOWN_S = 300           # 最大冷却时间（秒）
    DEAD_THRESHOLD = 10            # 连续错误次数达到此值标记为 DEAD

    # 默认 Token 限制（可被配置覆盖）
    DEFAULT_MAX_TOKENS_PER_DAY = 0
    DEFAULT_MAX_REQUESTS_PER_DAY = 0
    DEFAULT_MAX_REQUESTS_PER_HOUR = 0

    def __init__(self, pool_dir: Path | None = None, config=None):
        self._pool_dir = pool_dir or (Path.home() / ".nanobot" / "pool")
        self._pool_dir.mkdir(parents=True, exist_ok=True)
        self._slots: dict[int, TokenSlot] = {}
        self._current_index = 0  # 轮询指针
        self._lock = asyncio.Lock()

        # 从配置文件加载全局默认�?
        if config and hasattr(config, 'token_pool'):
            tp = config.token_pool
            self.BASE_COOLDOWN_S = tp.base_cooldown_seconds
            self.MAX_COOLDOWN_S = tp.max_cooldown_seconds
            self.DEAD_THRESHOLD = tp.dead_threshold
            self.DEFAULT_MAX_TOKENS_PER_DAY = tp.max_tokens_per_day
            self.DEFAULT_MAX_REQUESTS_PER_DAY = tp.max_requests_per_day
            self.DEFAULT_MAX_REQUESTS_PER_HOUR = tp.max_requests_per_hour
            logger.info(f"[TokenPool] 从配置加�? max_tokens/day={self.DEFAULT_MAX_TOKENS_PER_DAY or '无限�?}, "
                       f"max_requests/day={self.DEFAULT_MAX_REQUESTS_PER_DAY or '无限�?}, "
                       f"max_requests/hour={self.DEFAULT_MAX_REQUESTS_PER_HOUR or '无限�?}")

        # 启动时加载所有已保存�?slot
        self._load_all_slots()

    # ========================================================================
    # 公开 API
    # ========================================================================

    @property
    def size(self) -> int:
        """池中 slot 总数"""
        return len(self._slots)

    @property
    def active_count(self) -> int:
        """当前可用 slot 数量"""
        return sum(1 for s in self._slots.values() if s.is_available)

    @property
    def all_slots(self) -> list[TokenSlot]:
        """返回所�?slot（按 id 排序�?""
        return sorted(self._slots.values(), key=lambda s: s.slot_id)

    def add_slot(
        self,
        slot_id: int,
        github_access_token: str,
        copilot_token: str,
        expires_at: datetime,
        label: str = "",
        max_tokens_per_day: int | None = None,
        max_requests_per_day: int | None = None,
        max_requests_per_hour: int | None = None,
    ) -> TokenSlot:
        """
        添加或更新一�?Token 槽位

        Args:
            slot_id: 槽位编号�?-based�?
            github_access_token: GitHub OAuth Token
            copilot_token: Copilot API Token
            expires_at: Token 过期时间
            label: 可选的标签�?
            max_tokens_per_day: 每日最�?Token 限制（None=使用配置默认�? 0=无限制）
            max_requests_per_day: 每日最大请求次数限制（None=使用配置默认�? 0=无限制）
            max_requests_per_hour: 每小时最大请求次数限制（None=使用配置默认�? 0=无限制）

        Returns:
            创建/更新后的 TokenSlot
        """
        # 如果 slot 已存在，保留现有限制配置
        existing_limits = {}
        if slot_id in self._slots:
            existing = self._slots[slot_id]
            existing_limits = {
                "max_tokens_per_day": existing.max_tokens_per_day,
                "max_requests_per_day": existing.max_requests_per_day,
                "max_requests_per_hour": existing.max_requests_per_hour,
                "tokens_used_today": existing.tokens_used_today,
                "requests_today": existing.requests_today,
                "requests_hour": existing.requests_hour,
                "last_reset_date": existing.last_reset_date,
                "last_reset_hour": existing.last_reset_hour,
                "tokens_used_history": existing.tokens_used_history,
            }

        slot = TokenSlot(
            slot_id=slot_id,
            github_access_token=github_access_token,
            copilot_token=copilot_token,
            expires_at=expires_at,
            state=SlotState.ACTIVE,
            label=label or f"账号{slot_id}",
            max_tokens_per_day=max_tokens_per_day if max_tokens_per_day is not None else self.DEFAULT_MAX_TOKENS_PER_DAY,
            max_requests_per_day=max_requests_per_day if max_requests_per_day is not None else self.DEFAULT_MAX_REQUESTS_PER_DAY,
            max_requests_per_hour=max_requests_per_hour if max_requests_per_hour is not None else self.DEFAULT_MAX_REQUESTS_PER_HOUR,
            **existing_limits,
        )
        self._slots[slot_id] = slot
        self._save_slot(slot)
        logger.info(f"[TokenPool] Slot {slot_id} ({slot.label}) 已添�?更新")
        return slot

    def remove_slot(self, slot_id: int) -> bool:
        """移除一�?slot"""
        if slot_id in self._slots:
            del self._slots[slot_id]
            slot_file = self._pool_dir / f"slot_{slot_id}.json"
            if slot_file.exists():
                slot_file.unlink()
            logger.info(f"[TokenPool] Slot {slot_id} 已移�?)
            return True
        return False

    async def acquire(self) -> TokenSlot:
        """
        获取一个可用的 Token 槽位（核心调度方法）

        策略�?
        1. 从上次位置开始轮询，找到第一�?available �?slot
        2. 检�?slot 的自定义速率限制
        3. 如果冷却中的 slot 已过冷却期，自动恢复
        4. 如果所�?slot 都在冷却或限制，等待最早恢复的那个

        Returns:
            TokenSlot: 选中的槽�?

        Raises:
            RuntimeError: 池中没有任何 slot
        """
        async with self._lock:
            if not self._slots:
                raise RuntimeError(
                    "[TokenPool] 没有可用的账号。请先运�?"
                    "`nanobot login --slot 1` 添加至少一个账号�?
                )

            slot_ids = sorted(self._slots.keys())
            n = len(slot_ids)

            # 轮询查找可用 slot
            for i in range(n):
                idx = (self._current_index + i) % n
                slot = self._slots[slot_ids[idx]]

                # 如果冷却期已过，恢复�?ACTIVE
                if slot.state == SlotState.COOLING and time.time() >= slot.cooling_until:
                    slot.state = SlotState.ACTIVE
                    slot.consecutive_errors = 0
                    logger.info(f"[TokenPool] Slot {slot.slot_id} 冷却结束，已恢复")

                if slot.is_available:
                    # 检查自定义速率限制
                    allowed, reason = slot.check_rate_limit()
                    if not allowed:
                        logger.debug(f"[TokenPool] Slot {slot.slot_id} 跳过: {reason}")
                        continue

                    slot.last_used_at = time.time()
                    slot.total_requests += 1
                    self._current_index = (idx + 1) % n
                    logger.debug(
                        f"[TokenPool] 选中 Slot {slot.slot_id} ({slot.label}) "
                        f"[请求#{slot.total_requests}]"
                    )
                    return slot

        # 所�?slot 都不可用 �?等待最早恢复的
        return await self._wait_for_recovery()

    def report_success(self, slot_id: int, tokens_used: int = 0):
        """报告请求成功，重置连续错误计数，记录 Token 使用"""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.consecutive_errors = 0
            if slot.state == SlotState.COOLING:
                slot.state = SlotState.ACTIVE
            # 记录 Token 使用
            if tokens_used > 0:
                slot.record_usage(tokens_used)

    def report_rate_limit(self, slot_id: int, retry_after: int | None = None):
        """
        报告 429 Rate Limit 错误，触发熔断冷�?

        Args:
            slot_id: 触发错误的槽�?ID
            retry_after: 服务器建议的重试等待时间（秒�?
        """
        if slot_id not in self._slots:
            return

        slot = self._slots[slot_id]
        slot.consecutive_errors += 1
        slot.total_429s += 1

        # 判断是否需要标记为 DEAD
        if slot.consecutive_errors >= self.DEAD_THRESHOLD:
            slot.state = SlotState.DEAD
            logger.error(
                f"[TokenPool] Slot {slot.slot_id} 连续 {slot.consecutive_errors} 次错误，"
                f"标记�?DEAD。需要重�?`nanobot login --slot {slot.slot_id}` 恢复�?
            )
            return

        # 计算冷却时间：指数退�?
        if retry_after and retry_after > 0:
            cooldown = min(retry_after, self.MAX_COOLDOWN_S)
        else:
            # 2^(errors-1) * BASE, 上限 MAX
            cooldown = min(
                self.BASE_COOLDOWN_S * (2 ** (slot.consecutive_errors - 1)),
                self.MAX_COOLDOWN_S,
            )

        slot.state = SlotState.COOLING
        slot.cooling_until = time.time() + cooldown

        # ⚠️ GitHub 对同一 IP 有全局速率限制
        # 当一个账号触�?429 时，其他账号（同 IP）也会被限制
        logger.warning(
            f"[TokenPool] Slot {slot.slot_id} 触发 429 (第{slot.consecutive_errors}�?�?
            f"冷却 {cooldown:.0f}s�?
            f"剩余可用 slot: {self.active_count}/{self.size}�?
            f"注意：GitHub 对同一 IP 有全局速率限制，其他账号也可能被拒绝�?
        )

    def report_auth_error(self, slot_id: int):
        """报告认证错误�?01/403），标记为需要刷新或重新登录"""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.state = SlotState.DEAD
            logger.error(
                f"[TokenPool] Slot {slot.slot_id} 认证失败，标记为 DEAD�?
                f"请运�?`nanobot login --slot {slot.slot_id}` 重新认证�?
            )

    def update_copilot_token(
        self, slot_id: int, copilot_token: str, expires_at: datetime
    ):
        """更新某个 slot �?Copilot Token（刷新后调用�?""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.copilot_token = copilot_token
            slot.expires_at = expires_at
            if slot.state == SlotState.EXPIRED:
                slot.state = SlotState.ACTIVE
            self._save_slot(slot)
            logger.info(f"[TokenPool] Slot {slot_id} Copilot Token 已刷新，有效期至 {expires_at}")

    def get_status(self) -> list[dict]:
        """获取所�?slot 的状态摘�?""
        result = []
        for slot in self.all_slots:
            remaining = ""
            if slot.state == SlotState.COOLING:
                secs = max(0, slot.cooling_until - time.time())
                remaining = f"{secs:.0f}s"

            # 获取使用统计
            usage = slot.get_usage_summary()

            result.append({
                "slot_id": slot.slot_id,
                "label": slot.label,
                "state": slot.state.value,
                "cooling_remaining": remaining,
                "total_requests": slot.total_requests,
                "total_429s": slot.total_429s,
                "token_expires": slot.expires_at.isoformat(),
                "limits": {
                    "max_tokens_per_day": slot.max_tokens_per_day or "无限�?,
                    "max_requests_per_day": slot.max_requests_per_day or "无限�?,
                    "max_requests_per_hour": slot.max_requests_per_hour or "无限�?,
                },
                "usage": usage,
            })
        return result

    # ========================================================================
    # 兼容旧接口：提供�?session 视图
    # ========================================================================

    def get_legacy_session(self):
        """
        兼容旧代码：返回第一个可�?slot 对应�?CopilotSession�?
        使现有的 provider.session 检查仍然有效�?
        """
        from solopreneur.providers.github_copilot import CopilotSession

        for slot in self.all_slots:
            if slot.state != SlotState.DEAD:
                return CopilotSession(
                    github_access_token=slot.github_access_token,
                    copilot_token=slot.copilot_token,
                    expires_at=slot.expires_at,
                )
        return None

    # ========================================================================
    # 内部方法
    # ========================================================================

    async def _wait_for_recovery(self) -> TokenSlot:
        """所�?slot 都在冷却时，等待最早恢复的"""
        cooldown_slots = [
            s for s in self._slots.values() if s.state == SlotState.COOLING
        ]

        if not cooldown_slots:
            # 所�?slot 都是 DEAD，无法恢�?
            raise RuntimeError(
                "[TokenPool] 所有账号均已失�?(DEAD)。请运行 "
                "`nanobot login --slot N` 重新认证�?
            )

        # 找到最早恢复的 slot
        earliest = min(cooldown_slots, key=lambda s: s.cooling_until)
        wait_time = max(0, earliest.cooling_until - time.time())

        logger.warning(
            f"[TokenPool] 全部 slot 冷却中，等待 {wait_time:.1f}s �?"
            f"Slot {earliest.slot_id} 将恢�?.."
        )

        await asyncio.sleep(wait_time + 0.5)  # 多等 0.5s 余量

        earliest.state = SlotState.ACTIVE
        earliest.consecutive_errors = 0
        earliest.last_used_at = time.time()
        earliest.total_requests += 1

        logger.info(f"[TokenPool] Slot {earliest.slot_id} 已恢复，继续执行")
        return earliest

    def _save_slot(self, slot: TokenSlot):
        """将单�?slot 持久化到文件"""
        slot_file = self._pool_dir / f"slot_{slot.slot_id}.json"
        try:
            data = {
                "slot_id": slot.slot_id,
                "github_access_token": _encrypt_token(slot.github_access_token),
                "copilot_token": _encrypt_token(slot.copilot_token),
                "expires_at": slot.expires_at.isoformat(),
                "label": slot.label,
                "total_requests": slot.total_requests,
                "total_429s": slot.total_429s,
                # Token 限制配置
                "max_tokens_per_day": slot.max_tokens_per_day,
                "max_requests_per_day": slot.max_requests_per_day,
                "max_requests_per_hour": slot.max_requests_per_hour,
                # 使用统计
                "tokens_used_today": slot.tokens_used_today,
                "requests_today": slot.requests_today,
                "requests_hour": slot.requests_hour,
                "last_reset_date": slot.last_reset_date,
                "last_reset_hour": slot.last_reset_hour,
                "tokens_used_history": slot.tokens_used_history,
                "_encrypted": CRYPTO_AVAILABLE,
            }
            with open(slot_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # 仅所有者可读写
            try:
                slot_file.chmod(0o600)
            except OSError:
                pass  # Windows 可能不支�?
            logger.debug(f"[TokenPool] Slot {slot.slot_id} 已保存到 {slot_file}")
        except Exception as e:
            logger.error(f"[TokenPool] 保存 Slot {slot.slot_id} 失败: {e}")

    def _load_all_slots(self):
        """从磁盘加载所�?slot 文件"""
        slot_files = sorted(self._pool_dir.glob("slot_*.json"))
        for sf in slot_files:
            try:
                with open(sf, "r", encoding="utf-8") as f:
                    data = json.load(f)

                is_encrypted = data.get("_encrypted", False)
                github_token = data["github_access_token"]
                copilot_token = data["copilot_token"]

                if is_encrypted:
                    github_token = _decrypt_token(github_token)
                    copilot_token = _decrypt_token(copilot_token)

                expires_at = datetime.fromisoformat(data["expires_at"])
                slot_id = data["slot_id"]

                # 判断初始状�?
                if datetime.now() + timedelta(minutes=5) >= expires_at:
                    state = SlotState.EXPIRED
                else:
                    state = SlotState.ACTIVE

                slot = TokenSlot(
                    slot_id=slot_id,
                    github_access_token=github_token,
                    copilot_token=copilot_token,
                    expires_at=expires_at,
                    state=state,
                    label=data.get("label", f"账号{slot_id}"),
                    total_requests=data.get("total_requests", 0),
                    total_429s=data.get("total_429s", 0),
                    # Token 限制配置
                    max_tokens_per_day=data.get("max_tokens_per_day", 0),
                    max_requests_per_day=data.get("max_requests_per_day", 0),
                    max_requests_per_hour=data.get("max_requests_per_hour", 0),
                    # 使用统计
                    tokens_used_today=data.get("tokens_used_today", 0),
                    requests_today=data.get("requests_today", 0),
                    requests_hour=data.get("requests_hour", 0),
                    last_reset_date=data.get("last_reset_date", ""),
                    last_reset_hour=data.get("last_reset_hour", -1),
                    tokens_used_history=data.get("tokens_used_history", []),
                )
                self._slots[slot_id] = slot
                logger.info(
                    f"[TokenPool] 已加�?Slot {slot_id} ({slot.label}), "
                    f"状�? {state.value}, 过期: {expires_at}"
                )
            except Exception as e:
                logger.error(f"[TokenPool] 加载 {sf.name} 失败: {e}")

        if self._slots:
            logger.info(
                f"[TokenPool] 池初始化完成: {len(self._slots)} 个账�? "
                f"{self.active_count} 个可�?
            )
        else:
            logger.info("[TokenPool] 池为空，请运�?`nanobot login --slot 1` 添加账号")

    # ========================================================================
    # 迁移辅助：从旧的�?token 文件迁移
    # ========================================================================

    def migrate_from_legacy(self, legacy_token_file: Path | None = None):
        """
        从旧的单文件 token 迁移�?slot 1
        如果 slot 1 已存在，不会覆盖�?
        """
        legacy = legacy_token_file or (Path.home() / ".nanobot" / ".copilot_token.json")
        if not legacy.exists():
            return False

        if 1 in self._slots:
            logger.debug("[TokenPool] Slot 1 已存在，跳过迁移")
            return False

        try:
            with open(legacy, "r", encoding="utf-8") as f:
                data = json.load(f)

            is_encrypted = data.get("_encrypted", False)
            github_token = data["github_access_token"]
            copilot_token = data["copilot_token"]

            if is_encrypted:
                github_token = _decrypt_token(github_token)
                copilot_token = _decrypt_token(copilot_token)

            expires_at = datetime.fromisoformat(data["expires_at"])

            self.add_slot(
                slot_id=1,
                github_access_token=github_token,
                copilot_token=copilot_token,
                expires_at=expires_at,
                label="主账�?迁移)",
            )
            logger.info("[TokenPool] 已从旧格式迁移到 Slot 1")
            return True
        except Exception as e:
            logger.error(f"[TokenPool] 迁移失败: {e}")
            return False
