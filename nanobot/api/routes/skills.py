"""
技能配置 API 端点
管理技能的启用状态和变量
"""
from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field, field_validator
from typing import Dict, List
from loguru import logger
from pathlib import Path

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


@router.get("/config/skills", response_model=SkillsResponse)
async def get_skills():
    """
    获取所有可用技能列表
    
    Returns:
        SkillsResponse: 包含所有技能的列表
    """
    logger.info("获取技能列表")
    
    try:
        skills = []
        
        # 扫描 bundled skills
        from nanobot.config.loader import load_config
        config = load_config()
        
        bundled_skills_path = Path(__file__).parent.parent.parent / "skills"
        
        if bundled_skills_path.exists():
            for skill_dir in bundled_skills_path.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    skill_md = skill_dir / "SKILL.md"
                    description = "内置技能"
                    
                    # 读取技能描述（从 SKILL.md 第一行）
                    try:
                        first_line = skill_md.read_text(encoding='utf-8').split('\n')[0]
                        if first_line.startswith('#'):
                            description = first_line.lstrip('#').strip()
                    except:
                        pass
                    
                    skills.append(SkillItem(
                        name=skill_dir.name,
                        source="bundled",
                        enabled=True,
                        description=description,
                        variables={},
                        overridden=False
                    ))
        
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
