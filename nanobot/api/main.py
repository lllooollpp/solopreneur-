"""
Nanobot API 入口
FastAPI 应用，为前端提供 REST API 和 WebSocket 服务
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn
import sys
import os
from loguru import logger
from datetime import datetime

from nanobot.api.routes import status, wecom, auth, agent, chat, skills, agents, projects, dashboard, providers, metrics, harness
from nanobot.api.websocket import router as ws_router
from nanobot.api.middleware import RateLimitMiddleware


# 应用启动时间
_app_start_time = datetime.now()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    # 启动时
    logger.info("Nanobot API starting up...")

    yield

    # 关闭时
    logger.info("Nanobot API shutting down...")

    # 使用组件管理器清理所有资源
    from nanobot.core.dependencies import get_component_manager
    try:
        manager = get_component_manager()
        await manager.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

# 配置 loguru 日志输出
logger.remove()
logger.add(
    sys.stderr,
    level="DEBUG",  # 使用 DEBUG 级别以便调试
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# 创建 FastAPI 应用
app = FastAPI(
    title="Nanobot API",
    description="Nanobot 前端管理界面后端 API",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 中间件配置
# 从环境变量读取允许的来源（生产环境应配置）
# 默认允许所有来源 (开发环境)，生产环境应配置具体域名
default_origins = os.getenv("NANOBOT_CORS_ORIGINS", "*")
allowed_origins = ["*"] if default_origins == "*" else default_origins.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 速率限制中间件
# 从环境变量读取速率限制（默认60次/分钟）
rate_limit = int(os.getenv("NANOBOT_RATE_LIMIT", "60"))
app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)

# 注册路由
app.include_router(status.router, prefix="/api", tags=["status"])
app.include_router(wecom.router, prefix="/api", tags=["wecom"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(providers.router, prefix="/api", tags=["providers"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(projects.router, prefix="/api/v1", tags=["projects"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(metrics.router, prefix="/api/v1", tags=["metrics"])
app.include_router(harness.router, prefix="/api/v1", tags=["harness"])
app.include_router(ws_router, tags=["websocket"])


@app.get("/")
async def root():
    """根路径"""
    return {"message": "Nanobot API 正在运行", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """健康检查端点"""
    uptime = (datetime.now() - _app_start_time).total_seconds()
    
    # 检查GitHub Copilot认证状态
    from nanobot.api.routes.auth import get_copilot_provider
    copilot_authenticated = False
    try:
        provider = get_copilot_provider()
        copilot_authenticated = provider.session is not None
    except Exception:
        pass
    
    return {
        "status": "healthy",
        "uptime_seconds": uptime,
        "version": "0.1.0",
        "copilot_authenticated": copilot_authenticated
    }


def start_api_server(host: str = "0.0.0.0", port: int = 8000):
    """启动 API 服务器"""
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_api_server()
