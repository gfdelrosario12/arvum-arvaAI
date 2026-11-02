# Proposal: Full System Model Context Protocol (MCP) Integration

## Problem Statement
The current AI assistant (Arva AI) operates with localized internal adapters (`mcp_pagasa_adapter.py`, `mcp_lopez_agri_adapter.py`, `read_only_tools.py`) and a custom conversational planner (`farming_chat_planner.py`), but lacks a standardized, decoupled Model Context Protocol (MCP) architecture. Specifically:
1. There is no official MCP Server exposing agricultural capabilities, resources, and prompts over standard protocol endpoints (SSE/HTTP & JSON-RPC).
2. The AI orchestration layer lacks an extensible MCP Client capable of dynamic tool discovery, schema translation for Gemini 2.5 Flash function calling, multi-round tool execution, and timeout/error resilience.
3. The Spring Boot backend and Flutter frontend have limited insight into tool execution states (e.g. running, completed, requires confirmation).

## Proposed Solution
Implement a clean, comprehensive MCP integration across the entire ArvaCore ecosystem:
1. **MCP Server**: FastMCP / JSON-RPC server running within Arva AI, exposing 4 primary tool categories (Information Retrieval, AI Context, Application Operations, External Integrations), resources (agronomic profiles, field topologies, PhilRice manuals), and prompts.
2. **MCP Client**: Robust asynchronous client with session management, tool discovery, fallback handling, and execution timeout protection.
3. **Gemini Adapter**: Seamless conversion between discovered MCP tool schemas and Gemini 2.5 Flash function declarations, executing multi-turn tool loops with loop prevention (max 4 rounds).
4. **Backend & Security**: Role-based access control (RBAC), non-bypassable backend validation, execution audit trails, and human-in-the-loop confirmation for state-altering actions.
5. **Frontend UI/UX**: Tool execution progress indicators, execution state badges (Running, Completed, Requires Confirmation, Failed), and inspection dialogs.

## Non-Goals
- Allowing Gemini direct hardware/actuator control (safety interlock invariant strictly preserved).
- Replacing Spring Boot as the core database and business logic source of truth.
