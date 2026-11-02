"""
Unit and integration tests for ArvaCore Model Context Protocol (MCP) Server,
Client, and Gemini Function Calling Adapter.
"""

import pytest
import asyncio
from app.mcp.protocol import (
    MCPToolDefinition,
    MCPToolCategory,
    MCPToolExecutionState,
    MCPToolCallRequest
)
from app.mcp.server import ArvaMCPServer
from app.mcp.client import ArvaMCPClient
from app.mcp.gemini_mcp_adapter import GeminiMCPOrchestrator

@pytest.fixture
def mcp_server():
    return ArvaMCPServer(telemetry_tools=None)

@pytest.fixture
def mcp_client(mcp_server):
    return ArvaMCPClient(server=mcp_server)

@pytest.fixture
def orchestrator(mcp_client):
    return GeminiMCPOrchestrator(mcp_client=mcp_client)

def test_mcp_server_initialization_and_tool_discovery(mcp_server):
    tools = mcp_server.list_tools()
    assert len(tools) >= 7
    tool_names = [t.name for t in tools]
    assert "get_field_telemetry" in tool_names
    assert "get_irrigation_history" in tool_names
    assert "get_node_health" in tool_names
    assert "search_philrice_manual" in tool_names
    assert "get_agronomic_profile" in tool_names
    assert "evaluate_planting_readiness" in tool_names
    assert "propose_awd_irrigation" in tool_names
    assert "get_pagasa_weather" in tool_names

def test_mcp_server_resources_and_prompts(mcp_server):
    resources = mcp_server.list_resources()
    assert len(resources) >= 3
    uris = [r.uri for r in resources]
    assert "arva://agronomy/varieties" in uris
    assert "arva://agronomy/calendar" in uris
    assert "arva://agronomy/soil" in uris

    # Verify resource reading
    variety_res = mcp_server.read_resource("arva://agronomy/varieties")
    assert "content" in variety_res
    assert len(variety_res["content"]) >= 3

    prompts = mcp_server.list_prompts()
    assert len(prompts) >= 1
    assert prompts[0].name == "rice_consultation_prompt"

def test_mcp_server_tool_execution_pagasa_weather(mcp_server):
    req = MCPToolCallRequest(
        name="get_pagasa_weather",
        arguments={"days": 3},
        user_id="farmer_01",
        role="FARMER"
    )
    result = mcp_server.execute_tool(req)
    assert result.state == MCPToolExecutionState.COMPLETED
    assert result.result is not None
    assert "daily_forecast" in result.result

def test_mcp_server_rbac_enforcement(mcp_server):
    # propose_awd_irrigation requires OPERATOR role
    req = MCPToolCallRequest(
        name="propose_awd_irrigation",
        arguments={"field_id": 1, "target_depth_cm": 5.0},
        user_id="unauthorized_farmer",
        role="FARMER"
    )
    result = mcp_server.execute_tool(req)
    assert result.state == MCPToolExecutionState.FAILED
    assert "Unauthorized" in result.error

def test_mcp_server_human_confirmation_requirement(mcp_server):
    # propose_awd_irrigation requires operator confirmation
    req = MCPToolCallRequest(
        name="propose_awd_irrigation",
        arguments={"field_id": 1, "target_depth_cm": 5.0},
        user_id="operator_01",
        role="OPERATOR",
        confirmed=False
    )
    result = mcp_server.execute_tool(req)
    assert result.state == MCPToolExecutionState.REQUIRES_CONFIRMATION
    assert result.requires_confirmation is True

    # When confirmed is provided
    req_confirmed = MCPToolCallRequest(
        name="propose_awd_irrigation",
        arguments={"field_id": 1, "target_depth_cm": 5.0},
        user_id="operator_01",
        role="OPERATOR",
        confirmed=True
    )
    res_confirmed = mcp_server.execute_tool(req_confirmed)
    assert res_confirmed.state == MCPToolExecutionState.COMPLETED

@pytest.mark.asyncio
async def test_mcp_client_tool_discovery_and_invocation(mcp_client):
    tools = await mcp_client.discover_tools()
    assert len(tools) >= 7

    res = await mcp_client.call_tool(
        tool_name="get_agronomic_profile",
        arguments={"category": "yield"},
        user_id="farmer_test",
        role="FARMER"
    )
    assert res.state == MCPToolExecutionState.COMPLETED
    assert "yield_benchmarks" in res.result["data"]

@pytest.mark.asyncio
async def test_gemini_mcp_orchestrator(orchestrator):
    gemini_tools = await orchestrator.get_gemini_tools_declaration()
    assert len(gemini_tools) >= 7
    for gt in gemini_tools:
        assert "name" in gt
        assert "description" in gt
        assert "parameters" in gt

    selected = orchestrator.select_appropriate_tools(
        "Is it going to rain in Lopez and what is my soil status?",
        []
    )
    assert "get_pagasa_weather" in selected
    assert "get_agronomic_profile" in selected
