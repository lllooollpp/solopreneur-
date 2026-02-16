"""Shell execution tool."""

import asyncio
import functools
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from solopreneur.agent.core.tools.base import Tool


class ExecTool(Tool):
    """Tool to execute shell commands."""
    
    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        whitelist_mode: bool = False,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.whitelist_mode = whitelist_mode
        
        # 增强的危险命令模�?
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",          # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fqs]\b",             # del /f, del /q, del /s
            r"\brmdir\s+/s\b",               # rmdir /s
            r"\b(format|mkfs|diskpart)\b",   # disk operations
            r"\bdd\s+if=",                   # dd
            r">\s*/dev/sd",                  # write to disk
            r"\b(shutdown|reboot|poweroff|halt)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",          # fork bomb
            r"\|\s*sudo",                    # pipe to sudo
            r";\s*sudo",                     # semicolon sudo
            r"&&\s*sudo",                    # && sudo
            r"\$\(\s*(curl|wget)",           # command substitution download
            r"`(curl|wget)",                 # backtick download
            r"\b(chmod|chown)\s+[0-7]{3,4}", # permission changes
            r"\b(useradd|userdel|passwd|adduser)\b",  # user management
            r"\b(iptables|ufw|firewalld)\b", # firewall
            r"\beval\s+\$",                  # eval with variable
            r"\bexec\s+\$",                  # exec with variable
        ]
        
        # 安全命令白名单（仅在whitelist_mode=True时使用）
        self.allow_patterns = allow_patterns or [
            r"^(ls|dir|pwd|cd|type|Get-)\b",
            r"^(cat|head|tail|less|more|wc|sort|uniq)\b",
            r"^(grep|find|locate|which|where|rg|fd)\b",
            r"^(echo|printf|Write-Output)\b",
            r"^(git|hg|svn)\b",
            r"^(python[0-9]?|pip[0-9]?|node|npm|npx|pnpm|yarn|bun)\b",
            r"^(pytest|tox|coverage|mypy|ruff|flake8|black|isort)\b",
            r"^(playwright|jest|vitest|mocha|cypress)\b",
            r"^(go|cargo|rustc|java|javac|mvn|gradle|dotnet)\b",
            r"^(docker|kubectl|make|cmake|terraform|helm)\b",
            r"^(gcc|g\+\+|clang|rustup)\b",
            r"^(curl|wget|ssh|scp)\b",
            r"^(tar|zip|unzip|gzip)\b",
            r"^(mkdir|touch|cp|mv|ln)\b",
            r"^(env|set|export|printenv)\b",
            r"^(sed|awk|cut|tr|xargs)\b",
        ]
        
        self.restrict_to_workspace = restrict_to_workspace
    
    @property
    def name(self) -> str:
        return "exec"
    
    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command"
                }
            },
            "required": ["command"]
        }
    
    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        guard_error = self._guard_command(command, cwd)
        if guard_error:
            return guard_error
        
        try:
            # 使用 subprocess.run 在线程池中执行，避免 Windows SelectorEventLoop
            # 不支�?asyncio.create_subprocess_shell 的问�?
            # （uvicorn --reload 模式下使�?SelectorEventLoop�?
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                functools.partial(
                    self._run_command_sync, command, cwd
                ),
            )
            return result
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _run_command_sync(self, command: str, cwd: str) -> str:
        """在线程池中同步执行命令（兼容所有事件循环）�?""
        try:
            # �?Windows 上确保子进程继承 PATH
            env = os.environ.copy()
            if sys.platform == "win32":
                env.setdefault("PYTHONIOENCODING", "utf-8")

            proc = subprocess.run(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                timeout=self.timeout,
                env=env,
            )

            output_parts = []

            if proc.stdout:
                output_parts.append(proc.stdout.decode("utf-8", errors="replace"))

            if proc.stderr:
                stderr_text = proc.stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            if proc.returncode != 0:
                output_parts.append(f"\nExit code: {proc.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"

            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            return result

        except subprocess.TimeoutExpired:
            return f"Error: Command timed out after {self.timeout} seconds"
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def _guard_command(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        # 1. 检查危险命令模式（黑名单）
        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return f"Error: Command blocked by safety guard (dangerous pattern detected: {pattern})"

        # 2. 白名单模式检查（仅在 whitelist_mode=True 或用户显式传�?allow_patterns 时启用）
        if self.whitelist_mode:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist). Enable only safe commands."

        # 4. 工作空间限制检�?
        if self.restrict_to_workspace:
            # 路径遍历检�?
            if "..\\" in cmd or "../" in cmd or "/.." in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()

            # 提取路径并验�?
            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"'\s]+", cmd)
            posix_paths = re.findall(r"/[^\s\"']+", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw).resolve()
                    # 检查路径是否在工作目录�?
                    if cwd_path not in p.parents and p != cwd_path:
                        return f"Error: Command blocked by safety guard (path '{raw}' outside working dir)"
                except Exception:
                    continue

        return None
