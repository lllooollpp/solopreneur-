"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


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
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=self.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout} seconds"
            
            output_parts = []
            
            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))
            
            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")
            
            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")
            
            result = "\n".join(output_parts) if output_parts else "(no output)"
            
            # Truncate very long output
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
