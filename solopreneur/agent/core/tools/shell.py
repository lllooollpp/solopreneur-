"""Shell execution tool."""

import asyncio
import functools
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Callable

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
        console_stream: bool = True,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.whitelist_mode = whitelist_mode
        self.console_stream = console_stream
        
        # 增强的危险命令模式
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
        # 实时输出流回调（每行调用一次，从线程安全地推送到 async 侧）
        self._stream_callback: Callable[[str], None] | None = None

    def set_stream_callback(self, callback: Callable[[str], None] | None) -> None:
        """注入实时输出回调；传 None 则清除。"""
        self._stream_callback = callback
    
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
            # 不支持 asyncio.create_subprocess_shell 的问题
            # （uvicorn --reload 模式下使用 SelectorEventLoop）
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
        """在线程池中同步执行命令，逐行读取输出并通过回调实时推送。"""
        try:
            env = os.environ.copy()
            if sys.platform == "win32":
                env.setdefault("PYTHONIOENCODING", "utf-8")

            proc = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,   # stderr 合并进 stdout，便于按序流式输出
                cwd=cwd,
                env=env,
            )

            timed_out = threading.Event()

            def _kill_on_timeout() -> None:
                timed_out.set()
                proc.kill()

            timer = threading.Timer(self.timeout, _kill_on_timeout)
            cb = self._stream_callback
            output_lines: list[str] = []

            try:
                timer.start()
                assert proc.stdout is not None
                for raw_line in iter(proc.stdout.readline, b""):
                    line = raw_line.decode("utf-8", errors="replace")
                    output_lines.append(line)
                    if self.console_stream:
                        sys.stdout.write(line)
                        sys.stdout.flush()
                    if cb is not None:
                        try:
                            cb(line)
                        except Exception:
                            pass  # 回调异常不影响命令执行
                proc.stdout.close()
                proc.wait()
            finally:
                timer.cancel()

            if timed_out.is_set():
                return f"Error: Command timed out after {self.timeout} seconds"

            result = "".join(output_lines) if output_lines else "(no output)"

            if proc.returncode != 0:
                result += f"\nExit code: {proc.returncode}"

            # 截断超长输出
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            return result

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

        # 2. 白名单模式检查（仅在 whitelist_mode=True 或用户显式传入 allow_patterns 时启用）
        if self.whitelist_mode:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist). Enable only safe commands."

        # 4. 工作空间限制检查
        if self.restrict_to_workspace:
            # 路径遍历检测
            if "..\\" in cmd or "../" in cmd or "/.." in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            cwd_path = Path(cwd).resolve()

            # 提取路径并验证
            win_paths = re.findall(r"[A-Za-z]:\\[^\\\"'\s]+", cmd)
            posix_paths = re.findall(r"/[^\s\"']+", cmd)

            for raw in win_paths + posix_paths:
                try:
                    p = Path(raw).resolve()
                    # 检查路径是否在工作目录内
                    if cwd_path not in p.parents and p != cwd_path:
                        return f"Error: Command blocked by safety guard (path '{raw}' outside working dir)"
                except Exception:
                    continue

        return None
