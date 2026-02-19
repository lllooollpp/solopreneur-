"""
技能配置 API 端点
管理技能的启用状态和变量
"""
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List
from loguru import logger

router = APIRouter()


class SkillItem(BaseModel):
    """技能项模型"""
    name: str = Field(..., pattern=r"^[a-zA-Z0-9\-_]+$", max_length=100)
    source: str = Field(..., pattern=r"^(workspace|managed|bundled)$")
    enabled: bool
    description: str = Field(..., max_length=500)
    variables: Dict[str, str] = Field(default_factory=dict)
    overridden: bool
    
    @field_validator('variables')
    @classmethod
    def validate_variables(cls, v: Dict[str, str]) -> Dict[str, str]:
        """验证变量字典"""
        # 限制变量数量
        if len(v) > 50:
            raise ValueError("技能变量数量不能超过50个")
        
        # 验证每个键值对
        for key, value in v.items():
            if len(key) > 100:
                raise ValueError(f"变量名过长: {key}")
            if len(value) > 10000:
                raise ValueError(f"变量值过长: {key}")
        
        return v


class SkillsResponse(BaseModel):
    """技能列表响应"""
    skills: List[SkillItem]


class SkillUpdateRequest(BaseModel):
    """技能更新请求"""
    enabled: bool


class SkillCreateRequest(BaseModel):
    """技能创建请求"""
    name: str = Field(..., pattern=r"^[a-zA-Z0-9\-_]+$", max_length=100, description="技能名称")
    description: str = Field(..., min_length=1, max_length=500, description="技能描述")
    content: str = Field(..., min_length=1, max_length=500_000, description="SKILL.md 正文内容")


class SkillContentUpdateRequest(BaseModel):
    """技能内容更新请求"""
    content: str = Field(..., min_length=1, max_length=500_000, description="完整的 SKILL.md 内容")


@router.get("/config/skills", response_model=SkillsResponse)
async def get_skills():
    """
    获取所有可用技能列表
    
    Returns:
        SkillsResponse: 包含所有技能的列表
    """
    logger.info("获取技能列表")
    
    try:
        # 与 AgentManager 使用同一份 workspace 路径与 SkillsLoader，避免“页面与运行时路径不一致”
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        agent_manager = manager.get_agent_manager()
        skills_loader = agent_manager.skills

        discovered = skills_loader.list_skills(filter_unavailable=False)
        skills: List[SkillItem] = []

        for skill in discovered:
            name = skill["name"]
            source = skill.get("source", "builtin")
            source_mapped = "bundled" if source == "builtin" else source

            # 优先从 frontmatter description 获取
            description = "技能"
            meta = skills_loader.get_skill_metadata(name) or {}
            if meta.get("description"):
                description = meta["description"]
            else:
                # 回退：读取标题行
                try:
                    content = skills_loader.load_skill(name) or ""
                    first_line = content.split("\n", 1)[0].strip()
                    if first_line.startswith("#"):
                        description = first_line.lstrip("#").strip()
                except Exception:
                    pass

            skills.append(SkillItem(
                name=name,
                source=source_mapped,
                enabled=True,
                description=description,
                variables={},
                overridden=(source_mapped == "workspace"),
            ))

        logger.info(
            f"技能列表已加载: total={len(skills)}, workspace={sum(1 for s in skills if s.source == 'workspace')}, bundled={sum(1 for s in skills if s.source == 'bundled')}"
        )
        return SkillsResponse(skills=skills)
        
    except Exception as e:
        logger.error(f"获取技能列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/skills/{skill_name}")
async def update_skill(
    skill_name: str = PathParam(
        ...,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        max_length=100,
        description="技能名称，只允许字母数字-_"
    ),
    request: SkillUpdateRequest = None
):
    """
    更新技能配置
    
    Args:
        skill_name: 技能名称
        request: 更新请求
        
    Returns:
        更新结果
    """
    logger.info(f"更新技能配置: {skill_name}, enabled={request.enabled}")
    
    try:
        # 未来扩展: 持久化技能配置到配置文件
        # 当前简单返回成功状态
        return {
            "success": True,
            "message": f"技能 {skill_name} 已{'启用' if request.enabled else '禁用'}"
        }
        
    except Exception as e:
        logger.error(f"更新技能配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/skills/{skill_name}/content")
async def get_skill_content(
    skill_name: str = PathParam(
        ...,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        max_length=100,
        description="技能名称"
    ),
):
    """
    获取技能的 SKILL.md 完整内容

    Args:
        skill_name: 技能名称

    Returns:
        技能内容
    """
    logger.info(f"获取技能内容: {skill_name}")

    try:
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        agent_manager = manager.get_agent_manager()
        skills_loader = agent_manager.skills

        content = skills_loader.load_skill(skill_name)
        if content is None:
            raise HTTPException(status_code=404, detail=f"技能不存在: {skill_name}")

        return {"name": skill_name, "content": content}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取技能内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/skills")
async def create_skill(request: SkillCreateRequest):
    """
    创建新技能

    在 workspace/skills 中创建新的技能目录和 SKILL.md 文件。

    Args:
        request: 包含 name, description, content 的创建请求

    Returns:
        创建结果
    """
    logger.info(f"创建技能: {request.name}")

    try:
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        agent_manager = manager.get_agent_manager()
        skills_loader = agent_manager.skills

        skill_path = skills_loader.create_skill(
            name=request.name,
            description=request.description,
            content=request.content,
        )
        logger.info(f"技能已创建: {skill_path}")
        return {"success": True, "message": f"技能 {request.name} 已创建", "path": str(skill_path)}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"创建技能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/skills/{skill_name}/content")
async def update_skill_content(
    request: SkillContentUpdateRequest,
    skill_name: str = PathParam(
        ...,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        max_length=100,
        description="技能名称"
    ),
):
    """
    更新技能的 SKILL.md 内容

    Args:
        skill_name: 技能名称
        request: 包含完整 SKILL.md 内容的更新请求

    Returns:
        更新结果
    """
    logger.info(f"更新技能内容: {skill_name}")

    try:
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        agent_manager = manager.get_agent_manager()
        skills_loader = agent_manager.skills

        skill_path = skills_loader.update_skill(name=skill_name, content=request.content)
        logger.info(f"技能内容已更新: {skill_path}")
        return {"success": True, "message": f"技能 {skill_name} 已更新"}

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"更新技能内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/skills/{skill_name}")
async def delete_skill(
    skill_name: str = PathParam(
        ...,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        max_length=100,
        description="技能名称"
    ),
):
    """
    删除技能

    仅允许删除 workspace 技能。不允许删除内置技能。

    Args:
        skill_name: 技能名称

    Returns:
        删除结果
    """
    logger.info(f"删除技能: {skill_name}")

    try:
        from solopreneur.core.dependencies import get_component_manager
        manager = get_component_manager()
        agent_manager = manager.get_agent_manager()
        skills_loader = agent_manager.skills

        skills_loader.delete_skill(name=skill_name)
        logger.info(f"技能已删除: {skill_name}")
        return {"success": True, "message": f"技能 {skill_name} 已删除"}

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"删除技能失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
