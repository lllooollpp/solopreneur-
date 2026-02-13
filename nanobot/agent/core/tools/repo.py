"""Repository and code search tools for software engineering workflows."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

from nanobot.agent.core.tools.base import Tool


_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".php", ".rb", ".swift", ".kt", ".kts", ".scala", ".sql", ".md", ".yaml", ".yml",
    ".json", ".toml", ".ini", ".cfg", ".txt", ".xml", ".html", ".css", ".scss", ".vue", ".sh",
    ".ps1", ".bat", ".dockerfile",
}


class SearchCodeTool(Tool):
    """Search text in workspace files with optional regex."""

    def __init__(self, workspace: Path, max_file_size: int = 1_000_000):
        self.workspace = workspace.resolve()
        self.max_file_size = max_file_size

    @property
    def name(self) -> str:
        return "search_code"

    @property
    def description(self) -> str:
        return "Search code/files in workspace by keyword or regex and return file:line matches."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword or regex pattern to search"},
                "path": {"type": "string", "description": "Optional relative path under workspace"},
                "is_regex": {"type": "boolean", "description": "Treat query as regex", "default": False},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
            },
            "required": ["query"],
        }

    async def execute(
        self,
        query: str,
        path: str | None = None,
        is_regex: bool = False,
        max_results: int = 50,
        **kwargs: Any,
    ) -> str:
        if not query.strip():
            return "Error: query cannot be empty"

        base = self.workspace
        if path:
            candidate = (self.workspace / path).resolve()
            try:
                candidate.relative_to(self.workspace)
            except ValueError:
                return "Error: path must be inside workspace"
            if not candidate.exists():
                return f"Error: path not found: {path}"
            base = candidate

        pattern: re.Pattern[str] | None = None
        if is_regex:
            try:
                pattern = re.compile(query, re.IGNORECASE)
            except re.error as e:
                return f"Error: invalid regex: {e}"

        matches: list[str] = []
        files_scanned = 0

        targets = [base] if base.is_file() else base.rglob("*")
        for p in targets:
            if len(matches) >= max_results:
                break
            if p.is_dir():
                continue
            if p.suffix.lower() not in _TEXT_EXTENSIONS and p.name.lower() != "dockerfile":
                continue
            try:
                if p.stat().st_size > self.max_file_size:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            files_scanned += 1
            for idx, line in enumerate(text.splitlines(), start=1):
                ok = bool(pattern.search(line)) if pattern else (query.lower() in line.lower())
                if ok:
                    rel = p.relative_to(self.workspace).as_posix()
                    snippet = line.strip()
                    if len(snippet) > 220:
                        snippet = snippet[:220] + "..."
                    matches.append(f"{rel}:{idx}: {snippet}")
                    if len(matches) >= max_results:
                        break

        if not matches:
            return f"No matches for '{query}'. scanned_files={files_scanned}"

        return "\n".join([
            f"Found {len(matches)} matches (scanned_files={files_scanned}):",
            *matches,
        ])


class GitInspectTool(Tool):
    """Read-only git inspection tool."""

    def __init__(self, workspace: Path, timeout: int = 30):
        self.workspace = workspace.resolve()
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "git_inspect"

    @property
    def description(self) -> str:
        return "Inspect git repository state (status/diff/log/branches/current_branch) in a safe read-only way."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "diff", "log", "branches", "current_branch"],
                    "description": "Inspection action",
                },
                "path": {"type": "string", "description": "Optional relative file path for diff"},
                "max_count": {"type": "integer", "minimum": 1, "maximum": 200, "default": 30},
                "staged": {"type": "boolean", "description": "Use staged diff", "default": False},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        path: str | None = None,
        max_count: int = 30,
        staged: bool = False,
        **kwargs: Any,
    ) -> str:
        ok, msg = await self._run_git(["rev-parse", "--is-inside-work-tree"])
        if not ok or "true" not in msg.lower():
            return "Error: current workspace is not a git repository"

        cmd: list[str]
        if action == "status":
            cmd = ["status", "--short", "--branch"]
        elif action == "diff":
            cmd = ["diff"]
            if staged:
                cmd.append("--staged")
            if path:
                safe_path = self._safe_relpath(path)
                if not safe_path:
                    return "Error: path must be inside workspace"
                cmd.extend(["--", safe_path])
        elif action == "log":
            cmd = ["log", "--oneline", f"-n{max_count}"]
        elif action == "branches":
            cmd = ["branch", "--all"]
        elif action == "current_branch":
            cmd = ["rev-parse", "--abbrev-ref", "HEAD"]
        else:
            return f"Error: unsupported action: {action}"

        ok, output = await self._run_git(cmd)
        if not ok:
            return f"Error: git {action} failed: {output}"

        if not output.strip():
            return "(no output)"
        if len(output) > 12000:
            output = output[:12000] + "\n... (truncated)"
        return output

    def _safe_relpath(self, raw_path: str) -> str | None:
        try:
            candidate = (self.workspace / raw_path).resolve()
            candidate.relative_to(self.workspace)
            return candidate.relative_to(self.workspace).as_posix()
        except Exception:
            return None

    async def _run_git(self, args: list[str]) -> tuple[bool, str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=str(self.workspace),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            stdout = out.decode("utf-8", errors="replace")
            stderr = err.decode("utf-8", errors="replace")
            return proc.returncode == 0, (stdout or stderr).strip()
        except asyncio.TimeoutError:
            return False, f"git command timed out after {self.timeout}s"
        except Exception as e:
            return False, str(e)
