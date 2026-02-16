"""
仪表盘统�?API 端点
提供全面的系统统计数�?"""
import platform
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel

from solopreneur.core.dependencies import get_component_manager
from solopreneur.config.loader import get_config_path
from solopreneur.utils.helpers import get_data_path

router = APIRouter()


class AgentStats(BaseModel):
    """Agent 统计"""
    status: str
    uptime_seconds: int
    uptime_formatted: str
    current_model: str
    total_messages: int
    current_task: Optional[str] = None


class ProjectStats(BaseModel):
    """项目统计"""
    total: int
    recent: List[Dict[str, Any]]


class AgentDistribution(BaseModel):
    """Agent 分布统计"""
    total: int
    presets: int
    custom: int
    by_domain: Dict[str, int]
    by_type: Dict[str, int]


class SkillStats(BaseModel):
    """技能统�?""
    total: int
    enabled: int
    list: List[Dict[str, Any]]


class TokenStats(BaseModel):
    """Token 使用统计"""
    total_used: int
    requests_today: int
    pool_size: int
    available_slots: int


class ActivityItem(BaseModel):
    """活动�?""
    time: str
    type: str  # task, message, error, etc.
    title: str
    description: Optional[str] = None
    status: Optional[str] = None


class RecentActivity(BaseModel):
    """最近活�?""
    tasks: List[ActivityItem]
    messages: List[ActivityItem]
    errors: List[ActivityItem]


class SystemInfo(BaseModel):
    """系统信息"""
    version: str
    python_version: str
    platform: str
    config_path: str
    workspace_path: str


class DashboardStats(BaseModel):
    """仪表盘统计响�?""
    agent: AgentStats
    projects: ProjectStats
    agents: AgentDistribution
    skills: SkillStats
    tokens: TokenStats
    activity: RecentActivity
    system: SystemInfo


def format_uptime(seconds: int) -> str:
    """格式化运行时�?""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if days > 0:
        parts.append(f"{days}�?)
    if hours > 0:
        parts.append(f"{hours}�?)
    if minutes > 0:
        parts.append(f"{minutes}�?)
    parts.append(f"{secs}�?)
    return " ".join(parts)


@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    获取仪表盘统计数�?    
    Returns:
        DashboardStats: 全面的系统统计数�?    """
    try:
        comp = get_component_manager()
        
        # === Agent 状�?===
        runtime_file = get_data_path() / "runtime.txt"
        uptime_seconds = 0
        if runtime_file.exists():
            try:
                start_time = float(runtime_file.read_text().strip())
                uptime_seconds = int(time.time() - start_time)
            except:
                pass
        
        # 获取当前模型
        current_model = "gpt-5-mini"
        try:
            from solopreneur.config.loader import load_config
            config = load_config()
            current_model = config.agents.defaults.model
            if "/" in current_model:
                current_model = current_model.split("/")[-1]
        except:
            pass
        
        # 获取消息数（�?token pool 或其他来源）
        total_messages = 0
        try:
            provider = comp.get_copilot_provider()
            if hasattr(provider, '_request_count'):
                total_messages = provider._request_count
        except:
            pass
        
        agent_stats = AgentStats(
            status="IDLE",
            uptime_seconds=uptime_seconds,
            uptime_formatted=format_uptime(uptime_seconds),
            current_model=current_model,
            total_messages=total_messages
        )
        
        # === 项目统计 ===
        projects_data = {"total": 0, "recent": []}
        try:
            from solopreneur.projects import ProjectManager
            pm = ProjectManager()
            projects = pm.list_projects()
            projects_data["total"] = len(projects)
            
            # 获取最近项目（按更新时间排序）
            recent_projects = sorted(
                [p.to_dict() for p in projects],
                key=lambda x: x.get("updated_at", "") or "",
                reverse=True
            )[:5]
            projects_data["recent"] = [
                {
                    "id": p["id"],
                    "name": p["name"],
                    "path": p["path"],
                    "type": p.get("type", "local"),
                    "updated_at": p.get("updated_at", "")
                }
                for p in recent_projects
            ]
        except Exception as e:
            logger.warning(f"获取项目统计失败: {e}")
        
        project_stats = ProjectStats(**projects_data)
        
        # === Agent 分布 ===
        agents_data = {"total": 0, "presets": 0, "custom": 0, "by_domain": {}, "by_type": {}}
        try:
            agent_manager = comp.get_agent_manager()
            agents = agent_manager.list_agents()
            agents_data["total"] = len(agents)
            
            for agent in agents:
                source = agent.metadata.get("source", "preset")
                if source == "preset":
                    agents_data["presets"] += 1
                else:
                    agents_data["custom"] += 1
                
                # 按领域统�?                domain = agent.metadata.get("domain", "general")
                agents_data["by_domain"][domain] = agents_data["by_domain"].get(domain, 0) + 1
                
                # 按类型统�?                agent_type = agent.type.value if hasattr(agent.type, "value") else str(agent.type)
                agents_data["by_type"][agent_type] = agents_data["by_type"].get(agent_type, 0) + 1
        except Exception as e:
            logger.warning(f"获取 Agent 统计失败: {e}")
        
        agent_dist = AgentDistribution(**agents_data)
        
        # === 技能统计（�?/api/config/skills 同源�?===
        skills_data = {"total": 0, "enabled": 0, "list": []}
        try:
            skills_loader = comp.get_agent_manager().skills
            discovered = skills_loader.list_skills(filter_unavailable=False)

            for s in discovered:
                name = s["name"]
                description = "技�?
                meta = skills_loader.get_skill_metadata(name) or {}
                if meta.get("description"):
                    description = meta["description"]

                skills_data["total"] += 1
                skills_data["enabled"] += 1
                skills_data["list"].append({
                    "name": name,
                    "description": description,
                    "enabled": True
                })
        except Exception as e:
            logger.warning(f"获取技能统计失�? {e}")
        
        skill_stats = SkillStats(**skills_data)
        
        # === Token 统计 ===
        tokens_data = {"total_used": 0, "requests_today": 0, "pool_size": 0, "available_slots": 0}
        try:
            provider = comp.get_copilot_provider()
            if hasattr(provider, 'token_pool'):
                pool = provider.token_pool
                tokens_data["pool_size"] = len(pool.slots) if hasattr(pool, 'slots') else 0
                tokens_data["available_slots"] = sum(1 for s in pool.slots if s.is_valid) if hasattr(pool, 'slots') else 0
            if hasattr(provider, '_total_tokens'):
                tokens_data["total_used"] = provider._total_tokens
            if hasattr(provider, '_request_count'):
                tokens_data["requests_today"] = provider._request_count

            # 优先使用 SQLite 聚合（更准确，跨进程/重启可持续）
            db_path = get_data_path() / "nanobot.db"
            if db_path.exists():
                with sqlite3.connect(str(db_path)) as conn:
                    row_all = conn.execute(
                        "SELECT COALESCE(SUM(total_tokens), 0), COUNT(*) FROM llm_usage"
                    ).fetchone()
                    row_today = conn.execute(
                        "SELECT COUNT(*) FROM llm_usage WHERE date(created_at) = date('now', 'localtime')"
                    ).fetchone()

                if row_all:
                    tokens_data["total_used"] = int(row_all[0] or 0)
                if row_today:
                    tokens_data["requests_today"] = int(row_today[0] or 0)
        except Exception as e:
            logger.warning(f"获取 Token 统计失败: {e}")
        
        token_stats = TokenStats(**tokens_data)
        
        # === 最近活�?===
        activity_data = {"tasks": [], "messages": [], "errors": []}
        
        # 尝试从工作流引擎获取最近任�?        try:
            workflow_engine = comp.get_workflow_engine()
            if hasattr(workflow_engine, 'get_recent_tasks'):
                recent_tasks = workflow_engine.get_recent_tasks(limit=5)
                for task in recent_tasks:
                    activity_data["tasks"].append(ActivityItem(
                        time=task.get("time", ""),
                        type="task",
                        title=task.get("title", ""),
                        description=task.get("description", ""),
                        status=task.get("status", "")
                    ))
        except:
            pass
        
        # 从日志获取最近活�?        try:
            log_file = get_data_path() / "logs" / "nanobot.log"
            if log_file.exists():
                lines = log_file.read_text(encoding='utf-8').split('\n')[-100:]
                for line in lines:
                    if "ERROR" in line:
                        activity_data["errors"].append(ActivityItem(
                            time=datetime.now().isoformat(),
                            type="error",
                            title=line[:100],
                            status="error"
                        ))
        except:
            pass
        
        recent_activity = RecentActivity(**activity_data)
        
        # === 系统信息 ===
        system_info = SystemInfo(
            version="1.0.0",  # 可以从包版本获取
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            platform=platform.platform(),
            config_path=str(get_config_path()),
            workspace_path=str(Path.cwd())
        )
        
        return DashboardStats(
            agent=agent_stats,
            projects=project_stats,
            agents=agent_dist,
            skills=skill_stats,
            tokens=token_stats,
            activity=recent_activity,
            system=system_info
        )
        
    except Exception as e:
        logger.error(f"获取仪表盘统计失�? {e}")
        raise


@router.get("/dashboard/health")
async def health_check():
    """
    健康检查端�?    
    Returns:
        系统健康状�?    """
    try:
        comp = get_component_manager()
        
        # 检查各个组�?        health = {
            "status": "healthy",
            "components": {
                "agent_loop": "unknown",
                "provider": "unknown",
                "token_pool": "unknown"
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 检�?provider
        try:
            provider = comp.get_copilot_provider()
            health["components"]["provider"] = "ok"
            
            if hasattr(provider, 'token_pool'):
                pool = provider.token_pool
                valid_count = sum(1 for s in pool.slots if s.is_valid) if hasattr(pool, 'slots') else 0
                health["components"]["token_pool"] = "ok" if valid_count > 0 else "degraded"
        except:
            health["components"]["provider"] = "error"
        
        # 检�?agent loop
        try:
            await comp.get_agent_loop()
            health["components"]["agent_loop"] = "ok"
        except:
            health["components"]["agent_loop"] = "not_started"
        
        # 计算整体状�?        if "error" in health["components"].values():
            health["status"] = "degraded"
        if health["components"]["provider"] == "error":
            health["status"] = "unhealthy"
        
        return health
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }
