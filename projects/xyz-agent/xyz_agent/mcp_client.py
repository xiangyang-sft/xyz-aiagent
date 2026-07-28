#!/usr/bin/env python3
"""
xyz_agent.mcp — MCP (Model Context Protocol) 客户端
"""

import json
import asyncio
import subprocess
import logging
import time
import uuid
import sys
import os
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from .tool import ToolRegistry

logger = logging.getLogger(__name__)

# ============================================================
# MCP 消息类型
# ============================================================

MCP_JSONRPC_VERSION = "2.0"


def _make_request(method: str, params: Optional[Dict] = None) -> Dict:
    """构造 MCP JSON-RPC 请求"""
    return {
        "jsonrpc": MCP_JSONRPC_VERSION,
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }


def _make_notification(method: str, params: Optional[Dict] = None) -> Dict:
    """构造 MCP JSON-RPC 通知（无响应）"""
    return {
        "jsonrpc": MCP_JSONRPC_VERSION,
        "method": method,
        "params": params or {},
    }


# ============================================================
# MCP 服务器连接
# ============================================================

class MCPServerConnection:
    """
    MCP 服务器连接基类

    子类:
      - StdioMCPServer — 通过子进程 stdio 连接
      - HTTPMCPServer  — 通过 HTTP/SSE 连接
    """

    def __init__(self, name: str):
        self.name = name
        self.server_info: Optional[Dict] = None
        self._tools: List[Dict] = []
        self._connected = False
        self._capabilities: Dict = {}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def tools(self) -> List[Dict]:
        return self._tools

    async def connect(self):
        """建立连接"""
        raise NotImplementedError

    async def disconnect(self):
        """断开连接"""
        raise NotImplementedError

    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        """发送请求并等待响应"""
        raise NotImplementedError

    async def list_tools(self) -> List[Dict]:
        """获取 MCP 服务器提供的工具列表"""
        response = await self.send_request("tools/list")
        self._tools = response.get("tools", response.get("result", {}).get("tools", []))
        return self._tools

    async def call_tool(self, name: str, arguments: Dict) -> Any:
        """调用 MCP 工具"""
        response = await self.send_request("tools/call", {
            "name": name,
            "arguments": arguments,
        })
        return response.get("result", response)

    async def initialize(self):
        """初始化 MCP 会话"""
        response = await self.send_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "xyz-agent",
                "version": "0.1.0",
            },
        })
        result = response.get("result", response)
        self.server_info = result.get("serverInfo", {})
        self._capabilities = result.get("capabilities", {})
        # 发送初始化通知
        await self.send_notification("notifications/initialized")
        self._connected = True
        return result


class StdioMCPServer(MCPServerConnection):
    """
    通过子进程 stdio 通信的 MCP 服务器

    用法:
        server = StdioMCPServer("fs", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"])
        await server.connect()
    """

    def __init__(self, name: str, command: str, args: Optional[List[str]] = None,
                 env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None):
        super().__init__(name)
        self._command = command
        self._args = args or []
        self._env = env
        self._cwd = cwd
        self._process: Optional[subprocess.Popen] = None
        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self._buffer = ""

    async def connect(self):
        if self._connected:
            return

        logger.info(f"连接 MCP 服务器 '{self.name}': {self._command} {' '.join(self._args)}")

        try:
            self._process = await asyncio.create_subprocess_exec(
                self._command,
                *self._args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={**(os.environ), **(self._env or {})},
                cwd=self._cwd,
            )

            # 启动读取协程
            self._reader_task = asyncio.create_task(self._reader_loop())

            # 执行初始化握手
            await self.initialize()
            logger.info(f"MCP 服务器 '{self.name}' 连接成功: {self.server_info}")

        except Exception as e:
            logger.error(f"MCP 服务器 '{self.name}' 连接失败: {e}")
            await self.disconnect()
            raise

    async def disconnect(self):
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
            self._reader_task = None
        if self._process:
            try:
                self._process.terminate()
                await asyncio.sleep(0.5)
                if self._process.returncode is None:
                    self._process.kill()
                await self._process.wait()
            except:
                pass
            self._process = None
        # 取消所有待处理请求
        for future in self._pending_requests.values():
            if not future.done():
                future.set_exception(Exception("连接已断开"))
        self._pending_requests.clear()

    async def send_request(self, method: str, params: Optional[Dict] = None) -> Dict:
        request = _make_request(method, params)
        request_id = request["id"]

        future = asyncio.get_event_loop().create_future()
        self._pending_requests[request_id] = future

        try:
            async with self._lock:
                if self._process and self._process.stdin:
                    line = json.dumps(request, ensure_ascii=False) + "\n"
                    self._process.stdin.write(line.encode())
                    await self._process.stdin.drain()

            # 等待响应
            response = await asyncio.wait_for(future, timeout=30.0)
            return response

        except asyncio.TimeoutError:
            self._pending_requests.pop(request_id, None)
            raise TimeoutError(f"MCP 请求超时: {method}")
        except Exception as e:
            self._pending_requests.pop(request_id, None)
            raise

    async def send_notification(self, method: str, params: Optional[Dict] = None):
        """发送通知（无需等待响应）"""
        notification = _make_notification(method, params)
        async with self._lock:
            if self._process and self._process.stdin:
                line = json.dumps(notification, ensure_ascii=False) + "\n"
                self._process.stdin.write(line.encode())
                await self._process.stdin.drain()

    async def _reader_loop(self):
        """持续读取 stdout 并分发响应"""
        try:
            while self._process and self._process.stdout:
                line = await self._process.stdout.readline()
                if not line:
                    break

                line_str = line.decode().strip()
                if not line_str:
                    continue

                try:
                    msg = json.loads(line_str)
                    msg_id = msg.get("id")

                    if msg_id and msg_id in self._pending_requests:
                        future = self._pending_requests.pop(msg_id)
                        if not future.done():
                            future.set_result(msg)

                    # 处理通知
                    method = msg.get("method", "")
                    if method == "notifications/tools/list_changed":
                        logger.info(f"MCP 服务器 '{self.name}' 工具列表已变更")

                except json.JSONDecodeError:
                    # stderr 输出（非 JSON）
                    logger.debug(f"[MCP {self.name} stderr] {line_str}")

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"MCP 读取循环错误: {e}")
        finally:
            self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()


# ============================================================
# MCP 管理器
# ============================================================

class MCPManager:
    """
    MCP 管理器 — 管理多个 MCP 服务器连接

    用法:
        mcp = MCPManager()
        # stdio 连接
        fs_server = mcp.connect_stdio(
            "filesystem", "npx", ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        )
        # HTTP 连接
        mcp.connect_http("remote", "http://localhost:8000/mcp")

        # 发现并注册工具
        mcp.discover_all_tools(registry=my_registry)

        # 调用工具
        result = mcp.call_tool("filesystem", "read", {"path": "/tmp/test.txt"})

    也支持同步快捷方式:
        result = mcp.call_tool_sync("filesystem", "read", {"path": "/tmp/test.txt"})
    """

    def __init__(self):
        self._servers: Dict[str, MCPServerConnection] = {}
        self._tool_index: Dict[str, tuple] = {}  # tool_name -> (server_name, tool_def)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ---- 连接管理 ----

    def connect_stdio(self, name: str, command: str, args: Optional[List[str]] = None,
                      env: Optional[Dict] = None, cwd: Optional[str] = None,
                      auto_connect: bool = True) -> StdioMCPServer:
        """连接 stdio MCP 服务器"""
        server = StdioMCPServer(name, command, args, env, cwd)
        self._servers[name] = server

        if auto_connect:
            self._run_async(server.connect())

        return server

    def connect_http(self, name: str, url: str, api_key: Optional[str] = None):
        """连接 HTTP MCP 服务器（预留）"""
        logger.warning(f"HTTP MCP 服务器 '{name}' 暂未实现")
        raise NotImplementedError("HTTP MCP 传输层尚未实现")

    def get_server(self, name: str) -> Optional[MCPServerConnection]:
        return self._servers.get(name)

    def list_servers(self) -> List[str]:
        return list(self._servers.keys())

    async def disconnect_all(self):
        for server in self._servers.values():
            await server.disconnect()
        self._servers.clear()
        self._tool_index.clear()

    # ---- 工具发现 ----

    async def discover_all_tools(self, registry: Optional[ToolRegistry] = None) -> Dict[str, List[Dict]]:
        """从所有已连接的 MCP 服务器发现工具"""
        results = {}
        for name, server in self._servers.items():
            if server.is_connected:
                try:
                    tools = await server.list_tools()
                    results[name] = tools
                    for tool in tools:
                        tool_name = f"{name}:{tool.get('name', 'unknown')}"
                        self._tool_index[tool_name] = (name, tool)

                    # 注册到 ToolRegistry
                    if registry:
                        for tool in tools:
                            tool_name = tool.get('name', 'unknown')
                            registry.register_fn(
                                name=f"mcp:{name}:{tool_name}",
                                fn=self._make_mcp_callable(name, tool_name),
                                description=tool.get('description', ''),
                                parameters=tool.get('inputSchema', tool.get('parameters', {})),
                            )
                except Exception as e:
                    logger.warning(f"从 '{name}' 发现工具失败: {e}")
                    results[name] = []
            else:
                results[name] = []
        return results

    def discover_all_tools_sync(self, registry: Optional[ToolRegistry] = None) -> Dict[str, int]:
        """同步版本的工具发现（通过事件循环）"""
        result = self._run_async(self.discover_all_tools(registry))
        return {
            server: len(tools)
            for server, tools in result.items()
        }

    # ---- 工具调用 ----

    async def call_tool(self, server_or_name: Union[str, MCPServerConnection],
                        tool_name: str, arguments: Dict) -> Any:
        """调用 MCP 工具"""
        if isinstance(server_or_name, str):
            server = self._servers.get(server_or_name)
            if not server:
                raise KeyError(f"未知 MCP 服务器: {server_or_name}")
        else:
            server = server_or_name
        return await server.call_tool(tool_name, arguments)

    def call_tool_sync(self, server_name: str, tool_name: str, arguments: Dict) -> Any:
        """同步调用 MCP 工具"""
        return self._run_async(self.call_tool(server_name, tool_name, arguments))

    # ---- MCP 工具映射 ----

    def _make_mcp_callable(self, server_name: str, tool_name: str):
        """创建 MCP 工具的同步可调用包装"""
        def mcp_callable(**kwargs):
            return self.call_tool_sync(server_name, tool_name, kwargs)
        mcp_callable.__name__ = f"mcp_{server_name}_{tool_name}"
        mcp_callable.__doc__ = f"MCP 工具: {server_name}/{tool_name}"
        return mcp_callable

    async def mcp_callable_async(self, server_name: str, tool_name: str, **kwargs) -> str:
        """异步 MCP 调用"""
        result = await self.call_tool(server_name, tool_name, kwargs)
        return json.dumps(result, ensure_ascii=False, default=str)

    # ---- 辅助 ----

    def _run_async(self, coro):
        """在同步环境中运行协程"""
        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中运行
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=30)
        except RuntimeError:
            # 没有正在运行的事件循环
            return asyncio.run(coro)


