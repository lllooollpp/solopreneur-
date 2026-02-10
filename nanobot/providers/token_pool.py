"""
GitHub Copilot 多账号 Token 池管理器
支持多账号负载均衡、熔断冷却、自动恢复
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Optional
from loguru import logger

try:
    from nanobot.providers.github_copilot import (
        _encrypt_token, _decrypt_token, CRYPTO_AVAILABLE,
    )
except ImportError:
    CRYPTO_AVAILABLE = False
    _encrypt_token = _decrypt_token = lambda t: t


class SlotState(str, Enum):
    """Token 槽位状态"""
    ACTIVE = "active"        # 正常可用
    COOLING = "cooling"      # 触发 429，冷却中
    EXPIRED = "expired"      # Copilot Token 过期，需刷新
    DEAD = "dead"            # GitHub token 失效，需重新登录


@dataclass
class TokenSlot:
    """单个账号的 Token 槽位"""
    slot_id: int
    github_access_token: str
    copilot_token: str
    expires_at: datetime
    state: SlotState = SlotState.ACTIVE
    cooling_until: float = 0.0          # 冷却截止时间 (unix timestamp)
    consecutive_errors: int = 0          # 连续错误计数
    total_requests: int = 0              # 总请求计数
    total_429s: int = 0                  # 总 429 计数
    last_used_at: float = 0.0           # 上次使用时间
    label: str = ""                      # 可选标签（如 "账号A"）

    @property
    def is_available(self) -> bool:
        """当前是否可用于请求"""
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


class TokenPool:
    """
    多账号 Token 池管理器
    
    特性：
    - 轮询 (Round-Robin) 负载均衡
    - 熔断器 (Circuit Breaker)：429 → 自动冷却
    - 指数退避冷却时间：30s → 60s → 120s → 最大 300s
    - 自动 Token 刷新
    - 全部冷却时智能等待
    """

    # 冷却策略常量
    BASE_COOLDOWN_S = 30           # 基础冷却时间（秒）
    MAX_COOLDOWN_S = 300           # 最大冷却时间（秒）
    DEAD_THRESHOLD = 10            # 连续错误次数达到此值标记为 DEAD

    def __init__(self, pool_dir: Path | None = None):
        self._pool_dir = pool_dir or (Path.home() / ".nanobot" / "pool")
        self._pool_dir.mkdir(parents=True, exist_ok=True)
        self._slots: dict[int, TokenSlot] = {}
        self._current_index = 0  # 轮询指针
        self._lock = asyncio.Lock()
        
        # 启动时加载所有已保存的 slot
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
        """返回所有 slot（按 id 排序）"""
        return sorted(self._slots.values(), key=lambda s: s.slot_id)

    def add_slot(
        self,
        slot_id: int,
        github_access_token: str,
        copilot_token: str,
        expires_at: datetime,
        label: str = "",
    ) -> TokenSlot:
        """
        添加或更新一个 Token 槽位

        Args:
            slot_id: 槽位编号（1-based）
            github_access_token: GitHub OAuth Token
            copilot_token: Copilot API Token
            expires_at: Token 过期时间
            label: 可选的标签名

        Returns:
            创建/更新后的 TokenSlot
        """
        slot = TokenSlot(
            slot_id=slot_id,
            github_access_token=github_access_token,
            copilot_token=copilot_token,
            expires_at=expires_at,
            state=SlotState.ACTIVE,
            label=label or f"账号{slot_id}",
        )
        self._slots[slot_id] = slot
        self._save_slot(slot)
        logger.info(f"[TokenPool] Slot {slot_id} ({slot.label}) 已添加/更新")
        return slot

    def remove_slot(self, slot_id: int) -> bool:
        """移除一个 slot"""
        if slot_id in self._slots:
            del self._slots[slot_id]
            slot_file = self._pool_dir / f"slot_{slot_id}.json"
            if slot_file.exists():
                slot_file.unlink()
            logger.info(f"[TokenPool] Slot {slot_id} 已移除")
            return True
        return False

    async def acquire(self) -> TokenSlot:
        """
        获取一个可用的 Token 槽位（核心调度方法）

        策略：
        1. 从上次位置开始轮询，找到第一个 available 的 slot
        2. 如果冷却中的 slot 已过冷却期，自动恢复
        3. 如果所有 slot 都在冷却，等待最早恢复的那个

        Returns:
            TokenSlot: 选中的槽位
            
        Raises:
            RuntimeError: 池中没有任何 slot
        """
        async with self._lock:
            if not self._slots:
                raise RuntimeError(
                    "[TokenPool] 没有可用的账号。请先运行 "
                    "`nanobot login --slot 1` 添加至少一个账号。"
                )

            slot_ids = sorted(self._slots.keys())
            n = len(slot_ids)

            # 轮询查找可用 slot
            for i in range(n):
                idx = (self._current_index + i) % n
                slot = self._slots[slot_ids[idx]]

                # 如果冷却期已过，恢复为 ACTIVE
                if slot.state == SlotState.COOLING and time.time() >= slot.cooling_until:
                    slot.state = SlotState.ACTIVE
                    slot.consecutive_errors = 0
                    logger.info(f"[TokenPool] Slot {slot.slot_id} 冷却结束，已恢复")

                if slot.is_available:
                    slot.last_used_at = time.time()
                    slot.total_requests += 1
                    self._current_index = (idx + 1) % n
                    logger.debug(
                        f"[TokenPool] 选中 Slot {slot.slot_id} ({slot.label}) "
                        f"[请求#{slot.total_requests}]"
                    )
                    return slot

        # 所有 slot 都不可用 → 等待最早恢复的
        return await self._wait_for_recovery()

    def report_success(self, slot_id: int):
        """报告请求成功，重置连续错误计数"""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.consecutive_errors = 0
            if slot.state == SlotState.COOLING:
                slot.state = SlotState.ACTIVE

    def report_rate_limit(self, slot_id: int, retry_after: int | None = None):
        """
        报告 429 Rate Limit 错误，触发熔断冷却
        
        Args:
            slot_id: 触发错误的槽位 ID
            retry_after: 服务器建议的重试等待时间（秒）
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
                f"标记为 DEAD。需要重新 `nanobot login --slot {slot.slot_id}` 恢复。"
            )
            return

        # 计算冷却时间：指数退避
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

        logger.warning(
            f"[TokenPool] Slot {slot.slot_id} 触发 429 (第{slot.consecutive_errors}次)，"
            f"冷却 {cooldown:.0f}s，"
            f"剩余可用 slot: {self.active_count}/{self.size}"
        )

    def report_auth_error(self, slot_id: int):
        """报告认证错误（401/403），标记为需要刷新或重新登录"""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.state = SlotState.DEAD
            logger.error(
                f"[TokenPool] Slot {slot.slot_id} 认证失败，标记为 DEAD。"
                f"请运行 `nanobot login --slot {slot.slot_id}` 重新认证。"
            )

    def update_copilot_token(
        self, slot_id: int, copilot_token: str, expires_at: datetime
    ):
        """更新某个 slot 的 Copilot Token（刷新后调用）"""
        if slot_id in self._slots:
            slot = self._slots[slot_id]
            slot.copilot_token = copilot_token
            slot.expires_at = expires_at
            if slot.state == SlotState.EXPIRED:
                slot.state = SlotState.ACTIVE
            self._save_slot(slot)
            logger.info(f"[TokenPool] Slot {slot_id} Copilot Token 已刷新，有效期至 {expires_at}")

    def get_status(self) -> list[dict]:
        """获取所有 slot 的状态摘要"""
        result = []
        for slot in self.all_slots:
            remaining = ""
            if slot.state == SlotState.COOLING:
                secs = max(0, slot.cooling_until - time.time())
                remaining = f"{secs:.0f}s"

            result.append({
                "slot_id": slot.slot_id,
                "label": slot.label,
                "state": slot.state.value,
                "cooling_remaining": remaining,
                "total_requests": slot.total_requests,
                "total_429s": slot.total_429s,
                "token_expires": slot.expires_at.isoformat(),
            })
        return result

    # ========================================================================
    # 兼容旧接口：提供单 session 视图
    # ========================================================================

    def get_legacy_session(self):
        """
        兼容旧代码：返回第一个可用 slot 对应的 CopilotSession，
        使现有的 provider.session 检查仍然有效。
        """
        from nanobot.providers.github_copilot import CopilotSession

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
        """所有 slot 都在冷却时，等待最早恢复的"""
        cooldown_slots = [
            s for s in self._slots.values() if s.state == SlotState.COOLING
        ]

        if not cooldown_slots:
            # 所有 slot 都是 DEAD，无法恢复
            raise RuntimeError(
                "[TokenPool] 所有账号均已失效 (DEAD)。请运行 "
                "`nanobot login --slot N` 重新认证。"
            )

        # 找到最早恢复的 slot
        earliest = min(cooldown_slots, key=lambda s: s.cooling_until)
        wait_time = max(0, earliest.cooling_until - time.time())

        logger.warning(
            f"[TokenPool] 全部 slot 冷却中，等待 {wait_time:.1f}s 后 "
            f"Slot {earliest.slot_id} 将恢复..."
        )

        await asyncio.sleep(wait_time + 0.5)  # 多等 0.5s 余量

        earliest.state = SlotState.ACTIVE
        earliest.consecutive_errors = 0
        earliest.last_used_at = time.time()
        earliest.total_requests += 1

        logger.info(f"[TokenPool] Slot {earliest.slot_id} 已恢复，继续执行")
        return earliest

    def _save_slot(self, slot: TokenSlot):
        """将单个 slot 持久化到文件"""
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
                "_encrypted": CRYPTO_AVAILABLE,
            }
            with open(slot_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            # 仅所有者可读写
            try:
                slot_file.chmod(0o600)
            except OSError:
                pass  # Windows 可能不支持
            logger.debug(f"[TokenPool] Slot {slot.slot_id} 已保存到 {slot_file}")
        except Exception as e:
            logger.error(f"[TokenPool] 保存 Slot {slot.slot_id} 失败: {e}")

    def _load_all_slots(self):
        """从磁盘加载所有 slot 文件"""
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

                # 判断初始状态
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
                )
                self._slots[slot_id] = slot
                logger.info(
                    f"[TokenPool] 已加载 Slot {slot_id} ({slot.label}), "
                    f"状态: {state.value}, 过期: {expires_at}"
                )
            except Exception as e:
                logger.error(f"[TokenPool] 加载 {sf.name} 失败: {e}")

        if self._slots:
            logger.info(
                f"[TokenPool] 池初始化完成: {len(self._slots)} 个账号, "
                f"{self.active_count} 个可用"
            )
        else:
            logger.info("[TokenPool] 池为空，请运行 `nanobot login --slot 1` 添加账号")

    # ========================================================================
    # 迁移辅助：从旧的单 token 文件迁移
    # ========================================================================

    def migrate_from_legacy(self, legacy_token_file: Path | None = None):
        """
        从旧的单文件 token 迁移到 slot 1
        如果 slot 1 已存在，不会覆盖。
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
                label="主账号(迁移)",
            )
            logger.info("[TokenPool] 已从旧格式迁移到 Slot 1")
            return True
        except Exception as e:
            logger.error(f"[TokenPool] 迁移失败: {e}")
            return False
