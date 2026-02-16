"""
Harness 工具 - 管理长期运行任务的 Feature List

基于 Anthropic "Effective harnesses for long-running agents" 设计理念。
让 AI 能够初始化和管理 feature list，确保任务完整执行。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from solopreneur.agent.core.tools.base import Tool
from solopreneur.agent.core.harness import LongRunningHarness


class HarnessTool(Tool):
    """
    Harness 工具 - 管理长期运行任务的 Feature List

    支持：
    - init: 初始化 feature list（首次运行时调用）
    - status: 查看当前 feature 状态
    - start: 开始一个 feature
    - complete: 完成一个 feature
    - list: 列出所有 features
    """

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()
        self._harness: LongRunningHarness | None = None

    @property
    def harness(self) -> LongRunningHarness:
        if self._harness is None:
            self._harness = LongRunningHarness(self.workspace)
        return self._harness

    @property
    def name(self) -> str:
        return "harness"

    @property
    def description(self) -> str:
        return """Manage long-running task features and progress.

This tool helps you work incrementally and track completion status.

Actions:
- init: Initialize feature list for a project (call once at start)
- status: Get current progress and next feature to work on
- start: Mark a feature as in-progress (only one at a time)
- complete: Mark a feature as completed (requires testing)
- list: Show all features and their status

Important: Use 'init' action first for any complex multi-step project.
This creates a feature_list.json to track progress and ensure completion."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["init", "status", "start", "complete", "list"],
                    "description": "Action to perform",
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name (for 'init' action)",
                },
                "features": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Initial features list (for 'init' action). Each feature should have: id, category, priority, description, steps, test_criteria",
                },
                "feature_id": {
                    "type": "string",
                    "description": "Feature ID (for 'start' and 'complete' actions)",
                },
                "notes": {
                    "type": "string",
                    "description": "Notes for completion (for 'complete' action)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        project_name: str | None = None,
        features: list[dict] | None = None,
        feature_id: str | None = None,
        notes: str | None = None,
        **kwargs: Any,
    ) -> str:
        if action == "init":
            return self._init(project_name, features)
        elif action == "status":
            return self._status()
        elif action == "start":
            return self._start(feature_id)
        elif action == "complete":
            return self._complete(feature_id, notes)
        elif action == "list":
            return self._list()
        else:
            return f"Error: Unknown action: {action}"

    def _init(self, project_name: str | None, features: list[dict] | None) -> str:
        """初始化 feature list"""
        if self.harness.is_initialized():
            return "Harness already initialized. Use 'status' to see current progress."

        if not project_name:
            project_name = self.workspace.name

        if not features:
            # 生成默认的 feature 模板
            features = [
                {
                    "id": "FEAT-001",
                    "category": "setup",
                    "priority": "P0",
                    "description": "项目初始化和环境配置",
                    "steps": ["创建项目结构", "配置开发环境", "初始化依赖"],
                    "test_criteria": "项目可以正常运行",
                    "status": "pending",
                }
            ]

        try:
            self.harness.initialize(project_name, features)
            return f"✅ Harness initialized for '{project_name}'\n\n" \
                   f"Features created: {len(features)}\n" \
                   f"Use 'harness status' to see next steps.\n" \
                   f"Use 'harness start FEAT-XXX' to begin working on a feature."
        except Exception as e:
            return f"Error initializing harness: {e}"

    def _status(self) -> str:
        """获取当前状态"""
        if not self.harness.is_initialized():
            return "⚠️ Harness not initialized.\n\n" \
                   "For complex multi-step projects, use 'harness init' first to create a feature list.\n" \
                   "This helps track progress and ensures all tasks are completed."

        context = self.harness.get_session_context()

        lines = [
            f"## Project: {context.get('project', 'Unknown')}",
            f"Version: {context.get('version', '0.0.0')}",
            "",
        ]

        stats = context.get("statistics", {})
        if stats:
            lines.append(f"### Statistics")
            lines.append(f"- Total: {stats.get('total', 0)}")
            lines.append(f"- Completed: {stats.get('completed', 0)}")
            lines.append(f"- In Progress: {stats.get('in_progress', 0)}")
            lines.append(f"- Pending: {stats.get('pending', 0)}")
            lines.append("")

        current = context.get("current_feature")
        if current:
            lines.append(f"### Current Feature: {current.get('id')}")
            lines.append(f"- Description: {current.get('description')}")
            lines.append(f"- Status: {current.get('status')}")
            lines.append("")

        next_steps = context.get("next_steps", [])
        if next_steps:
            lines.append("### Next Steps")
            for i, step in enumerate(next_steps[:3], 1):
                lines.append(f"{i}. {step}")
            lines.append("")

        return "\n".join(lines)

    def _start(self, feature_id: str | None) -> str:
        """开始一个 feature"""
        if not self.harness.is_initialized():
            return "Error: Harness not initialized. Use 'harness init' first."

        if not feature_id:
            # 自动选择下一个 pending 的 feature
            context = self.harness.get_session_context()
            pending = context.get("statistics", {}).get("pending", 0)
            if pending == 0:
                return "No pending features. All features completed!"

            # 获取第一个 pending feature
            feature_list = self.harness._load_feature_list()
            for f in feature_list.get("features", []):
                if f.get("status") == "pending":
                    feature_id = f.get("id")
                    break

        if not feature_id:
            return "Error: No feature ID provided and no pending features found."

        try:
            self.harness.start_feature(feature_id)
            feature = self.harness.get_feature(feature_id)
            return f"✅ Started feature: {feature_id}\n\n" \
                   f"Description: {feature.get('description', 'N/A')}\n" \
                   f"Steps:\n" + "\n".join(f"  - {s}" for s in feature.get("steps", []))
        except Exception as e:
            return f"Error starting feature: {e}"

    def _complete(self, feature_id: str | None, notes: str | None) -> str:
        """完成一个 feature"""
        if not self.harness.is_initialized():
            return "Error: Harness not initialized."

        if not feature_id:
            # 获取当前 in_progress 的 feature
            features = self.harness.get_features_by_status("in_progress")
            if not features:
                return "Error: No feature in progress. Start one first with 'harness start'."
            feature_id = features[0].get("id")

        try:
            self.harness.complete_feature(feature_id, notes or "Completed")
            stats = self.harness._load_feature_list().get("statistics", {})

            result = f"✅ Completed feature: {feature_id}\n\n"
            result += f"Progress: {stats.get('completed', 0)}/{stats.get('total', 0)} completed\n"

            if stats.get("pending", 0) > 0:
                result += f"\nNext: Use 'harness start' to continue with remaining features."
            else:
                result += f"\n🎉 All features completed!"

            return result
        except Exception as e:
            return f"Error completing feature: {e}"

    def _list(self) -> str:
        """列出所有 features"""
        if not self.harness.is_initialized():
            return "Harness not initialized. Use 'harness init' first."

        feature_list = self.harness._load_feature_list()
        features = feature_list.get("features", [])

        lines = ["## Feature List", ""]

        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "blocked": "🚫",
        }

        for f in features:
            emoji = status_emoji.get(f.get("status", "pending"), "❓")
            lines.append(f"{emoji} **{f.get('id')}**: {f.get('description')}")
            lines.append(f"   - Status: {f.get('status')}")
            lines.append(f"   - Priority: {f.get('priority', 'N/A')}")
            lines.append("")

        return "\n".join(lines)
