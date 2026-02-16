"""Tool registry for dynamic tool management."""

import json
import re
from typing import Any

from solopreneur.agent.core.tools.base import Tool


class ToolRegistry:
    """
    Registry for agent tools.
    
    Allows dynamic registration and execution of tools.
    """
    
    def __init__(self):
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def unregister(self, name: str) -> None:
        """Unregister a tool by name."""
        self._tools.pop(name, None)
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools
    
    def get_definitions(self) -> list[dict[str, Any]]:
        """Get all tool definitions in OpenAI format."""
        return [tool.to_schema() for tool in self._tools.values()]
    
    async def execute(self, name: str, params: dict[str, Any]) -> str:
        """
        Execute a tool by name with given parameters.
        
        Args:
            name: Tool name.
            params: Tool parameters.
        
        Returns:
            Tool execution result as string.
        
        Raises:
            KeyError: If tool not found.
        """
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"

        try:
            params = self._normalize_params(params)
            errors = tool.validate_params(params)
            if errors:
                return f"Error: Invalid parameters for tool '{name}': " + "; ".join(errors)
            return await tool.execute(**params)
        except Exception as e:
            return f"Error executing {name}: {str(e)}"

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize tool params for malformed tool-call arguments.

        某些模型在函数调用参数里会返回：{"raw": "{...json...}"}
        这里尝试自动解包，减少因为参数格式轻微异常导致的工具失败�?
        """
        if not isinstance(params, dict):
            return params

        # 先移除显�?null 参数：模型常把可选字段输出为 null�?
        # 这会�?schema 校验阶段触发类型错误（如 string vs null）�?
        # 移除后可由工具内部默认上下文接管（例�?message �?channel/chat_id）�?
        params = {k: v for k, v in params.items() if v is not None}

        raw = params.get("raw")
        if not (isinstance(raw, str) and raw.strip()):
            return params

        # 仅当缺少其他关键参数时尝试解包，避免覆盖正常输入
        if len(params) > 1:
            return params

        text = raw.strip()

        # 去掉可能�?markdown 代码块包�?
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

        # 优先直接解析
        parsed = self._try_parse_json_object(text)
        if isinstance(parsed, dict):
            return parsed

        # 回退：提取第一�?{ ... } 再解�?
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start:end + 1]
            parsed = self._try_parse_json_object(snippet)
            if isinstance(parsed, dict):
                return parsed

        # 兜底：从破损 JSON 文本中提�?content 字段（常见于 message 工具�?
        recovered = self._extract_content_field(text)
        if recovered is not None:
            return {"content": recovered}

        return params

    @staticmethod
    def _try_parse_json_object(text: str) -> dict[str, Any] | None:
        try:
            obj = json.loads(text)
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None

    @staticmethod
    def _extract_content_field(text: str) -> str | None:
        """从破损参数字符串中提�?content 字段并反转义�?""
        m = re.search(r'"content"\s*:\s*"((?:\\.|[^"\\])*)"', text, re.DOTALL)
        if not m:
            return None

        raw_value = m.group(1)
        try:
            # 利用 JSON 反转义规则还原字符串
            return json.loads(f'"{raw_value}"')
        except Exception:
            # 最后兜底：粗略反转义常见字�?
            return (
                raw_value
                .replace(r"\\n", "\n")
                .replace(r"\\t", "\t")
                .replace(r'\\"', '"')
                .replace(r"\\\\", "\\")
            )
    
    @property
    def tool_names(self) -> list[str]:
        """Get list of registered tool names."""
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        return name in self._tools
