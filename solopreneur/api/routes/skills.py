"""
技能配�?API 端点
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
            raise ValueError("技能变量数量不能超�?0�?)
        
        # 验证每个键值对
        for key, value in v.items():
            if len(key) > 100:
                raise ValueError(f"变量名过�? {key}")
            if len(value) > 10000:
                raise ValueError(f"变量值过�? {key}")
        
        return v


class SkillsResponse(BaseModel):
    """技能列表响�?""
    skills: List[SkillItem]


class SkillUpdateRequest(BaseModel):
    """技能更新请�?""
    enabled: bool


@router.get("/config/skills", response_model=SkillsResponse)
async def get_skills():
    """
    获取所有可用技能列�?
    
    Returns:
        SkillsResponse: 包含所有技能的列表
    """
    logger.info("获取技能列�?)
    
    try:
        # �?AgentManager 使用同一�?workspace 路径�?SkillsLoader，避免“页面与运行时路径不一致�?
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

            # 优先�?frontmatter description 获取
            description = "技�?
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
        logger.error(f"获取技能列表失�? {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/skills/{skill_name}")
async def update_skill(
    skill_name: str = PathParam(
        ...,
        pattern=r"^[a-zA-Z0-9\-_]+$",
        max_length=100,
        description="技能名称，只允许字母数�?_"
    ),
    request: SkillUpdateRequest = None
):
    """
    更新技能配�?
    
    Args:
        skill_name: 技能名�?
        request: 更新请求
        
    Returns:
        更新结果
    """
    logger.info(f"更新技能配�? {skill_name}, enabled={request.enabled}")
    
    try:
        # 未来扩展: 持久化技能配置到配置文件
        # 当前简单返回成功状�?
        return {
            "success": True,
            "message": f"技�?{skill_name} 已{'启用' if request.enabled else '禁用'}"
        }
        
    except Exception as e:
        logger.error(f"更新技能配置失�? {e}")
        raise HTTPException(status_code=500, detail=str(e))
