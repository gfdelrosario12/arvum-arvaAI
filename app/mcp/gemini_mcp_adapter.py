"""
Gemini MCP Adapter.
Converts discovered MCP Tool definitions into Google Gemini 2.5 Flash FunctionDeclarations,
and coordinates multi-turn reasoning and tool invocation loops.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from app.mcp.protocol import MCPToolDefinition, MCPToolCallResult, MCPToolExecutionState
from app.mcp.client import ArvaMCPClient

logger = logging.getLogger("arva.mcp.gemini_adapter")

class GeminiMCPOrchestrator:
    """
    Coordinates Google Gemini 2.5 Flash function calling with an MCP Client.
    Supports multi-round tool loops, recursion prevention, and detailed execution telemetry.
    """

    def __init__(self, mcp_client: ArvaMCPClient, max_tool_rounds: int = 4):
        self.mcp_client = mcp_client
        self.max_tool_rounds = max_tool_rounds

    async def get_gemini_tools_declaration(self) -> List[Dict[str, Any]]:
        """Discovers tools via MCP and formats them as Gemini function declarations."""
        tools = await self.mcp_client.discover_tools()
        return [t.to_gemini_declaration() for t in tools]

    async def execute_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        user_id: str = "anonymous",
        role: str = "FARMER",
        confirmed: bool = False
    ) -> MCPToolCallResult:
        """Executes a single requested tool call through the MCP Client."""
        return await self.mcp_client.call_tool(
            tool_name=tool_name,
            arguments=arguments,
            user_id=user_id,
            role=role,
            confirmed=confirmed
        )

    def select_appropriate_tools(self, user_prompt: str, available_tools: List[MCPToolDefinition]) -> List[str]:
        """
        Determines which MCP tools are logically relevant based on prompt analysis,
        helping optimize context and avoid calling unnecessary tools.
        """
        prompt_lower = user_prompt.lower()
        selected = []

        # Weather intent
        if any(w in prompt_lower for w in ["weather", "rain", "forecast", "typhoon", "pagasa", "monsoon"]):
            selected.append("get_pagasa_weather")

        # Telemetry / water level intent
        if any(w in prompt_lower for w in ["water", "level", "depth", "moisture", "telemetry", "sensor", "node", "awd"]):
            selected.append("get_field_telemetry")

        # Agronomy / Variety / Soil intent
        if any(w in prompt_lower for w in ["variety", "varieties", "soil", "nsic", "yield", "calendar", "crop"]):
            selected.append("get_agronomic_profile")

        # Planting readiness
        if any(w in prompt_lower for w in ["ready", "readiness", "prepare", "preparation", "timeline", "planting"]):
            selected.append("evaluate_planting_readiness")

        # PhilRice manual guidance
        if any(w in prompt_lower for w in ["manual", "soaking", "incubation", "plowing", "harrowing", "fertilizer", "weeding"]):
            selected.append("search_philrice_manual")

        return selected
