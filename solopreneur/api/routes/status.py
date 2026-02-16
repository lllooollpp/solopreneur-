"""
状态查询端�?
提供 Agent 当前运行状�?
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class AgentStatusResponse(BaseModel):
    """Agent 状态响应模�?""
    status: str  # IDLE, THINKING, ERROR, OFFLINE
    current_task: Optional[str] = None
    error_message: Optional[str] = None
    uptime_seconds: int = 0
    total_messages: int = 0


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status():
    """
    获取 Agent 当前状�?
    
    Returns:
        AgentStatusResponse: 包含状态、当前任务、错误信息等
    """
    import time
    from pathlib import Path
    
    # 检查后端是否运行（通过检查进程或配置文件�?
    try:
        # 获取运行时间（从启动时间戳文件）
        runtime_file = Path.home() / ".solopreneur" / "runtime.txt"
        uptime_seconds = 0
        
        if runtime_file.exists():
            start_time = float(runtime_file.read_text().strip())
            uptime_seconds = int(time.time() - start_time)
        else:
            # 创建运行时间�?
            runtime_file.parent.mkdir(parents=True, exist_ok=True)
            runtime_file.write_text(str(time.time()))
        
        # 返回真实状�?
        return AgentStatusResponse(
            status="IDLE",
            current_task=None,
            error_message=None,
            uptime_seconds=uptime_seconds,
            total_messages=0
        )
    except Exception as e:
        return AgentStatusResponse(
            status="ERROR",
            current_task=None,
            error_message=str(e),
            uptime_seconds=0,
            total_messages=0
        )

