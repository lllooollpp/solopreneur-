"""Project environment variable tools."""

import json
from pathlib import Path
from typing import Any

from solopreneur.agent.core.tools.base import Tool
from solopreneur.projects import ProjectManager, ProjectEnvVar


class GetProjectEnvTool(Tool):
    """Read project-level environment variables."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "get_project_env"

    @property
    def description(self) -> str:
        return "Get project environment variables for the current project. Optionally filter by key."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Optional env variable key, e.g. DB_HOST",
                }
            },
            "required": [],
        }

    async def execute(self, key: str | None = None, **kwargs: Any) -> str:
        manager = ProjectManager()
        project = manager.get_project_by_path(self.workspace)
        if not project:
            return f"Error: No project matched current workspace path: {self.workspace}"

        env_vars = project.env_vars
        if key:
            env_vars = [item for item in env_vars if item.key == key]
            if not env_vars:
                return f"Error: Env var '{key}' not found in project '{project.name}'"

        payload = {
            "project_id": project.id,
            "project_name": project.name,
            "total": len(env_vars),
            "env_vars": [item.model_dump(mode="json") for item in env_vars],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)


class SetProjectEnvTool(Tool):
    """Upsert project-level environment variables."""

    def __init__(self, workspace: Path):
        self.workspace = workspace

    @property
    def name(self) -> str:
        return "set_project_env"

    @property
    def description(self) -> str:
        return "Upsert project environment variables for the current project. Existing keys will be replaced."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "env_vars": {
                    "type": "array",
                    "description": "Environment variables to upsert",
                    "items": {
                        "type": "object",
                        "properties": {
                            "key": {"type": "string"},
                            "value": {"type": "string"},
                            "category": {
                                "type": "string",
                                "enum": ["database", "registry", "server", "middleware", "credential", "general"],
                            },
                            "description": {"type": "string"},
                            "sensitive": {"type": "boolean"},
                        },
                        "required": ["key", "value"],
                    },
                }
            },
            "required": ["env_vars"],
        }

    async def execute(self, env_vars: list[dict[str, Any]], **kwargs: Any) -> str:
        manager = ProjectManager()
        project = manager.get_project_by_path(self.workspace)
        if not project:
            return f"Error: No project matched current workspace path: {self.workspace}"

        existing = {item.key: item for item in project.env_vars}

        try:
            for item in env_vars:
                parsed = ProjectEnvVar(**item)
                existing[parsed.key] = parsed
        except Exception as e:
            return f"Error: Invalid env_vars payload: {e}"

        updated = list(existing.values())
        project = manager.set_project_env_vars(project.id, updated)
        if not project:
            return "Error: Failed to update project env vars"

        payload = {
            "success": True,
            "project_id": project.id,
            "project_name": project.name,
            "total": len(project.env_vars),
            "message": f"Updated env vars in project '{project.name}'",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)
