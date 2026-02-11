"""
Agent 定义管理 API
"""
from fastapi import APIRouter, HTTPException, Body
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from nanobot.config.loader import load_config
from loguru import logger

router = APIRouter()


class AgentDefinitionUpdate(BaseModel):
    content: str = Field(
        ...,
        min_length=1,
        max_length=1_000_000,  # 1MB字符限制
        description="Agent定义内容，最大1MB"
    )
    
    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """验证Agent定义内容"""
        # 检查是否为有效UTF-8（Pydantic已默认处理）
        if not v.strip():
            raise ValueError("Agent定义不能为空")
        
        # 检查字节大小（而非字符数）
        byte_size = len(v.encode('utf-8'))
        if byte_size > 1_000_000:  # 1MB
            raise ValueError(f"Agent定义文件过大: {byte_size} bytes（最大1MB）")
        
        return v


@router.get("/agent/definition", response_class=PlainTextResponse)
async def get_agent_definition():
    """获取 Agent 定义 (SOUL.md)"""
    from nanobot.core.dependencies import get_component_manager
    manager = get_component_manager()
    config = manager.get_config()
    soul_path = config.workspace_path / "SOUL.md"

    if not soul_path.exists():
        raise HTTPException(status_code=404, detail="SOUL.md 不存在")

    try:
        # 尝试多种编码读取
        for encoding in ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'latin1']:
            try:
                content = soul_path.read_text(encoding=encoding)
                logger.info(f"成功使用 {encoding} 编码读取 SOUL.md")
                return content
            except UnicodeDecodeError:
                continue

        # 如果所有编码都失败，返回错误
        raise HTTPException(status_code=500, detail="无法解码 SOUL.md 文件，请检查文件编码")
    except Exception as e:
        logger.error(f"读取 SOUL.md 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/definition")
async def update_agent_definition(data: AgentDefinitionUpdate):
    """更新 Agent 定义 (SOUL.md)"""
    from nanobot.core.dependencies import get_component_manager
    manager = get_component_manager()
    config = manager.get_config()
    soul_path = config.workspace_path / "SOUL.md"

    try:
        # 确保使用 UTF-8 编码保存
        soul_path.write_text(data.content, encoding="utf-8")
        logger.info(f"成功保存 SOUL.md，长度: {len(data.content)} 字符")
        # 清除配置缓存，确保下次加载最新配置
        from nanobot.config.loader import invalidate_config_cache
        invalidate_config_cache()
        return {"success": True, "message": "Agent 定义已保存"}
    except Exception as e:
        logger.error(f"保存 SOUL.md 失败: {e}")
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")
