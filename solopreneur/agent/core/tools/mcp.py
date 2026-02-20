"""MCP（Model Context Protocol）工具集成。

支持两种传输模式：
  - docker-stdio : 通过 `docker run -i <image>` 启动容器，JSON-RPC 经 stdin/stdout 传输
  - docker-sse   : 通过 `docker run -p <port>` 启动容器，JSON-RPC 经 HTTP SSE 传输
  - sse          : 连接已运行的 MCP HTTP 服务（无需 Docker）

典型配置（config.json）：
    "tools": {
      "mcp": {
        "servers": [
          {
            "name": "filesystem",
            "transport": "docker-stdio",
            "image": "mcp/filesystem",
            "docker_args": ["-v", "/home:/home:ro"],
            "env": {}
          },
          {
            "name": "github",
            "transport": "docker-stdio",
            "image": "ghcr.io/github/github-mcp-server:latest",
            "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"}
          },
          {
            "name": "my-service",
            "transport": "sse",
            "url": "http://localhost:3000"
          }
        ]
      }
    }
"""
from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, TYPE_CHECKING

import httpx
from loguru import logger

from solopreneur.agent.core.tools.base import Tool

if TYPE_CHECKING:
    from solopreneur.agent.core.tools.registry import ToolRegistry

# MCP 协议版本
MCP_PROTOCOL_VERSION = "2024-11-05"
# 单次工具调用默认超时（秒）
MCP_TOOL_TIMEOUT = 120.0
# 初始化握手超时（秒）
MCP_INIT_TIMEOUT = 30.0


class MCPError(Exception):
    """MCP 协议错误。"""


# ---------------------------------------------------------------------------
# Stdio 传输（Docker 容器 stdin/stdout）
# ---------------------------------------------------------------------------

class MCPStdioClient:
    """通过 Docker stdio 与 MCP 服务器通信。

    启动容器：`docker run --rm -i [docker_args] [-e K=V ...] <image> [cmd...]`
    JSON-RPC 消息以换行分割的 JSON 行格式传输。
    """

    def __init__(
        self,
        name: str,
        image: str,
        docker_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
    ) -> None:
        self.name = name
        self._image = image
        self._docker_args: list[str] = docker_args or []
        self._env: dict[str, str] = env or {}
        self._cmd: list[str] = cmd or []

        self._proc: asyncio.subprocess.Process | None = None
        self._tools: list[dict[str, Any]] = []
        self._req_id = 0
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._read_task: asyncio.Task | None = None
        # 用 asyncio.Lock 保护 _req_id 自增 + stdin 写入
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """启动 Docker 容器并完成 MCP 握手。"""
        docker_cmd = ["docker", "run", "--rm", "-i"] + self._docker_args
        for k, v in self._env.items():
            docker_cmd += ["-e", f"{k}={v}"]
        docker_cmd.append(self._image)
        docker_cmd += self._cmd

        logger.info(f"[MCP:{self.name}] 启动容器: {' '.join(docker_cmd)}")
        self._proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # 启动后台读取循环
        self._read_task = asyncio.get_event_loop().create_task(
            self._reader_loop(), name=f"mcp-read-{self.name}"
        )

        # MCP 握手
        init_resp = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "solopreneur", "version": "0.1.0"},
            },
            timeout=MCP_INIT_TIMEOUT,
        )
        logger.info(f"[MCP:{self.name}] 握手成功，server={init_resp.get('serverInfo', {})}")

        # 发送 initialized 通知（不需要等待响应）
        await self._notify("notifications/initialized")

        # 获取工具列表
        tools_resp = await self._request("tools/list", {}, timeout=MCP_INIT_TIMEOUT)
        self._tools = tools_resp.get("tools", [])
        logger.info(f"[MCP:{self.name}] 发现 {len(self._tools)} 个工具: "
                    f"{[t['name'] for t in self._tools]}")

    async def stop(self) -> None:
        """停止容器。"""
        if self._read_task and not self._read_task.done():
            self._read_task.cancel()
        if self._proc:
            try:
                self._proc.kill()
                await self._proc.wait()
            except Exception:
                pass
        logger.info(f"[MCP:{self.name}] 已停止")

    # ------------------------------------------------------------------
    # 内部通信
    # ------------------------------------------------------------------

    async def _reader_loop(self) -> None:
        """持续读取 stdout，将响应 dispatch 给等待的 Future。"""
        assert self._proc and self._proc.stdout
        try:
            async for raw in self._proc.stdout:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    data: dict = json.loads(line)
                except json.JSONDecodeError:
                    continue
                req_id = data.get("id")
                if req_id is not None:
                    fut = self._pending.pop(req_id, None)
                    if fut and not fut.done():
                        if "error" in data:
                            err = data["error"]
                            fut.set_exception(MCPError(
                                f"code={err.get('code')} {err.get('message', 'unknown')}"
                            ))
                        else:
                            fut.set_result(data.get("result", {}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[MCP:{self.name}] 读取循环异常: {e}")
        finally:
            # 取消所有还在等待的 Future
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    async def _write(self, payload: dict) -> None:
        assert self._proc and self._proc.stdin
        data = json.dumps(payload, ensure_ascii=False) + "\n"
        self._proc.stdin.write(data.encode("utf-8"))
        await self._proc.stdin.drain()

    async def _request(self, method: str, params: dict, timeout: float = MCP_TOOL_TIMEOUT) -> dict:
        async with self._write_lock:
            self._req_id += 1
            req_id = self._req_id
            loop = asyncio.get_event_loop()
            fut: asyncio.Future[dict] = loop.create_future()
            self._pending[req_id] = fut
            await self._write({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise MCPError(f"MCP 请求 '{method}' 超时（{timeout}s）")

    async def _notify(self, method: str, params: dict | None = None) -> None:
        async with self._write_lock:
            await self._write({"jsonrpc": "2.0", "method": method, "params": params or {}})

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_tools(self) -> list[dict[str, Any]]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict, timeout: float = MCP_TOOL_TIMEOUT) -> str:
        result = await self._request(
            "tools/call", {"name": name, "arguments": arguments}, timeout=timeout
        )
        content = result.get("content", [])
        parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# SSE 传输（HTTP Server-Sent Events）
# ---------------------------------------------------------------------------

class MCPSseClient:
    """通过 HTTP SSE 与 MCP 服务器通信。

    MCP SSE 传输协议：
      1. GET <base_url>/sse → SSE 流
      2. 服务器发送  event: endpoint\\ndata: <POST_URL>
      3. 客户端向 POST_URL 发送 JSON-RPC 请求
      4. 服务器通过 SSE 流返回响应
    """

    def __init__(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._base_url = url.rstrip("/")
        self._headers: dict[str, str] = headers or {}
        self._post_url: str | None = None
        self._tools: list[dict[str, Any]] = []
        self._client: httpx.AsyncClient | None = None
        self._sse_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future[dict]] = {}
        self._req_id = 0
        self._write_lock = asyncio.Lock()
        self._endpoint_ready = asyncio.Event()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._client = httpx.AsyncClient(headers=self._headers, timeout=60.0)
        self._sse_task = asyncio.get_event_loop().create_task(
            self._sse_loop(), name=f"mcp-sse-{self.name}"
        )
        # 等待 endpoint 事件（最多 10 秒）
        try:
            await asyncio.wait_for(self._endpoint_ready.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise MCPError(f"[MCP:{self.name}] 等待 SSE endpoint 超时，请检查服务是否正常运行")

        # MCP 握手
        init_resp = await self._request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "solopreneur", "version": "0.1.0"},
            },
            timeout=MCP_INIT_TIMEOUT,
        )
        logger.info(f"[MCP:{self.name}] 握手成功，server={init_resp.get('serverInfo', {})}")
        await self._notify("notifications/initialized")

        tools_resp = await self._request("tools/list", {}, timeout=MCP_INIT_TIMEOUT)
        self._tools = tools_resp.get("tools", [])
        logger.info(f"[MCP:{self.name}] 发现 {len(self._tools)} 个工具: "
                    f"{[t['name'] for t in self._tools]}")

    async def stop(self) -> None:
        if self._sse_task and not self._sse_task.done():
            self._sse_task.cancel()
        if self._client:
            await self._client.aclose()
        logger.info(f"[MCP:{self.name}] 已停止")

    # ------------------------------------------------------------------
    # 内部通信
    # ------------------------------------------------------------------

    async def _sse_loop(self) -> None:
        """持续读取 SSE 流，处理 endpoint 事件和 JSON-RPC 响应。"""
        assert self._client
        event_type = ""
        try:
            async with self._client.stream("GET", f"{self._base_url}/sse") as resp:
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        event_type = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        if event_type == "endpoint" or (
                            not event_type and (
                                data_str.startswith("http") or data_str.startswith("/")
                            )
                        ):
                            # 服务器告知 POST URL
                            if data_str.startswith("http"):
                                self._post_url = data_str
                            else:
                                self._post_url = f"{self._base_url}{data_str}"
                            self._endpoint_ready.set()
                            logger.debug(f"[MCP:{self.name}] POST endpoint: {self._post_url}")
                        else:
                            # JSON-RPC 响应
                            try:
                                data = json.loads(data_str)
                            except json.JSONDecodeError:
                                pass
                            else:
                                req_id = data.get("id")
                                if req_id is not None:
                                    fut = self._pending.pop(req_id, None)
                                    if fut and not fut.done():
                                        if "error" in data:
                                            err = data["error"]
                                            fut.set_exception(MCPError(
                                                f"code={err.get('code')} {err.get('message', '')}"
                                            ))
                                        else:
                                            fut.set_result(data.get("result", {}))
                    elif not line:
                        event_type = ""
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"[MCP:{self.name}] SSE 流异常: {e}")
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    async def _request(self, method: str, params: dict, timeout: float = MCP_TOOL_TIMEOUT) -> dict:
        assert self._post_url and self._client
        async with self._write_lock:
            self._req_id += 1
            req_id = self._req_id
            loop = asyncio.get_event_loop()
            fut: asyncio.Future[dict] = loop.create_future()
            self._pending[req_id] = fut
        payload = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}
        await self._client.post(self._post_url, json=payload)
        try:
            return await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise MCPError(f"MCP SSE 请求 '{method}' 超时（{timeout}s）")

    async def _notify(self, method: str, params: dict | None = None) -> None:
        assert self._post_url and self._client
        await self._client.post(
            self._post_url,
            json={"jsonrpc": "2.0", "method": method, "params": params or {}},
        )

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def get_tools(self) -> list[dict[str, Any]]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict, timeout: float = MCP_TOOL_TIMEOUT) -> str:
        result = await self._request(
            "tools/call", {"name": name, "arguments": arguments}, timeout=timeout
        )
        content = result.get("content", [])
        parts = [c.get("text", "") for c in content if c.get("type") == "text"]
        return "\n".join(parts) if parts else json.dumps(result, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Docker SSE 传输（docker run -p + SSE 连接）
# ---------------------------------------------------------------------------

class MCPDockerSseClient(MCPSseClient):
    """先用 `docker run -p` 启动容器，再通过 SSE 连接。"""

    def __init__(
        self,
        name: str,
        image: str,
        port: int,
        container_port: int | None = None,
        docker_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        cmd: list[str] | None = None,
        startup_delay: float = 2.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        url = f"http://localhost:{port}"
        super().__init__(name=name, url=url, headers=headers)
        self._image = image
        self._port = port
        self._container_port = container_port or port
        self._docker_args: list[str] = docker_args or []
        self._env: dict[str, str] = env or {}
        self._cmd: list[str] = cmd or []
        self._startup_delay = startup_delay
        self._docker_proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        docker_cmd = [
            "docker", "run", "--rm", "-d",
            "-p", f"{self._port}:{self._container_port}",
        ] + self._docker_args
        for k, v in self._env.items():
            docker_cmd += ["-e", f"{k}={v}"]
        docker_cmd.append(self._image)
        docker_cmd += self._cmd

        logger.info(f"[MCP:{self.name}] 启动 Docker-SSE 容器: {' '.join(docker_cmd)}")
        self._docker_proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        # 等待容器启动
        await asyncio.sleep(self._startup_delay)
        # 调用父类 SSE 启动
        await super().start()

    async def stop(self) -> None:
        await super().stop()
        if self._docker_proc:
            try:
                self._docker_proc.kill()
                await self._docker_proc.wait()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Tool Adapter：将 MCP Tool 包装为 solopreneur 原生 Tool
# ---------------------------------------------------------------------------

class MCPToolAdapter(Tool):
    """将 MCP 工具定义包装为 solopreneur 原生 Tool。

    工具名规则：mcp_<server_name>_<original_tool_name>
    描述前缀：[MCP:<server_name>] <original_description>
    """

    def __init__(
        self,
        server_name: str,
        tool_def: dict[str, Any],
        client: MCPStdioClient | MCPSseClient,
    ) -> None:
        self._server_name = server_name
        self._tool_def = tool_def
        self._client = client

    @property
    def name(self) -> str:
        # 工具名不能含空格或特殊字符
        raw = self._tool_def["name"].replace(" ", "_").replace("-", "_")
        return f"mcp_{self._server_name}_{raw}"

    @property
    def description(self) -> str:
        orig_desc = self._tool_def.get("description", self._tool_def["name"])
        return f"[MCP:{self._server_name}] {orig_desc}"

    @property
    def parameters(self) -> dict[str, Any]:
        return self._tool_def.get(
            "inputSchema", {"type": "object", "properties": {}, "required": []}
        )

    async def execute(self, **kwargs: Any) -> str:
        tool_name = self._tool_def["name"]
        try:
            return await self._client.call_tool(tool_name, kwargs)
        except MCPError as e:
            return f"MCP 工具调用失败 '{tool_name}': {e}"
        except Exception as e:
            return f"调用 MCP 工具 '{tool_name}' 时发生意外错误: {e}"


# ---------------------------------------------------------------------------
# MCPManager：根据配置管理全部 MCP 服务器
# ---------------------------------------------------------------------------

_ClientType = MCPStdioClient | MCPDockerSseClient | MCPSseClient


class MCPManager:
    """管理全部配置的 MCP 服务器生命周期，并将其工具注册到 ToolRegistry。

    使用方式（在 ComponentManager 中）：
        mcp_manager = MCPManager(config.tools.mcp.servers)
        await mcp_manager.start_all()
        # ... 注入到 AgentLoop
        await mcp_manager.stop_all()  # 应用关闭时调用
    """

    def __init__(self, servers_config: list[dict[str, Any]] | None = None) -> None:
        self._configs: list[dict[str, Any]] = servers_config or []
        self._clients: dict[str, _ClientType] = {}

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start_all(self) -> None:
        """启动所有已启用的 MCP 服务器。失败的服务器会跳过（记录错误日志）。"""
        for cfg in self._configs:
            if not cfg.get("enabled", True):
                continue
            name: str = cfg.get("name", "")
            if not name:
                logger.warning("[MCPManager] 跳过无 name 的服务器配置")
                continue
            transport: str = cfg.get("transport", "docker-stdio")
            try:
                client = self._build_client(name, transport, cfg)
                await client.start()
                self._clients[name] = client
            except Exception as e:
                logger.error(f"[MCPManager] 启动 MCP 服务器 '{name}' 失败: {e}")

    async def stop_all(self) -> None:
        """停止全部 MCP 服务器。"""
        for client in self._clients.values():
            try:
                await client.stop()
            except Exception as e:
                logger.warning(f"[MCPManager] 停止服务器时出错: {e}")
        self._clients.clear()

    # ------------------------------------------------------------------
    # 工具注册
    # ------------------------------------------------------------------

    def register_tools(self, registry: "ToolRegistry") -> None:
        """将所有 MCP 服务器的工具注册到 ToolRegistry。"""
        count = 0
        for server_name, client in self._clients.items():
            for tool_def in client.get_tools():
                adapter = MCPToolAdapter(
                    server_name=server_name,
                    tool_def=tool_def,
                    client=client,
                )
                registry.register(adapter)
                count += 1
                logger.debug(f"[MCPManager] 注册工具: {adapter.name}")
        if count:
            logger.info(f"[MCPManager] 共注册 {count} 个 MCP 工具")

    def get_tool_names(self) -> list[str]:
        """返回所有 MCP 工具的名称列表（注册后的 adapter 名称）。"""
        names = []
        for server_name, client in self._clients.items():
            for tool_def in client.get_tools():
                raw = tool_def["name"].replace(" ", "_").replace("-", "_")
                names.append(f"mcp_{server_name}_{raw}")
        return names

    def is_empty(self) -> bool:
        return len(self._clients) == 0

    # ------------------------------------------------------------------
    # 内部工厂
    # ------------------------------------------------------------------

    @staticmethod
    def _build_client(name: str, transport: str, cfg: dict) -> _ClientType:
        if transport == "docker-stdio":
            image = cfg.get("image")
            if not image:
                raise MCPError(f"docker-stdio 模式需要指定 'image'，服务器: {name}")
            return MCPStdioClient(
                name=name,
                image=image,
                docker_args=cfg.get("docker_args", []),
                env=cfg.get("env", {}),
                cmd=cfg.get("cmd", []),
            )
        elif transport == "docker-sse":
            image = cfg.get("image")
            port = cfg.get("port")
            if not image or not port:
                raise MCPError(f"docker-sse 模式需要指定 'image' 和 'port'，服务器: {name}")
            return MCPDockerSseClient(
                name=name,
                image=image,
                port=int(port),
                container_port=cfg.get("container_port") or int(port),
                docker_args=cfg.get("docker_args", []),
                env=cfg.get("env", {}),
                cmd=cfg.get("cmd", []),
                startup_delay=float(cfg.get("startup_delay", 2.0)),
                headers=cfg.get("headers", {}),
            )
        elif transport == "sse":
            url = cfg.get("url")
            if not url:
                raise MCPError(f"sse 模式需要指定 'url'，服务器: {name}")
            return MCPSseClient(
                name=name,
                url=url,
                headers=cfg.get("headers", {}),
            )
        else:
            raise MCPError(f"未知 MCP 传输类型: '{transport}'，服务器: {name}")
