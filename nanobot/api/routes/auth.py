"""
GitHub Copilot 认证端点
处理 OAuth 设备流认证 + 多账号 Token 池管理
"""
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel
from loguru import logger
from typing import Optional

from nanobot.providers.github_copilot import GitHubCopilotProvider

router = APIRouter()


def get_copilot_provider() -> GitHubCopilotProvider:
    """
    获取或创建 Copilot Provider 实例

    使用组件管理器统一管理单例
    """
    from nanobot.core.dependencies import get_component_manager
    manager = get_component_manager()
    return manager.get_copilot_provider()


# ========================================================================
# 模型 API
# ========================================================================

@router.get("/auth/models")
async def get_models():
    """获取可用的模型列表"""
    try:
        from nanobot.core.dependencies import get_component_manager
        from nanobot.providers.factory import create_llm_provider

        manager = get_component_manager()
        config = manager.get_config()

        # 仅在开启 copilot_priority 时优先使用 Copilot
        copilot_priority = getattr(config.providers, "copilot_priority", False)
        copilot_provider = manager.get_copilot_provider()
        if copilot_priority and copilot_provider.session:
            models = await copilot_provider.get_available_models()
            return {
                "models": models,
                "authenticated": True,
                "provider": "copilot"
            }

        # 否则检查其他 Provider
        llm_provider = create_llm_provider(config, default_model=config.agents.defaults.model)

        if llm_provider:
            # 根据不同 Provider 返回对应模型列表
            providers_config = config.providers

            # 检测当前使用的 Provider
            if providers_config.vllm.api_base:
                # 当配置了本地 vLLM 接口时，优先返回 local 标识和默认模型（从 config.agents.defaults.model 中读取）
                default_model = getattr(config.agents.defaults, 'model', None)
                return {
                    "models": ["llama-3-8b", "llama-3-70b", "qwen-7b", "qwen-14b", "yi-34b", "your-model-name"],
                    "default_model": default_model,
                    "local": True,
                    "authenticated": True,
                    "provider": "vllm",
                    "note": "本地 vLLM/OpenAI 兼容接口，请根据实际部署的模型填写模型名称"
                }
            elif providers_config.zhipu.api_key:
                return {
                    "models": ["glm-4", "glm-4-plus", "glm-4-flash", "glm-3-turbo"],
                    "authenticated": True,
                    "provider": "zhipu"
                }
            elif providers_config.openrouter.api_key:
                return {
                    "models": ["anthropic/claude-3.5-sonnet", "openai/gpt-4o", "google/gemini-pro-1.5", "meta-llama/llama-3.1-70b-instruct"],
                    "authenticated": True,
                    "provider": "openrouter"
                }
            elif providers_config.anthropic.api_key:
                return {
                    "models": ["claude-3-5-sonnet", "claude-3-5-haiku", "claude-3-opus"],
                    "authenticated": True,
                    "provider": "anthropic"
                }
            elif providers_config.openai.api_key:
                return {
                    "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
                    "authenticated": True,
                    "provider": "openai"
                }
            elif providers_config.groq.api_key:
                return {
                    "models": ["llama-3.1-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"],
                    "authenticated": True,
                    "provider": "groq"
                }
            elif providers_config.gemini.api_key:
                return {
                    "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"],
                    "authenticated": True,
                    "provider": "gemini"
                }

        # 没有配置任何 Provider，返回默认列表
        return {
            "models": ["gpt-5-mini", "gpt-4o", "gpt-4o-mini", "claude-sonnet-4"],
            "authenticated": False,
            "provider": "none",
            "note": "未配置任何 LLM Provider，请在配置管理页面添加"
        }
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================================================
# Pydantic 模型
# ========================================================================

class DeviceFlowStartResponse(BaseModel):
    """设备流启动响应"""
    device_code: str
    user_code: str
    verification_uri: str
    expires_in: int
    interval: int


class TokenPollRequest(BaseModel):
    """Token 轮询请求"""
    device_code: str
    slot_id: int = 0  # 0 = 自动分配下一个可用 slot


class TokenResponse(BaseModel):
    """Token 响应"""
    github_token: str
    copilot_token: str
    expires_at: str
    slot_id: int = 1


class PoolSlotInfo(BaseModel):
    """池槽位信息"""
    slot_id: int
    label: str
    state: str
    cooling_remaining: str
    total_requests: int
    total_429s: int
    token_expires: str
    limits: dict = {}     # Token 限制配置
    usage: dict = {}      # 当前使用统计


class PoolStatusResponse(BaseModel):
    """池状态响应"""
    authenticated: bool
    slots: list[PoolSlotInfo]
    active_count: int
    total_count: int


class AddSlotRequest(BaseModel):
    """添加槽位请求"""
    label: str = ""


class SlotLimitRequest(BaseModel):
    """账号 Token 限制配置请求"""
    max_tokens_per_day: int = 0      # 每日最大 Token 限制（0=无限制）
    max_requests_per_day: int = 0     # 每日最大请求次数（0=无限制）
    max_requests_per_hour: int = 0    # 每小时最大请求次数（0=无限制）


# ========================================================================
# 旧接口 (保持兼容)
# ========================================================================

@router.post("/auth/github/device", response_model=DeviceFlowStartResponse)
async def start_github_device_flow():
    """启动 GitHub Copilot OAuth 设备流（兼容旧接口）"""
    logger.info("Starting GitHub Copilot device flow authentication")
    
    try:
        provider = get_copilot_provider()
        device_flow = await provider.start_device_flow()
        
        return DeviceFlowStartResponse(
            device_code=device_flow.device_code,
            user_code=device_flow.user_code,
            verification_uri=device_flow.verification_uri,
            expires_in=device_flow.expires_in,
            interval=device_flow.interval
        )
    except Exception as e:
        logger.error(f"启动设备流失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/github/token", response_model=TokenResponse)
async def poll_github_token(request: TokenPollRequest):
    """
    轮询 GitHub Token（支持指定 slot）

    - slot_id=0 或不传：自动分配下一个可用编号
    - slot_id=N：写入指定 slot
    """
    logger.info(f"Polling for GitHub Token (target slot: {request.slot_id})")
    
    try:
        provider = get_copilot_provider()
        
        # 非阻塞轮询一次
        response = await provider._http_client.post(
            provider.TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": provider.CLIENT_ID,
                "device_code": request.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            }
        )
        
        data = response.json()
        
        if "access_token" in data:
            # 获取成功，立即获取 Copilot Token
            github_token = data["access_token"]
            copilot_token, expires_at = await provider.get_copilot_token(github_token)
            
            # 确定目标 slot_id
            slot_id = request.slot_id
            if slot_id <= 0:
                # 自动分配：取当前最大 slot_id + 1
                existing_ids = [s.slot_id for s in provider.pool.all_slots]
                slot_id = max(existing_ids, default=0) + 1
            
            # 生成标签
            label = f"账号{slot_id}"
            
            provider.pool.add_slot(
                slot_id=slot_id,
                github_access_token=github_token,
                copilot_token=copilot_token,
                expires_at=expires_at,
                label=label,
            )
            logger.info(f"Session saved to TokenPool (slot {slot_id})")
            
            return TokenResponse(
                github_token=github_token,
                copilot_token=copilot_token,
                expires_at=expires_at.isoformat(),
                slot_id=slot_id,
            )
        
        error = data.get("error")
        if error == "authorization_pending":
            raise HTTPException(status_code=202, detail="授权待处理")
        elif error == "slow_down":
            raise HTTPException(status_code=429, detail="请求过快")
        elif error in ["expired_token", "access_denied"]:
            raise HTTPException(status_code=403, detail=f"授权失败: {error}")
        else:
            raise HTTPException(status_code=500, detail=f"未知错误: {error}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"轮询 Token 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/github/status")
async def get_auth_status():
    """获取当前认证状态（含 Token 池信息）"""
    provider = get_copilot_provider()
    pool = provider.pool
    
    if pool.size == 0:
        return {
            "authenticated": False,
            "expires_at": None,
            "pool": [],
            "active_count": 0,
            "total_count": 0,
        }
    
    return {
        "authenticated": True,
        "expires_at": pool.all_slots[0].expires_at.isoformat() if pool.all_slots else None,
        "pool": pool.get_status(),
        "active_count": pool.active_count,
        "total_count": pool.size,
    }


@router.post("/auth/github/logout")
async def logout():
    """退出登录，清除所有 slot"""
    logger.info("User logged out from GitHub Copilot")
    
    provider = get_copilot_provider()
    for slot in list(provider.pool.all_slots):
        provider.pool.remove_slot(slot.slot_id)
    
    logger.info("All slots cleared from TokenPool")
    return {"success": True, "message": "已退出登录，所有账号已清除"}


# ========================================================================
# 多账号 Token 池管理 API
# ========================================================================

@router.get("/auth/pool/status")
async def get_pool_status():
    """获取 Token 池详细状态"""
    provider = get_copilot_provider()
    pool = provider.pool
    
    slots = pool.get_status()
    return {
        "authenticated": pool.size > 0,
        "slots": slots,
        "active_count": pool.active_count,
        "total_count": pool.size,
    }


@router.post("/auth/pool/login", response_model=DeviceFlowStartResponse)
async def pool_start_login(request: AddSlotRequest = AddSlotRequest()):
    """
    为 Token 池启动新的设备流登录
    
    返回 device_code 等信息，前端需要展示验证码给用户，
    然后调用 /auth/pool/poll 轮询结果
    """
    logger.info(f"Starting pool login (label: {request.label or 'auto'})")
    
    try:
        provider = get_copilot_provider()
        device_flow = await provider.start_device_flow()
        
        return DeviceFlowStartResponse(
            device_code=device_flow.device_code,
            user_code=device_flow.user_code,
            verification_uri=device_flow.verification_uri,
            expires_in=device_flow.expires_in,
            interval=device_flow.interval
        )
    except Exception as e:
        logger.error(f"Pool login 启动失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PoolPollRequest(BaseModel):
    """池轮询请求"""
    device_code: str
    slot_id: int = 0  # 0 = 自动分配
    label: str = ""


@router.post("/auth/pool/poll")
async def pool_poll_token(request: PoolPollRequest):
    """
    轮询 Token 池登录结果
    
    - slot_id=0：自动分配下一个编号
    - label：自定义标签
    """
    try:
        provider = get_copilot_provider()
        
        response = await provider._http_client.post(
            provider.TOKEN_URL,
            headers={"Accept": "application/json"},
            data={
                "client_id": provider.CLIENT_ID,
                "device_code": request.device_code,
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code"
            }
        )
        
        data = response.json()
        
        if "access_token" in data:
            github_token = data["access_token"]
            copilot_token, expires_at = await provider.get_copilot_token(github_token)
            
            # 确定 slot_id
            slot_id = request.slot_id
            if slot_id <= 0:
                existing_ids = [s.slot_id for s in provider.pool.all_slots]
                slot_id = max(existing_ids, default=0) + 1
            
            label = request.label or f"账号{slot_id}"
            
            provider.pool.add_slot(
                slot_id=slot_id,
                github_access_token=github_token,
                copilot_token=copilot_token,
                expires_at=expires_at,
                label=label,
            )
            
            logger.info(f"Pool login successful: slot {slot_id} ({label})")
            
            return {
                "status": "success",
                "slot_id": slot_id,
                "label": label,
                "expires_at": expires_at.isoformat(),
            }
        
        error = data.get("error")
        if error == "authorization_pending":
            return {"status": "pending"}
        elif error == "slow_down":
            return {"status": "slow_down"}
        elif error in ["expired_token", "access_denied"]:
            return {"status": "error", "error": f"授权失败: {error}"}
        else:
            return {"status": "error", "error": f"未知错误: {error}"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pool poll 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auth/pool/{slot_id}")
async def pool_remove_slot(slot_id: int = PathParam(..., ge=1)):
    """移除指定 slot"""
    provider = get_copilot_provider()
    
    if provider.pool.remove_slot(slot_id):
        return {"success": True, "message": f"Slot {slot_id} 已移除"}
    else:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")


@router.post("/auth/pool/{slot_id}/refresh")
async def pool_refresh_slot(slot_id: int = PathParam(..., ge=1)):
    """刷新指定 slot 的 Copilot Token"""
    provider = get_copilot_provider()
    pool = provider.pool
    
    # 找到目标 slot
    target = None
    for slot in pool.all_slots:
        if slot.slot_id == slot_id:
            target = slot
            break
    
    if target is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")
    
    try:
        await provider.refresh_slot_token(target)
        # 重新获取更新后的状态
        updated_status = pool.get_status()
        slot_info = next((s for s in updated_status if s["slot_id"] == slot_id), None)
        return {
            "success": True,
            "message": f"Slot {slot_id} Token 已刷新",
            "slot": slot_info,
        }
    except Exception as e:
        logger.error(f"Slot {slot_id} 刷新失败: {e}")
        raise HTTPException(status_code=500, detail=f"刷新失败: {e}")


@router.put("/auth/pool/{slot_id}/label")
async def pool_update_label(slot_id: int = PathParam(..., ge=1), request: AddSlotRequest = AddSlotRequest()):
    """更新指定 slot 的标签"""
    provider = get_copilot_provider()
    pool = provider.pool

    target = None
    for slot in pool.all_slots:
        if slot.slot_id == slot_id:
            target = slot
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")

    target.label = request.label or f"账号{slot_id}"
    pool._save_slot(target)

    return {"success": True, "label": target.label}


@router.put("/auth/pool/{slot_id}/limits")
async def pool_set_limits(
    slot_id: int = PathParam(..., ge=1),
    request: SlotLimitRequest = SlotLimitRequest()
):
    """
    设置指定账号的 Token 使用限制

    Args:
        slot_id: 账号槽位 ID
        max_tokens_per_day: 每日最大 Token 数（0=无限制）
        max_requests_per_day: 每日最大请求次数（0=无限制）
        max_requests_per_hour: 每小时最大请求次数（0=无限制）
    """
    provider = get_copilot_provider()
    pool = provider.pool

    # 找到目标 slot
    target = None
    for slot in pool.all_slots:
        if slot.slot_id == slot_id:
            target = slot
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")

    # 更新限制配置
    target.max_tokens_per_day = request.max_tokens_per_day
    target.max_requests_per_day = request.max_requests_per_day
    target.max_requests_per_hour = request.max_requests_per_hour
    pool._save_slot(target)

    logger.info(
        f"Slot {slot_id} 限制已更新: "
        f"tokens/day={request.max_tokens_per_day or '无'}, "
        f"req/day={request.max_requests_per_day or '无'}, "
        f"req/hour={request.max_requests_per_hour or '无'}"
    )

    return {
        "success": True,
        "message": f"Slot {slot_id} 的 Token 限制已更新",
        "limits": {
            "max_tokens_per_day": request.max_tokens_per_day or "无限制",
            "max_requests_per_day": request.max_requests_per_day or "无限制",
            "max_requests_per_hour": request.max_requests_per_hour or "无限制",
        }
    }


@router.get("/auth/pool/{slot_id}/usage")
async def pool_get_usage(slot_id: int = PathParam(..., ge=1)):
    """获取指定账号的 Token 使用统计"""
    provider = get_copilot_provider()
    pool = provider.pool

    # 找到目标 slot
    target = None
    for slot in pool.all_slots:
        if slot.slot_id == slot_id:
            target = slot
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")

    usage = target.get_usage_summary()

    return {
        "slot_id": slot_id,
        "label": target.label,
        "state": target.state.value,
        "usage": usage,
    }


@router.post("/auth/pool/{slot_id}/reset-usage")
async def pool_reset_usage(slot_id: int = PathParam(..., ge=1)):
    """重置指定账号的使用统计"""
    provider = get_copilot_provider()
    pool = provider.pool

    # 找到目标 slot
    target = None
    for slot in pool.all_slots:
        if slot.slot_id == slot_id:
            target = slot
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Slot {slot_id} 不存在")

    # 重置计数器
    target.tokens_used_today = 0
    target.requests_today = 0
    target.requests_hour = 0
    pool._save_slot(target)

    logger.info(f"Slot {slot_id} 使用统计已重置")

    return {
        "success": True,
        "message": f"Slot {slot_id} 的使用统计已重置"
    }
