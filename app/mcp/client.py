"""
ArvaCore MCP Client Implementation.
Connects to local or remote MCP servers, discovers tools,
validates arguments, and executes tool calls with timeout protection
and automatic session management.
"""

import time
import logging
from typing import Dict, Any, List, Optional
import httpx

from app.mcp.protocol import (
    MCPToolDefinition,
    MCPResourceDefinition,
    MCPPromptDefinition,
    MCPToolCallRequest,
    MCPToolCallResult,
    MCPToolExecutionState
)
from app.mcp.server import ArvaMCPServer

logger = logging.getLogger("arva.mcp.client")

class ArvaMCPClient:
    """
    Client connecting to an MCP server (either directly embedded or via HTTP/SSE endpoint).
    """

    def __init__(self, server: Optional[ArvaMCPServer] = None, remote_url: Optional[str] = None, timeout_seconds: float = 15.0):
        self.server = server
        self.remote_url = remote_url.rstrip("/") if remote_url else None
        self.timeout_seconds = timeout_seconds
        self._cached_tools: Optional[List[MCPToolDefinition]] = None
        self._last_discovery_time = 0.0

    async def initialize(self) -> bool:
        """Initializes connection and pre-fetches tool definitions."""
        try:
            tools = await self.discover_tools(force_refresh=True)
            logger.info(f"MCP Client initialized successfully with {len(tools)} tools discovered.")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize MCP Client: {str(e)}", exc_info=True)
            return False

    async def discover_tools(self, force_refresh: bool = False) -> List[MCPToolDefinition]:
        """Discovers available tools from the connected MCP Server."""
        now = time.time()
        if self._cached_tools is not None and not force_refresh and (now - self._last_discovery_time < 300):
            return self._cached_tools

        if self.server:
            # Direct in-process invocation
            self._cached_tools = self.server.list_tools()
            self._last_discovery_time = now
            return self._cached_tools

        if self.remote_url:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                resp = await client.get(f"{self.remote_url}/api/v1/mcp/tools")
                resp.raise_for_status()
                data = resp.json()
                self._cached_tools = [MCPToolDefinition.model_validate(t) for t in data.get("tools", [])]
                self._last_discovery_time = now
                return self._cached_tools

        return []

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str = "anonymous",
        role: str = "FARMER",
        confirmed: bool = False
    ) -> MCPToolCallResult:
        """Invokes an MCP tool call on the server with strict timeout and error capture."""
        req = MCPToolCallRequest(
            name=tool_name,
            arguments=arguments,
            user_id=user_id,
            role=role,
            confirmed=confirmed
        )

        start_time = time.time()
        try:
            if self.server:
                # Direct invocation
                return self.server.execute_tool(req)

            if self.remote_url:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    resp = await client.post(f"{self.remote_url}/api/v1/mcp/call", json=req.model_dump())
                    resp.raise_for_status()
                    return MCPToolCallResult.model_validate(resp.json())

            return MCPToolCallResult(
                name=tool_name,
                state=MCPToolExecutionState.FAILED,
                error="MCP Client is not connected to any server instance.",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except httpx.TimeoutException:
            return MCPToolCallResult(
                name=tool_name,
                state=MCPToolExecutionState.TIMED_OUT,
                error=f"MCP Tool '{tool_name}' timed out after {self.timeout_seconds} seconds.",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        except Exception as e:
            return MCPToolCallResult(
                name=tool_name,
                state=MCPToolExecutionState.FAILED,
                error=f"MCP Client tool call error: {str(e)}",
                execution_time_ms=(time.time() - start_time) * 1000
            )
