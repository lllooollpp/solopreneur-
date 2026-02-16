"""Repository and code search tools for software engineering workflows."""

from __future__ import annotations

import asyncio
import re
import shutil
from pathlib import Path
from typing import Any

from solopreneur.agent.core.tools.base import Tool


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

    # 类级别缓�?git 路径
    _git_path: str | None = None

    def __init__(self, workspace: Path, timeout: int = 30):
        self.workspace = workspace.resolve()
        self.timeout = timeout
        # 查找 git 可执行文件路�?
        if GitInspectTool._git_path is None:
            GitInspectTool._git_path = shutil.which("git")

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
        git_cmd = GitInspectTool._git_path or "git"
        try:
            # Windows 兼容性：确保使用正确的路径分隔符
            cwd = str(self.workspace).replace("/", "\\") if "\\" in str(self.workspace) else str(self.workspace)

            proc = await asyncio.create_subprocess_exec(
                git_cmd,
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            stdout = out.decode("utf-8", errors="replace")
            stderr = err.decode("utf-8", errors="replace")
            return proc.returncode == 0, (stdout or stderr).strip()
        except asyncio.TimeoutError:
            return False, f"git command timed out after {self.timeout}s"
        except FileNotFoundError:
            return False, "git command not found. Please install git and ensure it's in PATH."
        except PermissionError as e:
            return False, f"Permission denied: {e}"
        except Exception as e:
            return False, f"Failed to run git: {type(e).__name__}: {e}"


class GitCommandTool(Tool):
    """
    Git 命令工具 - 支持常用�?git 写操作�?

    提供 init、add、commit、push、pull 等常用操作，
    自动处理 git 仓库初始化和常见错误�?
    """

    def __init__(self, workspace: Path, timeout: int = 60):
        self.workspace = workspace.resolve()
        self.timeout = timeout
        # 使用 GitInspectTool �?git 路径缓存
        if GitInspectTool._git_path is None:
            GitInspectTool._git_path = shutil.which("git")

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return """Execute git commands for version control operations.

Supported actions:
- init: Initialize a new git repository
- add: Stage files for commit (use '.' for all, or specify paths)
- commit: Create a commit with a message
- push: Push to remote (requires remote setup)
- pull: Pull from remote
- checkout: Switch branches or restore files
- branch: Create or list branches

Auto-handles: git config user.name/email if not set."""

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["init", "add", "commit", "push", "pull", "checkout", "branch", "remote", "config"],
                    "description": "Git action to perform",
                },
                "files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Files to add (for 'add' action). Use ['.'] for all files.",
                },
                "message": {
                    "type": "string",
                    "description": "Commit message (for 'commit' action)",
                },
                "branch": {
                    "type": "string",
                    "description": "Branch name (for 'checkout', 'branch' actions)",
                },
                "remote_name": {
                    "type": "string",
                    "description": "Remote name (default: origin)",
                },
                "remote_url": {
                    "type": "string",
                    "description": "Remote URL (for 'remote add' action)",
                },
                "create_branch": {
                    "type": "boolean",
                    "description": "Create new branch when checkout (default: false)",
                },
                "set_upstream": {
                    "type": "boolean",
                    "description": "Set upstream for push (default: false)",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        files: list[str] | None = None,
        message: str | None = None,
        branch: str | None = None,
        remote_name: str = "origin",
        remote_url: str | None = None,
        create_branch: bool = False,
        set_upstream: bool = False,
        **kwargs: Any,
    ) -> str:
        # 检�?git 是否可用
        ok, _ = await self._run_git(["--version"])
        if not ok:
            return "Error: git command not found. Please install git first."

        # 处理不同操作
        if action == "init":
            return await self._init_repo()
        elif action == "add":
            return await self._add_files(files or ["."])
        elif action == "commit":
            return await self._commit(message)
        elif action == "push":
            return await self._push(branch, set_upstream)
        elif action == "pull":
            return await self._pull()
        elif action == "checkout":
            return await self._checkout(branch, create_branch)
        elif action == "branch":
            return await self._branch_action(branch)
        elif action == "remote":
            return await self._remote_action(remote_name, remote_url)
        elif action == "config":
            return await self._config_user()
        else:
            return f"Error: unsupported action: {action}"

    async def _is_git_repo(self) -> bool:
        ok, result = await self._run_git(["rev-parse", "--is-inside-work-tree"])
        return ok and "true" in result.lower()

    async def _init_repo(self) -> str:
        """初始�?git 仓库"""
        if await self._is_git_repo():
            return f"Git repository already exists at {self.workspace}"

        ok, result = await self._run_git(["init"])
        if not ok:
            return f"Error: Failed to initialize git repository: {result}"

        # 自动配置用户信息
        await self._config_user()

        return f"Git repository initialized at {self.workspace}"

    async def _config_user(self) -> str:
        """配置 git 用户信息"""
        # 检查是否已配置
        ok_name, name = await self._run_git(["config", "user.name"])
        ok_email, email = await self._run_git(["config", "user.email"])

        if ok_name and ok_email and name and email:
            return f"Git user already configured: {name} <{email}>"

        # 使用默认�?
        await self._run_git(["config", "user.name", "Nanobot"])
        await self._run_git(["config", "user.email", "nanobot@local"])
        return "Git user configured: Nanobot <nanobot@local>"

    async def _add_files(self, files: list[str]) -> str:
        """添加文件到暂存区"""
        if not await self._is_git_repo():
            init_result = await self._init_repo()
            if "Error" in init_result:
                return init_result

        # 验证文件路径
        safe_files = []
        for f in files:
            if f == ".":
                safe_files.append(".")
            else:
                safe_path = self._safe_relpath(f)
                if safe_path:
                    safe_files.append(safe_path)
                else:
                    return f"Error: Invalid file path: {f}"

        ok, result = await self._run_git(["add", *safe_files])
        if not ok:
            return f"Error: git add failed: {result}"

        # 显示暂存状�?
        ok, status = await self._run_git(["status", "--short"])
        staged = [line for line in status.split("\n") if line.strip() and line.strip()[0] in "MADRC"]
        return f"Files staged for commit ({len(staged)} files):\n{status}" if staged else "No changes to stage"

    async def _commit(self, message: str | None) -> str:
        """创建提交"""
        if not await self._is_git_repo():
            return "Error: Not a git repository. Run 'git init' first."

        if not message:
            return "Error: Commit message is required."

        # 检查是否有暂存的更�?
        ok, status = await self._run_git(["status", "--short"])
        staged = [line for line in status.split("\n") if line.strip() and line.strip()[0] in "MADRC"]
        if not staged:
            return "Nothing to commit. Use 'git add' to stage files first."

        ok, result = await self._run_git(["commit", "-m", message])
        if not ok:
            return f"Error: git commit failed: {result}"

        return f"Committed successfully: {message}"

    async def _push(self, branch: str | None, set_upstream: bool) -> str:
        """推送到远程"""
        if not await self._is_git_repo():
            return "Error: Not a git repository."

        # 获取当前分支
        ok, current_branch = await self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        if not ok:
            return "Error: Cannot determine current branch."
        current_branch = current_branch.strip()
        target_branch = branch or current_branch

        args = ["push"]
        if set_upstream:
            args.extend(["-u", "origin", target_branch])
        else:
            args.extend(["origin", target_branch])

        ok, result = await self._run_git(args)
        if not ok:
            return f"Error: git push failed: {result}\nTip: You may need to set up remote first with 'git remote add origin <url>'"

        return f"Pushed to origin/{target_branch}"

    async def _pull(self) -> str:
        """从远程拉�?""
        if not await self._is_git_repo():
            return "Error: Not a git repository."

        ok, result = await self._run_git(["pull"])
        if not ok:
            return f"Error: git pull failed: {result}"

        return f"Pulled successfully: {result}" if result else "Already up to date."

    async def _checkout(self, branch: str | None, create: bool) -> str:
        """切换分支"""
        if not await self._is_git_repo():
            return "Error: Not a git repository."

        if not branch:
            return "Error: Branch name is required."

        args = ["checkout"]
        if create:
            args.extend(["-b", branch])
        else:
            args.append(branch)

        ok, result = await self._run_git(args)
        if not ok:
            return f"Error: git checkout failed: {result}"

        return f"Switched to branch '{branch}'" + (" (created)" if create else "")

    async def _branch_action(self, branch: str | None) -> str:
        """分支操作"""
        if not await self._is_git_repo():
            return "Error: Not a git repository."

        if branch:
            # 创建新分�?
            ok, result = await self._run_git(["branch", branch])
            if not ok:
                return f"Error: git branch failed: {result}"
            return f"Branch '{branch}' created."
        else:
            # 列出所有分�?
            ok, result = await self._run_git(["branch", "-a"])
            if not ok:
                return f"Error: git branch failed: {result}"
            return f"Branches:\n{result}"

    async def _remote_action(self, name: str, url: str | None) -> str:
        """远程仓库操作"""
        if not await self._is_git_repo():
            return "Error: Not a git repository."

        if url:
            # 添加远程仓库
            ok, result = await self._run_git(["remote", "add", name, url])
            if not ok:
                return f"Error: git remote add failed: {result}"
            return f"Remote '{name}' added: {url}"
        else:
            # 列出远程仓库
            ok, result = await self._run_git(["remote", "-v"])
            if not ok:
                return f"Error: git remote failed: {result}"
            return f"Remotes:\n{result}" if result else "No remotes configured."

    def _safe_relpath(self, raw_path: str) -> str | None:
        try:
            candidate = (self.workspace / raw_path).resolve()
            candidate.relative_to(self.workspace)
            return candidate.relative_to(self.workspace).as_posix()
        except Exception:
            return None

    async def _run_git(self, args: list[str]) -> tuple[bool, str]:
        git_cmd = GitInspectTool._git_path or "git"
        try:
            # Windows 兼容性：确保使用正确的路径分隔符
            cwd = str(self.workspace).replace("/", "\\") if "\\" in str(self.workspace) else str(self.workspace)

            proc = await asyncio.create_subprocess_exec(
                git_cmd,
                *args,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            stdout = out.decode("utf-8", errors="replace")
            stderr = err.decode("utf-8", errors="replace")
            return proc.returncode == 0, (stdout or stderr).strip()
        except asyncio.TimeoutError:
            return False, f"git command timed out after {self.timeout}s"
        except FileNotFoundError:
            return False, "git command not found. Please install git and ensure it's in PATH."
        except PermissionError as e:
            return False, f"Permission denied: {e}"
        except Exception as e:
            return False, f"Failed to run git: {type(e).__name__}: {e}"
