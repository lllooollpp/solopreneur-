"""
长期运行 Agent 框架 API 端点
提供功能列表、进度追踪、会话上下文�?REST API

强约束特性：
- 单任务约束：同时只能有一�?in_progress
- 提交闸门：完成前检�?working tree clean
- 冒烟测试：启动时运行强制测试
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from solopreneur.agent.core.harness import LongRunningHarness


router = APIRouter()


# ==================== Models ====================

class FeatureCreate(BaseModel):
    """创建功能请求"""
    id: str
    category: str
    priority: str  # P0, P1, P2
    description: str
    steps: list[str]
    test_criteria: str
    test_cases: Optional[list[dict]] = None


class FeatureUpdate(BaseModel):
    """更新功能请求"""
    status: Optional[str] = None
    notes: Optional[str] = None


class ProgressRecord(BaseModel):
    """进度记录请求"""
    message: str


class CompleteFeatureRequest(BaseModel):
    """完成功能请求"""
    notes: Optional[str] = ""
    verify_clean: Optional[bool] = True


class StartFeatureRequest(BaseModel):
    """开始功能请�?""
    force: Optional[bool] = False


# ==================== Helper ====================

def _get_harness() -> LongRunningHarness:
    """获取 harness 实例"""
    from solopreneur.core.dependencies import get_component_manager
    manager = get_component_manager()
    config = manager.get_config()
    workspace = Path(config.agents.defaults.workspace).expanduser()
    return LongRunningHarness(workspace)


# ==================== Routes ====================

@router.get("/harness/status")
async def get_harness_status():
    """
    获取长期运行框架状�?    
    Returns:
        - initialized: 是否已初始化
        - working_tree_clean: 工作区是否干净
        - constraints: 约束配置
    """
    harness = _get_harness()
    clean_check = harness.verify_working_tree_clean()
    
    return {
        "initialized": harness.is_initialized(),
        "agent_dir": str(harness.agent_dir),
        "feature_list_path": str(harness.feature_list_path),
        "progress_path": str(harness.progress_path),
        "working_tree_clean": clean_check["clean"],
        "constraints": {
            "single_task": True,
            "require_clean_working_tree": True,
            "require_test_pass": True
        }
    }


@router.get("/harness/context")
async def get_session_context():
    """
    获取会话上下�?    
    每次新会话开始时应调用此接口，获取：
    - 当前功能状�?    - 最近进�?    - Git 历史
    - 下一步建�?    """
    harness = _get_harness()
    return harness.get_session_context()


@router.get("/harness/prompt")
async def get_startup_prompt():
    """
    获取启动提示�?    
    返回一个格式化的提示词，可直接用于 Agent
    """
    harness = _get_harness()
    return {
        "prompt": harness.get_startup_prompt()
    }


@router.post("/harness/smoke-test")
async def run_smoke_tests():
    """
    运行冒烟测试
    
    强制运行，验证核心功能可用�?    """
    harness = _get_harness()
    result = harness.run_smoke_tests()
    
    if not result["passed"]:
        raise HTTPException(
            status_code=500,
            detail=f"Smoke tests failed: {result['summary']}"
        )
    
    return result


@router.get("/harness/working-tree")
async def check_working_tree():
    """
    检�?git working tree 状�?    
    用于完成功能前的质量闸门
    """
    harness = _get_harness()
    return harness.verify_working_tree_clean()


@router.get("/harness/current-feature")
async def get_enforced_current_feature():
    """
    获取当前唯一允许的功能（强约束版本）
    
    如果有多�?in_progress，会自动将其余标记为 blocked
    """
    harness = _get_harness()
    feature = harness.get_enforced_current_feature()
    
    return {
        "feature": feature,
        "message": "Found current feature" if feature else "No active feature"
    }


@router.get("/features")
async def list_features(
    status: Optional[str] = Query(None, description="按状态过�? pending, in_progress, completed, blocked")
):
    """
    列出所有功�?    
    Args:
        status: 可选，按状态过�?    """
    harness = _get_harness()
    features = harness.list_features(status)
    
    return {
        "total": len(features),
        "features": features
    }


@router.get("/features/{feature_id}")
async def get_feature(feature_id: str):
    """获取单个功能详情"""
    harness = _get_harness()
    feature = harness.get_feature(feature_id)
    
    if not feature:
        raise HTTPException(status_code=404, detail=f"Feature not found: {feature_id}")
    
    return feature


@router.post("/features")
async def add_feature(feature: FeatureCreate):
    """添加新功�?""
    harness = _get_harness()
    
    # 检�?ID 是否已存�?    if harness.get_feature(feature.id):
        raise HTTPException(status_code=400, detail=f"Feature ID already exists: {feature.id}")
    
    feature_dict = feature.model_dump()
    feature_dict["status"] = "pending"
    feature_dict["completed_at"] = None
    feature_dict["assigned_to"] = None
    feature_dict["notes"] = None
    
    harness.add_feature(feature_dict)
    
    return {"message": f"Feature {feature.id} added", "feature": feature_dict}


@router.post("/features/{feature_id}/start")
async def start_feature(feature_id: str, request: StartFeatureRequest = None):
    """
    开始一个功能（强约束版本）
    
    强约束：
    - 如果有其�?in_progress 的功能，会自动将其转�?blocked
    - 除非 force=True，否则不允许同时有多个进行中
    """
    harness = _get_harness()
    
    if request is None:
        request = StartFeatureRequest()
    
    result = harness.start_feature(feature_id, force=request.force)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    
    return {
        "message": result["message"],
        "feature_id": feature_id,
        "status": "in_progress",
        "blocked_features": result["blocked_features"]
    }


@router.post("/features/{feature_id}/complete")
async def complete_feature(feature_id: str, request: CompleteFeatureRequest = None):
    """
    完成一个功能（强约束版�?- 硬门禁）

    硬门禁：
    1. 强制运行功能测试用例，必须全部通过
    2. 强制检�?git working tree 是否干净
    3. 两项都通过才允许完�?    """
    harness = _get_harness()

    if request is None:
        request = CompleteFeatureRequest()

    result = harness.complete_feature(
        feature_id,
        request.notes or "",
        verify_clean=request.verify_clean,
        run_tests=True,  # 强制运行测试
        force=False
    )

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return {
        "message": result["message"],
        "feature_id": feature_id,
        "status": "completed",
        "notes": request.notes,
        "committed": result["committed"],
        "test_passed": result.get("test_passed", None)
    }


@router.post("/features/{feature_id}/block")
async def block_feature(feature_id: str, reason: str = Query(..., description="阻塞原因")):
    """阻塞一个功�?""
    harness = _get_harness()
    
    if not harness.block_feature(feature_id, reason):
        raise HTTPException(status_code=404, detail=f"Feature not found: {feature_id}")
    
    return {"message": f"Feature {feature_id} blocked", "reason": reason}


@router.post("/features/{feature_id}/tests")
async def run_feature_tests(feature_id: str):
    """
    运行功能的测试用�?    
    Returns:
        - passed: 是否全部通过
        - results: 各测试结�?        - summary: 总结
    """
    harness = _get_harness()
    
    if not harness.get_feature(feature_id):
        raise HTTPException(status_code=404, detail=f"Feature not found: {feature_id}")
    
    result = harness.run_feature_tests(feature_id)
    
    return result


@router.get("/progress")
async def get_progress():
    """获取最近进�?""
    harness = _get_harness()
    
    if not harness.progress_path.exists():
        return {"progress": "No progress recorded yet."}
    
    content = harness.progress_path.read_text(encoding="utf-8")
    
    return {
        "file": str(harness.progress_path),
        "content": content
    }


@router.post("/progress")
async def record_progress(progress: ProgressRecord):
    """记录进度"""
    harness = _get_harness()
    harness.record_progress(progress.message)
    
    return {"message": "Progress recorded", "entry": progress.message}


@router.post("/harness/initialize")
async def initialize_harness():
    """
    初始化长期运行框�?
    仅首次运行时需要调�?    """
    harness = _get_harness()

    if harness.is_initialized():
        return {"message": "Harness already initialized", "path": str(harness.agent_dir)}

    # �?specs 加载初始功能
    # TODO: 自动�?specs 目录解析
    initial_features = []

    harness.initialize("nanobot", initial_features)

    return {
        "message": "Harness initialized",
        "agent_dir": str(harness.agent_dir),
        "feature_list": str(harness.feature_list_path),
        "progress_file": str(harness.progress_path)
    }


@router.post("/harness/session-tests")
async def run_session_startup_tests():
    """
    运行会话启动测试（硬闭环�?
    在会话开始时自动运行当前项目的测试，验证上次改动没有破坏功能�?    """
    harness = _get_harness()
    result = harness.run_session_startup_tests()

    return result


@router.post("/features/{feature_id}/transition")
async def transition_feature_status(
    feature_id: str,
    new_status: str = Query(..., description="目标状�? pending, in_progress, completed, blocked"),
    reason: str = Query("", description="变更原因"),
    bypass_validation: bool = Query(False, description="跳过验证（仅限管理员�?)
):
    """
    状态转换入口（门禁控制�?
    所有状态变更必须通过此接口，确保状态转换合法并记录审计日志�?    """
    harness = _get_harness()

    result = harness.transition_feature_status(feature_id, new_status, reason, bypass_validation)

    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])

    return result


@router.get("/features/{feature_id}/audit")
async def get_feature_audit_log(feature_id: str):
    """
    获取功能的状态变更审计日�?    """
    harness = _get_harness()
    logs = harness.get_status_audit_log(feature_id)

    return {
        "feature_id": feature_id,
        "audit_count": len(logs),
        "logs": logs
    }


@router.get("/status-governance")
async def get_status_governance():
    """
    获取状态治理规�?    """
    harness = _get_harness()
    feature_list = harness._load_feature_list()

    return {
        "status_governance": feature_list.get("status_governance", {}),
        "valid_transitions": harness.VALID_TRANSITIONS,
        "constraints": feature_list.get("constraints", {})
    }
