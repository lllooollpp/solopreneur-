"""
Agent 管理 API 端点

管理可配置的 Agents（支持任意领域：软件工程、医疗、法律等）
"""
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field
from typing import Dict, List, Any
from loguru import logger
from pathlib import Path

from nanobot.config.loader import load_config
from nanobot.agent.definitions.manager import AgentManager
from nanobot.agent.definitions.definition import AgentDefinition, AgentType

router = APIRouter()


class AgentItem(BaseModel):
    """Agent 列表项"""
    name: str
    title: str
    emoji: str
    description: str
    type: str
    domain: str
    source: str  # preset or custom
    metadata: Dict[str, Any]


class AgentDetail(AgentItem):
    """Agent 详情"""
    system_prompt: str
    skills: List[str]
    tools: List[str] | None
    max_iterations: int
    temperature: float | None
    output_format: str


class AgentsResponse(BaseModel):
    """Agent 列表响应"""
    agents: List[AgentItem]


class AgentCreateRequest(BaseModel):
    """创建 Agent 请求"""
    name: str = Field(..., pattern=r"^[a-zA-Z0-9_\-]+$", max_length=50)
    title: str = Field(..., max_length=100)
    emoji: str = Field(default="🤖", max_length=10)
    description: str = Field(default="", max_length=500)
    system_prompt: str = Field(..., min_length=10)
    type: str = Field(default="subagent")
    skills: List[str] = Field(default_factory=list)
    tools: List[str] | None = Field(default=None)
    max_iterations: int = Field(default=15, ge=1, le=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    output_format: str = Field(default="")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentUpdateRequest(BaseModel):
    """更新 Agent 请求"""
    title: str | None = Field(default=None, max_length=100)
    emoji: str | None = Field(default=None, max_length=10)
    description: str | None = Field(default=None, max_length=500)
    system_prompt: str | None = Field(default=None, min_length=10)
    skills: List[str] | None = None
    tools: List[str] | None = None
    max_iterations: int | None = Field(default=None, ge=1, le=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    output_format: str | None = None
    metadata: Dict[str, Any] | None = None


def _get_agent_manager() -> AgentManager:
    """获取 AgentManager 实例"""
    config = load_config()
    return AgentManager(workspace=config.workspace_path)


@router.get("/agents", response_model=AgentsResponse)
async def get_agents(
    domain: str | None = None,
    source: str | None = None,
):
    """
    获取所有可用 Agent 列表
    
    Args:
        domain: 按领域过滤 (software, medical, legal, general)
        source: 按来源过滤 (preset, custom)
    
    Returns:
        AgentsResponse: Agent 列表
    """
    try:
        manager = _get_agent_manager()
        agents = manager.list_agents()
        
        # 过滤
        if domain:
            agents = [a for a in agents if a.metadata.get("domain") == domain]
        if source:
            agents = [a for a in agents if a.metadata.get("source") == source]
        
        return AgentsResponse(agents=[
            AgentItem(
                name=a.name,
                title=a.title,
                emoji=a.emoji,
                description=a.description,
                type=a.type.value,
                domain=a.metadata.get("domain", "general"),
                source=a.metadata.get("source", "preset"),
                metadata=a.metadata,
            )
            for a in agents
        ])
        
    except Exception as e:
        logger.error(f"获取 Agent 列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agents/{agent_name}", response_model=AgentDetail)
async def get_agent(
    agent_name: str = PathParam(..., description="Agent 名称")
):
    """
    获取 Agent 详情
    
    Args:
        agent_name: Agent 名称
    
    Returns:
        AgentDetail: Agent 详细信息
    """
    try:
        manager = _get_agent_manager()
        agent = manager.get_agent(agent_name)
        
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' 不存在")
        
        return AgentDetail(
            name=agent.name,
            title=agent.title,
            emoji=agent.emoji,
            description=agent.description,
            type=agent.type.value,
            domain=agent.metadata.get("domain", "general"),
            source=agent.metadata.get("source", "preset"),
            metadata=agent.metadata,
            system_prompt=agent.system_prompt,
            skills=agent.skills,
            tools=agent.tools,
            max_iterations=agent.max_iterations,
            temperature=agent.temperature,
            output_format=agent.output_format,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 Agent 详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents")
async def create_agent(request: AgentCreateRequest):
    """
    创建新的自定义 Agent
    
    Args:
        request: Agent 创建请求
    
    Returns:
        创建结果
    """
    try:
        manager = _get_agent_manager()
        
        # 检查是否已存在
        if manager.get_agent(request.name):
            raise HTTPException(
                status_code=400, 
                detail=f"Agent '{request.name}' 已存在"
            )
        
        # 创建 Agent 定义
        agent = AgentDefinition(
            name=request.name,
            title=request.title,
            emoji=request.emoji,
            description=request.description,
            system_prompt=request.system_prompt,
            type=AgentType(request.type),
            skills=request.skills,
            tools=request.tools,
            max_iterations=request.max_iterations,
            temperature=request.temperature,
            output_format=request.output_format,
            metadata={**request.metadata, "source": "custom", "domain": "custom"},
        )
        
        # 保存
        if manager.create_agent(agent):
            return {
                "success": True,
                "message": f"Agent '{request.name}' 创建成功",
                "agent": request.name,
            }
        else:
            raise HTTPException(status_code=500, detail="创建 Agent 失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"创建 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/agents/{agent_name}")
async def update_agent(
    agent_name: str = PathParam(..., description="Agent 名称"),
    request: AgentUpdateRequest = None
):
    """
    更新自定义 Agent
    
    注意：只能更新自定义 Agent，预设 Agent 不可修改
    
    Args:
        agent_name: Agent 名称
        request: 更新请求
    
    Returns:
        更新结果
    """
    try:
        manager = _get_agent_manager()
        
        existing = manager.get_agent(agent_name)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' 不存在")
        
        # 检查是否为预设
        if existing.metadata.get("source") == "preset":
            raise HTTPException(
                status_code=400, 
                detail="预设 Agent 不可修改，请创建自定义 Agent"
            )
        
        # 构建更新后的 Agent
        update_data = existing.model_dump()
        if request.title is not None:
            update_data["title"] = request.title
        if request.emoji is not None:
            update_data["emoji"] = request.emoji
        if request.description is not None:
            update_data["description"] = request.description
        if request.system_prompt is not None:
            update_data["system_prompt"] = request.system_prompt
        if request.skills is not None:
            update_data["skills"] = request.skills
        if request.tools is not None:
            update_data["tools"] = request.tools
        if request.max_iterations is not None:
            update_data["max_iterations"] = request.max_iterations
        if request.temperature is not None:
            update_data["temperature"] = request.temperature
        if request.output_format is not None:
            update_data["output_format"] = request.output_format
        if request.metadata is not None:
            update_data["metadata"] = {**existing.metadata, **request.metadata}
        
        updated_agent = AgentDefinition(**update_data)
        
        # 删除旧版本，创建新版本
        manager.delete_agent(agent_name)
        if manager.create_agent(updated_agent):
            return {
                "success": True,
                "message": f"Agent '{agent_name}' 更新成功",
            }
        else:
            raise HTTPException(status_code=500, detail="更新 Agent 失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/agents/{agent_name}")
async def delete_agent(
    agent_name: str = PathParam(..., description="Agent 名称")
):
    """
    删除自定义 Agent
    
    注意：只能删除自定义 Agent，预设 Agent 不可删除
    
    Args:
        agent_name: Agent 名称
    
    Returns:
        删除结果
    """
    try:
        manager = _get_agent_manager()
        
        existing = manager.get_agent(agent_name)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' 不存在")
        
        # 检查是否为预设
        if existing.metadata.get("source") == "preset":
            raise HTTPException(
                status_code=400, 
                detail="预设 Agent 不可删除"
            )
        
        if manager.delete_agent(agent_name):
            return {
                "success": True,
                "message": f"Agent '{agent_name}' 已删除",
            }
        else:
            raise HTTPException(status_code=500, detail="删除 Agent 失败")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agents/{agent_name}/reload")
async def reload_agents():
    """
    重新加载所有 Agent 配置
    
    用于开发时热重载配置
    
    Returns:
        重载结果
    """
    try:
        manager = _get_agent_manager()
        manager.reload()
        
        count = len(manager.list_agents())
        return {
            "success": True,
            "message": f"已重载 {count} 个 Agent",
            "count": count,
        }
        
    except Exception as e:
        logger.error(f"重载 Agent 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
