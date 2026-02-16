"""
项目管理 API 端点
"""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from solopreneur.projects import ProjectManager, ProjectCreate, ProjectUpdate, ProjectEnvVar
from solopreneur.core.dependencies import get_component_manager
from solopreneur.storage import SubagentTaskPersistence

router = APIRouter()

# 全局项目管理器实�?
_project_manager: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """获取项目管理器实例（单例�?""
    global _project_manager
    if _project_manager is None:
        _project_manager = ProjectManager()
    return _project_manager


@router.get("/projects")
async def list_projects():
    """
    获取所有项目列�?
    
    Returns:
        项目列表
    """
    try:
        manager = get_project_manager()
        projects = manager.list_projects()
        return {
            "projects": [p.to_dict() for p in projects],
            "total": len(projects)
        }
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """
    获取项目详情
    
    Args:
        project_id: 项目ID
        
    Returns:
        项目详情
    """
    try:
        manager = get_project_manager()
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return project.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects")
async def create_project(data: ProjectCreate):
    """
    创建新项�?
    
    支持创建本地项目或从 Git 仓库克隆
    
    Args:
        data: 项目创建数据
        
    Returns:
        创建的项目信�?
    """
    try:
        manager = get_project_manager()
        project = manager.create_project(data)
        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"Project '{project.name}' created successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate):
    """
    更新项目信息
    
    Args:
        project_id: 项目ID
        data: 更新数据
        
    Returns:
        更新后的项目信息
    """
    try:
        manager = get_project_manager()
        project = manager.update_project(project_id, data)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return {
            "success": True,
            "project": project.to_dict(),
            "message": f"Project '{project.name}' updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}")
async def delete_project(
    project_id: str,
    delete_files: bool = Query(default=False, description="是否同时删除项目文件")
):
    """
    删除项目
    
    Args:
        project_id: 项目ID
        delete_files: 是否同时删除项目文件（仅对Git克隆的项目有效）
        
    Returns:
        删除结果
    """
    try:
        manager = get_project_manager()
        success = manager.delete_project(project_id, delete_files=delete_files)
        if not success:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return {
            "success": True,
            "message": f"Project {project_id} deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/pull")
async def pull_project(project_id: str):
    """
    拉取 Git 仓库更新
    
    仅适用于从 Git 仓库克隆的项�?
    
    Args:
        project_id: 项目ID
        
    Returns:
        拉取结果
    """
    try:
        manager = get_project_manager()
        result = manager.pull_repository(project_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to pull project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/status")
async def get_project_status(project_id: str):
    """
    获取项目状态（包括Git状态）
    
    Args:
        project_id: 项目ID
        
    Returns:
        项目状态信�?
    """
    try:
        manager = get_project_manager()
        status = manager.get_project_status(project_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get project status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class WikiGenerateRequest(BaseModel):
    options: dict | None = None
    model: str | None = None
    note: str | None = None


class ProjectEnvUpdateRequest(BaseModel):
    env_vars: list[ProjectEnvVar]


@router.get("/projects/{project_id}/env")
async def get_project_env(project_id: str):
    """获取项目环境变量列表�?""
    try:
        manager = get_project_manager()
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return {
            "project_id": project_id,
            "env_vars": [item.model_dump(mode="json") for item in project.env_vars],
            "total": len(project.env_vars),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project env vars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/env")
async def set_project_env(project_id: str, data: ProjectEnvUpdateRequest):
    """覆盖设置项目环境变量�?""
    try:
        manager = get_project_manager()
        project = manager.set_project_env_vars(project_id, data.env_vars)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        return {
            "success": True,
            "project_id": project_id,
            "env_vars": [item.model_dump(mode="json") for item in project.env_vars],
            "total": len(project.env_vars),
            "message": "Project env vars updated successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set project env vars: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/env/{key}")
async def delete_project_env(project_id: str, key: str):
    """删除项目中的单个环境变量�?""
    try:
        manager = get_project_manager()
        deleted, project = manager.delete_project_env_var(project_id, key)
        if project is None:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Env var not found: {key}")
        return {
            "success": True,
            "project_id": project_id,
            "message": f"Env var '{key}' deleted successfully",
            "total": len(project.env_vars),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project env var: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/docs")
async def get_project_docs(project_id: str):
    """
    获取项目�?Wiki 文档列表

    Args:
        project_id: 项目ID

    Returns:
        文档列表
    """
    try:
        from pathlib import Path

        manager = get_project_manager()
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

        # 查找项目目录下的 docs �?wiki 文件�?
        project_path = Path(project.path)
        docs_dirs = []

        for dir_name in ['docs', 'wiki', 'documentation']:
            docs_dir = project_path / dir_name
            if docs_dir.exists() and docs_dir.is_dir():
                docs_dirs.append(docs_dir)

        files = []
        for docs_dir in docs_dirs:
            for file_path in docs_dir.rglob('*.md'):
                relative_path = file_path.relative_to(project_path)
                # 读取文件内容
                try:
                    content = file_path.read_text(encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Failed to read file {file_path}: {e}")
                    content = ""
                files.append({
                    "name": file_path.name,
                    "path": str(relative_path),
                    "content": content
                })

        return {"files": files}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/wiki/generate")
async def generate_project_wiki(project_id: str, data: WikiGenerateRequest):
    """
    触发为指定项目生�?Wiki 文档的后台子任务�?

    返回任务 ID（已接受），实际生成由后台子 Agent 执行并在完成后通过系统消息汇报�?
    """
    try:
        manager = get_project_manager()
        project = manager.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail=f"Project not found: {project_id}")

        comp = get_component_manager()
        agent_loop = await comp.get_agent_loop()

        # 获取 wiki_writer agent 定义
        agent_def = agent_loop.agent_manager.get_agent("wiki_writer")
        if agent_def is None:
            raise HTTPException(status_code=500, detail="wiki_writer agent not available")

        # 构建任务描述
        opts = data.options or {}
        task_desc = (
            f"Generate project wiki for '{project.name}' at {project.path}.\n"
            f"Options: {opts}\n"
        )
        if data.note:
            task_desc += f"Note: {data.note}\n"

        # 运行在后台，立即返回任务 id
        task_id = str(uuid.uuid4())[:8]
        task_store = SubagentTaskPersistence()

        # 先落一�?pending，便于前�?诊断查询到任�?
        task_store.upsert(
            task_id=task_id,
            label=f"Wiki生成: {project.name}",
            task_text=task_desc,
            origin_channel="api",
            origin_chat_id=project_id,
            status="pending",
        )

        async def _bg_run():
            try:
                task_store.upsert(
                    task_id=task_id,
                    label=f"Wiki生成: {project.name}",
                    task_text=task_desc,
                    origin_channel="api",
                    origin_chat_id=project_id,
                    status="running",
                )

                logger.info("=" * 60)
                logger.info(f"[{task_id}] 🚀 开始后�?Wiki 生成任务")
                logger.info(f"[{task_id}] 项目: {project.name}")
                logger.info(f"[{task_id}] 路径: {project.path}")
                logger.info(f"[{task_id}] Agent: {agent_def.name} ({agent_def.title})")
                logger.info(f"[{task_id}] 任务描述: {task_desc[:200]}...")
                logger.info("=" * 60)

                result = await agent_loop.subagents.run_with_agent(
                    agent_def=agent_def,
                    agent_manager=agent_loop.agent_manager,
                    task=task_desc,
                    context="",
                    project_dir=str(project.path),
                )

                logger.info("=" * 60)
                logger.info(f"[{task_id}] �?Wiki 生成完成")
                logger.info(f"[{task_id}] 结果长度: {len(result)} 字符")
                logger.info("=" * 60)

                task_store.upsert(
                    task_id=task_id,
                    label=f"Wiki生成: {project.name}",
                    task_text=task_desc,
                    origin_channel="api",
                    origin_chat_id=project_id,
                    status="success",
                    result_text=result,
                )

                # 发布结果回主 Agent（使用子 Agent 的公告格式）
                await agent_loop.subagents._announce_result(
                    task_id=task_id,
                    label=f"Wiki生成: {project.name}",
                    task=task_desc,
                    result=result,
                    origin={"channel": "cli", "chat_id": "direct"},
                    status="ok",
                )
            except Exception as e:
                logger.error("=" * 60)
                logger.error(f"[{task_id}] �?Wiki 生成失败")
                logger.error(f"[{task_id}] 错误类型: {type(e).__name__}")
                logger.error(f"[{task_id}] 错误信息: {e}")
                logger.error("=" * 60, exc_info=True)

                task_store.upsert(
                    task_id=task_id,
                    label=f"Wiki生成: {project.name}",
                    task_text=task_desc,
                    origin_channel="api",
                    origin_chat_id=project_id,
                    status="failed",
                    error_text=str(e),
                )

                await agent_loop.subagents._announce_result(
                    task_id=task_id,
                    label=f"Wiki生成: {project.name}",
                    task=task_desc,
                    result=f"错误: {e}",
                    origin={"channel": "cli", "chat_id": "direct"},
                    status="error",
                )

        asyncio.create_task(_bg_run())

        return {"task_id": task_id, "status": "accepted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start wiki generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
