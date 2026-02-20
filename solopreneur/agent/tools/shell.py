"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, Callable

from solopreneur.agent.tools.base import Tool


class ExecTool(Tool):
    """Tool to execute shell commands."""
    
    # 长期运行的服务型命令模式：这类命令不会退出，exec 工具无法等待其完成
    _SERVER_PATTERNS: list[tuple[str, str]] = [
        # npm/yarn/pnpm dev servers
        (r"\bnpm\s+(run\s+)?(start|dev|serve|preview)\b",
         "Use 'npm run build' to check compilation, or run the server in the background manually."),
        (r"\byarn\s+(run\s+)?(start|dev|serve|preview)\b",
         "Use 'yarn build' to check compilation, or run the server in the background manually."),
        (r"\bpnpm\s+(run\s+)?(start|dev|serve|preview)\b",
         "Use 'pnpm build' to check compilation, or run the server in the background manually."),
        # Common framework dev servers
        (r"\breact-scripts\s+start\b",
         "react-scripts start runs an indefinite dev server. Use 'react-scripts build' instead."),
        (r"\bnext\s+dev\b",
         "next dev runs an indefinite dev server. Use 'next build' to check compilation."),
        (r"\bvite(\s+dev)?\s*$",
         "vite dev runs an indefinite dev server. Use 'vite build' instead."),
        (r"\bvite\s+preview\b",
         "vite preview runs an indefinite HTTP server. Use 'vite build' to check compilation."),
        (r"\bnuxt\s+dev\b",
         "nuxt dev runs an indefinite dev server. Use 'nuxt build' instead."),
        (r"\bng\s+serve\b",
         "ng serve runs an indefinite dev server. Use 'ng build' to check compilation."),
        (r"\bvue-cli-service\s+serve\b",
         "vue-cli-service serve runs an indefinite dev server. Use 'vue-cli-service build' instead."),
        # Backend servers
        (r"\buvicorn\b(?!.*--workers\s*1.*--limit-max-requests)",
         "uvicorn starts an indefinite HTTP server that exec cannot await. Run it in the background separately."),
        (r"\bgunicorn\b",
         "gunicorn starts an indefinite HTTP server. Run it in the background separately."),
        (r"\bflask\s+run\b",
         "flask run starts an indefinite dev server. Run it in the background separately."),
        (r"\bdjango.*runserver\b",
         "runserver starts an indefinite dev server. Run it in the background separately."),
        (r"\bfastapi\s+dev\b",
         "fastapi dev starts an indefinite dev server. Run it in the background separately."),
        (r"\bpython\s+-m\s+http\.server\b",
         "http.server starts an indefinite HTTP server. Run it in the background separately."),
        # Watchers / long-running processes
        (r"\bnodemon\b",
         "nodemon is a file watcher that runs indefinitely. Run it in the background separately."),
        (r"\bnpm\s+run\s+watch\b",
         "'npm run watch' is a long-running process. Run it in the background separately."),
        (r"\btsc\s+(-w|--watch)\b",
         "tsc --watch runs indefinitely. Use 'tsc' (without --watch) for a one-shot compile check."),
    ]

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
            r"^(ls|dir|pwd|cd)\b",
            r"^(cat|head|tail|less|more)\b",
            r"^(grep|find|locate|which)\b",
            r"^(echo|printf)\b",
            r"^(git|hg|svn)\b",
            r"^(python[0-9]?|pip[0-9]?|node|npm|npx)\b",
            r"^(go|cargo|rustc|java|javac|mvn|gradle)\b",
            r"^(docker|kubectl|make|cmake)\b",
            r"^(gcc|g\+\+|clang)\b",
        ]
        
        self.restrict_to_workspace = restrict_to_workspace
        # 实时输出流回调（async callable，每行调用一次）
        self._stream_callback: Callable[[str], Any] | None = None

    def set_stream_callback(self, callback: Callable[[str], Any] | None) -> None:
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
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # 合并 stderr，按序流式输出
                cwd=cwd,
            )

            output_lines: list[str] = []
            cb = self._stream_callback

            async def _read_stream() -> None:
                assert process.stdout is not None
                async for raw_line in process.stdout:
                    line = raw_line.decode("utf-8", errors="replace")
                    output_lines.append(line)
                    if cb is not None:
                        try:
                            result = cb(line)
                            if asyncio.iscoroutine(result):
                                await result
                        except Exception:
                            pass

            try:
                await asyncio.wait_for(_read_stream(), timeout=self.timeout)
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout} seconds"

            await process.wait()

            result = "".join(output_lines) if output_lines else "(no output)"

            if process.returncode != 0:
                result += f"\nExit code: {process.returncode}"

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

        # 0. 检查长期运行的服务型命令（会导致 exec 永久阻塞）
        for pattern, hint in self._SERVER_PATTERNS:
            if re.search(pattern, lower):
                return (
                    f"Error: Command blocked — '{cmd}' starts a long-running server/watcher "
                    f"that never exits, which would cause exec to hang until timeout.\n"
                    f"Hint: {hint}"
                )

        # 1. 检查危险命令模式（黑名单）
        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return f"Error: Command blocked by safety guard (dangerous pattern detected: {pattern})"

        # 2. 白名单模式检查
        if self.whitelist_mode:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist). Enable only safe commands."

        # 3. 允许模式检查（如果指定了非空allow_patterns且不是白名单模式）
        if self.allow_patterns and not self.whitelist_mode:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

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
