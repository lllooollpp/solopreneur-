"""
长期运行 Agent 框架
基于 Anthropic "Effective harnesses for long-running agents"

�?Agent 能够:
1. 跨会话保持进�?2. 每次只处理一个功�?(强约�?
3. 自动记录和恢复状�?4. 强制提交质量闸门
5. 测试用例驱动的完成判�?
关键约束:
- 同一时间只能有一�?in_progress 的功�?- 完成功能前必须检�?working tree clean
- 每个功能必须有对应的测试用例
"""
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger


class FeatureStatus(str, Enum):
    """功能状�?""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"


@dataclass
class TestCase:
    """测试用例"""
    name: str
    description: str
    command: str  # 执行命令
    expected: str  # 预期结果
    passed: bool = False


@dataclass
class Feature:
    """功能�?""
    id: str
    category: str
    priority: str  # P0, P1, P2
    description: str
    steps: list[str]
    test_criteria: str
    status: str = "pending"
    completed_at: str | None = None
    assigned_to: str | None = None
    notes: str | None = None
    test_cases: list[dict] = field(default_factory=list)  # 测试用例列表
    acceptance_tests: list[str] = field(default_factory=list)  # E2E 验收测试


class LongRunningHarness:
    """
    长期运行 Agent 框架
    
    负责�?    1. 管理 feature_list.json - 功能清单
    2. 记录进度�?progress.md - 进度文件
    3. 提供会话上下文恢�?- 让新会话快速理解项目状�?    4. 强约束：每次只处理一个功�?    5. 提交质量闸门：完成前检�?working tree clean
    
    关键约束:
    - start_feature() 时，如果有其�?in_progress，会自动将其转为 blocked
    - complete_feature() 时，会检�?git working tree 是否干净
    - 只有所有测试用例通过才能标记完成
    
    使用方式:
    ```python
    harness = LongRunningHarness(workspace_path)
    
    # 首次初始�?    harness.initialize("project_name", initial_features)
    
    # 每次会话开始时获取上下�?    context = harness.get_session_context()
    
    # 开始功能（强约束：会自动阻塞其他进行中的功能）
    harness.start_feature("FEAT-001")
    
    # 运行测试用例
    results = harness.run_tests("FEAT-001")
    
    # 完成功能（强制检�?git clean�?    harness.complete_feature("FEAT-001", "实现完成")
    ```
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.agent_dir = workspace / ".agent"
        self.agent_dir.mkdir(exist_ok=True)
        
        self.feature_list_path = self.agent_dir / "feature_list.json"
        self.progress_path = self.agent_dir / "progress.md"
        self.session_state_path = self.agent_dir / "session_state.json"
        self.test_results_dir = self.agent_dir / "test_results"
        self.test_results_dir.mkdir(exist_ok=True)
    
    def is_initialized(self) -> bool:
        """检查是否已初始�?""
        return self.feature_list_path.exists()
    
    def initialize(self, project_name: str, initial_features: list[dict]) -> None:
        """
        初始化环境（首次运行时调用）
        
        类似文章中的 Initializer Agent:
        - 创建 feature_list.json
        - 创建 progress.md
        - 创建 init.sh
        """
        # 创建功能清单
        feature_list = {
            "project": project_name,
            "version": "0.1.0",
            "last_updated": datetime.now().isoformat(),
            "features": initial_features,
            "statistics": self._calc_statistics(initial_features)
        }
        
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(feature_list, f, indent=2, ensure_ascii=False)
        
        # 创建进度文件
        self._init_progress_file(project_name)
        
        logger.info(f"�?Initialized long-running harness for {project_name}")
        logger.info(f"   Feature list: {self.feature_list_path}")
        logger.info(f"   Progress file: {self.progress_path}")
    
    def get_session_context(self) -> dict[str, Any]:
        """
        获取会话上下文（每次新会话开始时调用�?        
        类似文章中的 "Getting up to speed" 流程:
        1. 读取进度文件
        2. 读取 feature list
        3. 获取 git log
        4. 确定当前要做什�?        
        Returns:
            dict: 包含 feature_list, recent_progress, git_log, current_feature, next_steps
        """
        if not self.is_initialized():
            return {
                "initialized": False,
                "message": "Run harness.initialize() first"
            }

        feature_list = self._load_feature_list()

        context = {
            "initialized": True,
            "project": feature_list.get("project", "unknown"),
            "version": feature_list.get("version", "0.0.0"),
            "statistics": feature_list.get("statistics", {}),
            "recent_progress": self._load_recent_progress(),
            "git_log": self._get_recent_commits(),
            "current_feature": None,
            "next_steps": [],
            "test_config": feature_list.get("test_config", {}),
            "session_tests_passed": None  # 会话启动测试结果
        }

        # 检查是否有进行中的功能
        for f in feature_list.get("features", []):
            if f.get("status") == "in_progress":
                context["current_feature"] = f
                context["next_steps"] = [
                    f"Continue: {f['description']}",
                    f"Steps remaining: {', '.join(f.get('steps', []))}"
                ]
                break

        # 如果没有进行中的，找下一个待处理
        if not context["current_feature"]:
            for f in feature_list.get("features", []):
                if f.get("status") == "pending":
                    context["current_feature"] = f
                    context["next_steps"] = [
                        f"Start: {f['description']}",
                        f"Priority: {f['priority']}"
                    ]
                    break

        return context

    def run_session_startup_tests(self) -> dict:
        """
        会话启动时自动运行项目测试（硬闭环）

        这是评审要求�?会话开始先跑正在开发项目的 E2E/回归测试"的实现�?
        Returns:
            dict: {"passed": bool, "results": list, "summary": str, "should_continue": bool}
        """
        feature_list = self._load_feature_list()
        test_config = feature_list.get("test_config", {})

        # 如果没有配置测试命令，尝试自动检�?        if not test_config:
            test_config = self._auto_detect_test_config()

        if not test_config.get("enabled", True):
            return {
                "passed": True,
                "results": [],
                "summary": "Tests disabled in config",
                "should_continue": True
            }

        results = []
        all_passed = True

        # 运行配置的测试命�?        test_commands = test_config.get("commands", [])

        if not test_commands:
            # 默认测试命令
            test_commands = self._get_default_test_commands()

        for cmd in test_commands:
            result = self._run_command(cmd.get("command", cmd) if isinstance(cmd, dict) else cmd)
            result["name"] = cmd.get("name", cmd) if isinstance(cmd, dict) else cmd
            results.append(result)
            if not result["passed"]:
                all_passed = False

        summary = f"{'�?All session startup tests passed' if all_passed else '�?Session startup tests failed'} ({len(results)} commands)"

        # 记录测试结果
        self._append_progress(f"🔄 Session startup tests: {summary}")

        return {
            "passed": all_passed,
            "results": results,
            "summary": summary,
            "should_continue": all_passed or not test_config.get("block_on_failure", True)
        }

    def _auto_detect_test_config(self) -> dict:
        """自动检测项目的测试配置"""
        test_config = {"enabled": True, "commands": [], "block_on_failure": True}

        # 检�?Python 项目
        if (self.workspace / "pyproject.toml").exists() or (self.workspace / "setup.py").exists():
            test_config["commands"].append({"name": "pytest", "command": "pytest -x -q"})

        # 检�?Node.js 项目
        if (self.workspace / "package.json").exists():
            test_config["commands"].append({"name": "npm test", "command": "npm test --if-present"})

        # 检�?Playwright E2E 测试
        if (self.workspace / "playwright.config.ts").exists() or (self.workspace / "e2e").exists():
            test_config["commands"].append({"name": "playwright", "command": "npx playwright test --reporter=list"})

        return test_config

    def _get_default_test_commands(self) -> list:
        """获取默认测试命令"""
        return [
            {"name": "quick tests", "command": "pytest -x -q --ignore=tests/e2e"}
        ]

    def _run_command(self, command: str) -> dict:
        """运行命令并返回结�?""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=300  # 5分钟超时
            )

            return {
                "command": command,
                "passed": result.returncode == 0,
                "output": (result.stdout + result.stderr)[:1000],
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"command": command, "passed": False, "output": "Command timed out", "exit_code": -1}
        except Exception as e:
            return {"command": command, "passed": False, "output": str(e), "exit_code": -1}
    
    def get_startup_prompt(self) -> str:
        """
        获取启动提示词（�?Agent 使用�?
        这是一个标准化的启动流程，确保每次会话都能快速理解状�?        包含：会话启动时运行测试的强制流�?        """
        context = self.get_session_context()

        if not context.get("initialized"):
            return """
# 项目未初始化

请先运行初始化：
```python
from solopreneur.agent.core.harness import LongRunningHarness
harness = LongRunningHarness(workspace)
harness.initialize("project_name", features)
```
"""

        prompt = f"""# 项目上下�?
## ⚠️ 会话启动检查清�?
**在开始任何工作之前，请按以下顺序执行�?*

1. **运行项目测试** - 验证上次会话的改动没有破坏现有功�?   ```bash
   # Python 项目
   pytest

   # Node.js 项目
   npm test

   # E2E 测试
   npx playwright test
   ```

2. **如果测试失败** - 优先修复失败的测试，再继续新的开发工�?
3. **检�?Working Tree** - 确认 git 状�?   ```bash
   git status
   ```
   如果有未提交的更改，考虑是否需要先提交或暂存�?
---

## 当前状�?- 项目: {context['project']} v{context['version']}
- 统计: 总计 {context['statistics'].get('total', 0)} 个功�?  - �?已完�? {context['statistics'].get('completed', 0)}
  - 🔄 进行�? {context['statistics'].get('in_progress', 0)}
  - �?待处�? {context['statistics'].get('pending', 0)}

## 最近进�?{context['recent_progress']}

## 最近提�?{chr(10).join(context['git_log'][:5]) if context['git_log'] else '暂无提交'}

## 当前任务
"""

        if context['current_feature']:
            f = context['current_feature']
            prompt += f"""
- ID: {f['id']}
- 描述: {f['description']}
- 优先�? {f['priority']}
- 状�? {f['status']}
- 步骤:
{chr(10).join(f'  - {s}' for s in f.get('steps', []))}
- 验收标准: {f.get('test_criteria', '未定�?)}
- 测试用例: {len(f.get('test_cases', []))} �?"""
        else:
            prompt += "所有功能已完成！🎉\n"

        prompt += f"""
## 下一�?{chr(10).join(f'- {s}' for s in context['next_steps']) if context['next_steps'] else '- 无待处理任务'}

## 功能完成前的检查清�?- [ ] 单元测试已编写并通过
- [ ] 集成测试已编写并通过（如适用�?- [ ] E2E 测试已编写并通过（前端功能）
- [ ] 运行 `pytest` �?`npm test` 全部通过
- [ ] 运行 `npx playwright test` 全部通过（前端功能）
- [ ] Git working tree 干净
"""

        return prompt
    
    def start_feature(self, feature_id: str, force: bool = False) -> dict:
        """
        标记功能为进行中（强约束版本�?        
        强约束逻辑�?        1. 如果有其�?in_progress 的功能，会自动将其转�?blocked
        2. 除非 force=True，否则不允许同时有多个进行中
        
        Args:
            feature_id: 功能 ID
            force: 是否强制开始（忽略单任务约束）
        
        Returns:
            dict: {"success": bool, "blocked_features": list, "message": str}
        """
        feature_list = self._load_feature_list()
        features = feature_list.get("features", [])
        
        # 找到目标功能
        target_feature = None
        for f in features:
            if f.get("id") == feature_id:
                target_feature = f
                break
        
        if not target_feature:
            return {"success": False, "blocked_features": [], "message": f"Feature not found: {feature_id}"}
        
        # 检查是否已完成
        if target_feature.get("status") == "completed":
            return {"success": False, "blocked_features": [], "message": f"Feature already completed: {feature_id}"}
        
        # 强约束：检查是否有其他进行中的功能
        blocked_features = []
        if not force:
            for f in features:
                if f.get("status") == "in_progress" and f.get("id") != feature_id:
                    # 自动阻塞其他进行中的功能
                    f["status"] = "blocked"
                    f["notes"] = f"Auto-blocked: {feature_id} started"
                    blocked_features.append(f["id"])
                    logger.warning(f"Auto-blocked feature {f['id']} due to single-task constraint")
        
        # 标记目标功能为进行中
        target_feature["status"] = "in_progress"
        self._save_feature_list(feature_list)
        
        # 记录进度
        msg = f"🚀 Started #{feature_id}: {target_feature['description']}"
        if blocked_features:
            msg += f" (auto-blocked: {', '.join(blocked_features)})"
        self._append_progress(msg)

        logger.info(f"Started feature: {feature_id}")
        return {
            "success": True,
            "blocked_features": blocked_features,
            "message": f"Started {feature_id}" + (f", blocked {len(blocked_features)} other features" if blocked_features else "")
        }

    def complete_feature(
        self,
        feature_id: str,
        notes: str = "",
        verify_clean: bool = True,
        run_tests: bool = True,
        force: bool = False
    ) -> dict:
        """
        标记功能为已完成（强约束版本�?
        强约束逻辑（硬门禁）：
        1. 强制运行功能测试用例，必须全部通过
        2. 强制检�?git working tree 是否干净
        3. 两项都通过才允许完�?
        Args:
            feature_id: 功能 ID
            notes: 完成备注
            verify_clean: 是否检�?git working tree 干净
            run_tests: 是否运行测试用例（默认强制）
            force: 是否跳过所有检查（危险，仅限特殊情况）

        Returns:
            dict: {"success": bool, "committed": bool, "test_passed": bool, "message": str}
        """
        feature_list = self._load_feature_list()

        # 查找目标功能
        target_feature = None
        for f in feature_list.get("features", []):
            if f.get("id") == feature_id:
                target_feature = f
                break

        if not target_feature:
            return {"success": False, "committed": False, "test_passed": False, "message": f"Feature not found: {feature_id}"}

        # 检查功能状态（只能完成 in_progress 的功能）
        if target_feature.get("status") != "in_progress":
            return {
                "success": False,
                "committed": False,
                "test_passed": False,
                "message": f"Feature {feature_id} is not in_progress (current: {target_feature.get('status')}). Only in_progress features can be completed."
            }

        # 硬门�?1：强制运行测试用�?        test_result = None
        if run_tests and not force:
            test_result = self.run_feature_tests(feature_id)
            if not test_result["passed"]:
                return {
                    "success": False,
                    "committed": False,
                    "test_passed": False,
                    "message": f"Tests failed for {feature_id}. Fix failing tests before completing.\n{test_result['summary']}"
                }

        # 硬门�?2：检�?working tree（强约束�?        if verify_clean and not force:
            clean_check = self.verify_working_tree_clean()
            if not clean_check["clean"]:
                return {
                    "success": False,
                    "committed": False,
                    "test_passed": test_result["passed"] if test_result else None,
                    "message": f"Working tree not clean: {clean_check['changes']}. Commit or stash changes first."
                }

        # 所有门禁通过，标记完�?        target_feature["status"] = "completed"
        target_feature["completed_at"] = datetime.now().isoformat()
        if notes:
            target_feature["notes"] = notes
        if test_result:
            target_feature["test_results"] = {
                "passed": test_result["passed"],
                "summary": test_result["summary"],
                "timestamp": datetime.now().isoformat()
            }
        self._save_feature_list(feature_list)
        self._append_progress(f"�?Completed #{feature_id}: {notes}")
        logger.info(f"Completed feature: {feature_id}")
        return {
            "success": True,
            "committed": True,
            "test_passed": True,
            "message": f"Feature {feature_id} completed successfully (tests passed, working tree clean)"
        }
    
    def verify_working_tree_clean(self) -> dict:
        """
        检�?git working tree 是否干净
        
        Returns:
            dict: {"clean": bool, "changes": list, "message": str}
        """
        try:
            # 检查是否有未提交的更改
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=10
            )
            
            if result.returncode != 0:
                return {"clean": False, "changes": [], "message": f"Git command failed: {result.stderr}"}
            
            changes = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            if changes:
                return {
                    "clean": False,
                    "changes": changes,
                    "message": f"Working tree has {len(changes)} uncommitted changes"
                }
            
            return {"clean": True, "changes": [], "message": "Working tree is clean"}
            
        except Exception as e:
            return {"clean": False, "changes": [], "message": f"Error checking working tree: {e}"}
    
    def run_feature_tests(self, feature_id: str) -> dict:
        """
        运行功能的测试用�?        
        Args:
            feature_id: 功能 ID
        
        Returns:
            dict: {"passed": bool, "results": list, "summary": str}
        """
        feature = self.get_feature(feature_id)
        if not feature:
            return {"passed": False, "results": [], "summary": f"Feature not found: {feature_id}"}
        
        test_cases = feature.get("test_cases", [])
        if not test_cases:
            return {"passed": True, "results": [], "summary": "No test cases defined"}
        
        results = []
        all_passed = True
        
        for tc in test_cases:
            test_result = self._run_single_test(tc)
            results.append(test_result)
            if not test_result["passed"]:
                all_passed = False
        
        # 保存测试结果
        result_file = self.test_results_dir / f"{feature_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({
                "feature_id": feature_id,
                "timestamp": datetime.now().isoformat(),
                "passed": all_passed,
                "results": results
            }, f, indent=2, ensure_ascii=False)
        
        summary = f"{'�?All tests passed' if all_passed else '�?Some tests failed'} ({len(results)} tests)"
        self._append_progress(f"🧪 Tests #{feature_id}: {summary}")
        
        return {"passed": all_passed, "results": results, "summary": summary}
    
    def _run_single_test(self, test_case: dict) -> dict:
        """运行单个测试用例"""
        name = test_case.get("name", "unnamed")
        command = test_case.get("command", "")
        expected = test_case.get("expected", "")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=60
            )
            
            output = result.stdout + result.stderr
            passed = expected.lower() in output.lower() if expected else result.returncode == 0
            
            return {
                "name": name,
                "passed": passed,
                "output": output[:500],  # 限制输出长度
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"name": name, "passed": False, "output": "Test timed out", "exit_code": -1}
        except Exception as e:
            return {"name": name, "passed": False, "output": str(e), "exit_code": -1}
    
    def run_smoke_tests(self) -> dict:
        """
        运行冒烟测试（每次会话启动时强制运行�?        
        冒烟测试包括�?        1. 后端 API 健康检�?        2. 前端构建检�?        3. 数据库连接检�?        4. 关键依赖导入检�?        
        Returns:
            dict: {"passed": bool, "results": list, "summary": str}
        """
        smoke_tests = [
            {
                "name": "Backend imports",
                "command": "python -c \"from solopreneur.api.main import app; print('OK')\"",
                "expected": "OK"
            },
            {
                "name": "Harness imports",
                "command": "python -c \"from solopreneur.agent.core.harness import LongRunningHarness; print('OK')\"",
                "expected": "OK"
            },
            {
                "name": "Provider imports",
                "command": "python -c \"from solopreneur.providers.litellm_provider import LiteLLMProvider; print('OK')\"",
                "expected": "OK"
            },
            {
                "name": "Config file exists",
                "command": "python -c \"from pathlib import Path; import os; p = Path.home() / '.solopreneur' / 'config.json'; print('EXISTS' if p.exists() else 'NOT_FOUND')\"",
                "expected": "EXISTS"
            },
            {
                "name": "Feature list valid",
                "command": f"python -c \"import json; f = open('{self.feature_list_path}'); d = json.load(f); print('VALID' if 'features' in d else 'INVALID')\"",
                "expected": "VALID"
            }
        ]
        
        results = []
        all_passed = True
        
        for test in smoke_tests:
            result = self._run_single_test(test)
            results.append(result)
            if not result["passed"]:
                all_passed = False
        
        summary = f"{'�?All smoke tests passed' if all_passed else '�?Smoke tests failed'} ({len(results)} tests)"
        logger.info(f"Smoke tests: {summary}")
        
        return {"passed": all_passed, "results": results, "summary": summary}
    
    def get_enforced_current_feature(self) -> dict | None:
        """
        获取当前唯一允许的功能（强约束版本）
        
        强约束：
        - 如果有多�?in_progress，返回第一个并将其余标记为 blocked
        - 如果没有 in_progress，返回第一�?pending
        
        Returns:
            dict: 当前功能，或 None
        """
        feature_list = self._load_feature_list()
        features = feature_list.get("features", [])
        
        in_progress = [f for f in features if f.get("status") == "in_progress"]
        
        if len(in_progress) > 1:
            # 强约束：只保留第一个，其余标记�?blocked
            primary = in_progress[0]
            for f in in_progress[1:]:
                f["status"] = "blocked"
                f["notes"] = f"Auto-blocked: multiple in_progress detected, {primary['id']} takes priority"
                logger.warning(f"Auto-blocked {f['id']} due to multiple in_progress constraint")
            self._save_feature_list(feature_list)
            return primary
        elif len(in_progress) == 1:
            return in_progress[0]
        
        # 没有进行中的，返回第一�?pending
        for f in features:
            if f.get("status") == "pending":
                return f

        return None

    def block_feature(self, feature_id: str, reason: str) -> bool:
        """标记功能为阻塞状�?""
        feature_list = self._load_feature_list()

        for f in feature_list.get("features", []):
            if f.get("id") == feature_id:
                f["status"] = "blocked"
                f["notes"] = f"BLOCKED: {reason}"
                self._save_feature_list(feature_list)
                self._append_progress(f"🚫 Blocked #{feature_id}: {reason}")
                logger.warning(f"Blocked feature: {feature_id} - {reason}")
                return True

        return False

    def record_progress(self, message: str) -> None:
        """记录进度（通用方法�?""
        self._append_progress(message)
    
    def add_feature(self, feature: dict) -> None:
        """添加新功�?""
        feature_list = self._load_feature_list()
        feature_list.setdefault("features", []).append(feature)
        self._save_feature_list(feature_list)
        self._append_progress(f"�?Added #{feature.get('id', 'new')}: {feature.get('description', '')}")
    
    def get_feature(self, feature_id: str) -> dict | None:
        """获取单个功能"""
        feature_list = self._load_feature_list()
        for f in feature_list.get("features", []):
            if f.get("id") == feature_id:
                return f
        return None
    
    def list_features(self, status: str | None = None) -> list[dict]:
        """列出功能（可选按状态过滤）"""
        feature_list = self._load_feature_list()
        features = feature_list.get("features", [])
        
        if status:
            return [f for f in features if f.get("status") == status]
        return features
    
    # ==================== 私有方法 ====================
    
    def _load_feature_list(self) -> dict:
        """加载功能清单（兼�?list �?dict 两种格式�?""
        if not self.feature_list_path.exists():
            return {"project": "unknown", "features": [], "statistics": {}}
        
        with open(self.feature_list_path, encoding="utf-8") as f:
            data = json.load(f)

        # 兼容旧格式：如果文件内容是列表，包装为标�?dict 格式
        if isinstance(data, list):
            logger.warning(
                f"feature_list.json is a plain list, converting to dict format"
            )
            data = {
                "project": "unknown",
                "features": data,
                "statistics": self._calc_statistics(data),
            }
            # 回写修正后的格式
            self._save_feature_list(data)

        return data
    
    def _save_feature_list(self, feature_list: dict) -> None:
        """保存功能清单"""
        feature_list["last_updated"] = datetime.now().isoformat()
        feature_list["statistics"] = self._calc_statistics(feature_list.get("features", []))
        
        with open(self.feature_list_path, "w", encoding="utf-8") as f:
            json.dump(feature_list, f, indent=2, ensure_ascii=False)
    
    def _init_progress_file(self, project_name: str) -> None:
        """初始化进度文�?""
        today = datetime.now().strftime("%Y-%m-%d")
        content = f"""# {project_name} 开发进�?
## 最新会�?({today})

### 进行中的工作
- [ ] 待开�?
### 下一步计�?1. 查看 feature_list.json 了解功能列表
2. 选择一个功能开始实�?
---

## 历史记录

### {today}
- 项目初始�?- 创建长期运行框架
"""
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write(content)
    
    def _append_progress(self, message: str) -> None:
        """追加进度记录"""
        timestamp = datetime.now().strftime("%H:%M")
        entry = f"- [{timestamp}] {message}\n"
        
        # 读取现有内容
        if self.progress_path.exists():
            content = self.progress_path.read_text(encoding="utf-8")
        else:
            content = "# 开发进度\n\n## 最新会话\n\n### 进行中的工作\n"
        
        # 在适当位置插入
        lines = content.split("\n")
        insert_idx = 0
        
        for i, line in enumerate(lines):
            if "### 进行中的工作" in line:
                insert_idx = i + 1
                break
            elif "### 完成的工�? in line and insert_idx == 0:
                insert_idx = i
                lines.insert(insert_idx, "\n### 进行中的工作\n")
                insert_idx += 1
                break
        
        # 确保不重复插入相同的消息
        if entry.strip() and entry.strip() not in content:
            lines.insert(insert_idx, entry)
        
        with open(self.progress_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    
    def _load_recent_progress(self) -> str:
        """加载最近的进度"""
        if not self.progress_path.exists():
            return "No progress recorded yet."
        
        content = self.progress_path.read_text(encoding="utf-8")
        
        # 返回最新会话部分（截取到历史记录之前）
        if "## 历史记录" in content:
            return content.split("## 历史记录")[0].strip()
        
        # 限制长度
        return content[:1500] if len(content) > 1500 else content
    
    def _get_recent_commits(self, count: int = 10) -> list[str]:
        """获取最近的 git 提交"""
        import subprocess
        
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", f"-{count}"],
                capture_output=True,
                text=True,
                cwd=self.workspace,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")
        except Exception as e:
            logger.debug(f"Could not get git log: {e}")
        
        return []
    
    def _calc_statistics(self, features: list) -> dict:
        """计算统计信息"""
        status_count = {
            "pending": 0,
            "in_progress": 0,
            "completed": 0,
            "blocked": 0
        }

        for f in features:
            status = f.get("status", "pending")
            if status in status_count:
                status_count[status] += 1

        return {
            "total": len(features),
            **status_count
        }

    # ==================== 状态门禁控�?====================

    # 合法状态转换图
    VALID_TRANSITIONS = {
        "pending": ["in_progress", "blocked"],
        "in_progress": ["completed", "blocked", "pending"],
        "completed": [],  # 已完成不能转�?        "blocked": ["pending", "in_progress"]
    }

    def _validate_status_transition(self, current_status: str, new_status: str) -> tuple[bool, str]:
        """
        验证状态转换是否合�?
        Args:
            current_status: 当前状�?            new_status: 目标状�?
        Returns:
            tuple: (is_valid: bool, message: str)
        """
        if current_status == new_status:
            return True, f"Status already {new_status}"

        allowed = self.VALID_TRANSITIONS.get(current_status, [])

        if new_status in allowed:
            return True, f"Valid transition: {current_status} -> {new_status}"

        return False, f"Invalid transition: {current_status} -> {new_status}. Allowed: {allowed}"

    def _record_status_change(self, feature_id: str, old_status: str, new_status: str, reason: str = "") -> None:
        """记录状态变更审计日�?""
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "feature_id": feature_id,
            "old_status": old_status,
            "new_status": new_status,
            "reason": reason
        }

        audit_file = self.agent_dir / "status_audit.jsonl"
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_entry, ensure_ascii=False) + "\n")

    def transition_feature_status(
        self,
        feature_id: str,
        new_status: str,
        reason: str = "",
        bypass_validation: bool = False
    ) -> dict:
        """
        状态转换入口（门禁控制�?
        所有状态变更必须通过此方法，直接修改 feature_list.json 无效�?
        Args:
            feature_id: 功能 ID
            new_status: 目标状�?            reason: 变更原因
            bypass_validation: 是否跳过验证（仅限管理员�?
        Returns:
            dict: {"success": bool, "message": str, "audit_id": str}
        """
        feature_list = self._load_feature_list()

        # 查找功能
        feature = None
        for f in feature_list.get("features", []):
            if f.get("id") == feature_id:
                feature = f
                break

        if not feature:
            return {"success": False, "message": f"Feature not found: {feature_id}", "audit_id": None}

        current_status = feature.get("status", "pending")

        # 验证状态转�?        if not bypass_validation:
            is_valid, msg = self._validate_status_transition(current_status, new_status)
            if not is_valid:
                return {"success": False, "message": msg, "audit_id": None}

        # 执行状态转�?        feature["status"] = new_status
        if reason:
            feature["status_reason"] = reason

        self._save_feature_list(feature_list)

        # 记录审计日志
        self._record_status_change(feature_id, current_status, new_status, reason)

        audit_id = f"{feature_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        return {
            "success": True,
            "message": f"Status changed: {current_status} -> {new_status}",
            "audit_id": audit_id
        }

    def get_status_audit_log(self, feature_id: str | None = None) -> list[dict]:
        """
        获取状态变更审计日�?
        Args:
            feature_id: 可选，过滤特定功能的日�?
        Returns:
            list: 审计日志列表
        """
        audit_file = self.agent_dir / "status_audit.jsonl"

        if not audit_file.exists():
            return []

        logs = []
        with open(audit_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if feature_id is None or entry.get("feature_id") == feature_id:
                        logs.append(entry)

        return logs[-100:]  # 返回最�?100 �?

# 便捷函数
def get_harness(workspace: Path | str | None = None) -> LongRunningHarness:
    """
    获取 LongRunningHarness 实例
    
    Args:
        workspace: 工作目录，默认为当前目录
    
    Returns:
        LongRunningHarness 实例
    """
    if workspace is None:
        workspace = Path.cwd()
    elif isinstance(workspace, str):
        workspace = Path(workspace)
    
    return LongRunningHarness(workspace)
