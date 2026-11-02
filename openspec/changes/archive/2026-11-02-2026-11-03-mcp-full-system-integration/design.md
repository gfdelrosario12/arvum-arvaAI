# Design: MCP Full System Architecture & Integration

## Architecture Overview

```
                      +---------------------------------------+
                      |       User / Flutter Frontend         |
                      |  - Execution Indicators               |
                      |  - Confirmation Modals                |
                      +-------------------+-------------------+
                                          |
                                          | REST / SSE
                                          v
                      +---------------------------------------+
                      |   ArvaNet Spring Boot Backend         |
                      |   (Source of Truth, RBAC, DB)         |
                      +-------------------+-------------------+
                                          |
                                          | REST / HTTP
                                          v
+--------------------------------------------------------------------------------+
| ArvaAI Microservice                                                            |
|                                                                                |
|   +-----------------------+              +---------------------------------+   |
|   |   Gemini 2.5 Flash    | <=========>  |       MCP Client                |   |
|   |  - Reasoning          | Function     |  - Tool Discovery               |   |
|   |  - Function Calling   | Calling      |  - Execution Engine             |   |
|   |  - Response Gen       | Adapter      |  - Error & Timeout Handling     |   |
|   +-----------------------+              +----------------+----------------+   |
|                                                           |                    |
|                                                           | MCP Protocol       |
|                                                           | (SSE / JSON-RPC)   |
|                                                           v                    |
|                                          +----------------+----------------+   |
|                                          |       MCP Server                |   |
|                                          |  - Tools (Info, Context, Ops)   |   |
|                                          |  - Resources (Manuals, Profiles)|   |
|                                          |  - Prompts (Consultations)      |   |
|                                          +----------------+----------------+   |
|                                                           |                    |
+-----------------------------------------------------------+--------------------+
                                                            |
                                                            v
                                           Backend Services & External APIs
                                           - Telemetry & Node Health
                                           - PhilRice Agronomic Data
                                           - PAGASA Weather Models
                                           - Lopez Agro-statistics
```

## Component Details

### 1. MCP Server (`app/mcp/server.py`)
- Standards compliant Model Context Protocol Server over HTTP/SSE and internal direct invocation.
- Exposes:
  - **Tools**:
    - `get_field_telemetry`: Fetches real-time sensor data across nodes.
    - `get_irrigation_history`: Fetches past irrigation logs and water usage.
    - `get_pagasa_weather`: Weather forecasts and warnings for Lopez, Quezon.
    - `get_agronomic_profile`: Historical yields, soil series, and variety recommendations.
    - `search_philrice_manual`: Semantic index retrieval over official PhilRice manual.
    - `propose_awd_irrigation`: Drafts reflood action plan (requires confirmation).
    - `evaluate_planting_readiness`: Multi-factor suitability scoring.
  - **Resources**:
    - `arva://agronomy/varieties`: Certified rice variety profiles.
    - `arva://agronomy/calendar`: Lopez Quezon seasonal cropping calendar.
    - `arva://agronomy/soil`: Dominant soil characteristics.
  - **Prompts**:
    - `rice_consultation_prompt`: Guided multi-turn planting assessment prompt template.

### 2. MCP Client & Gemini Adapter (`app/mcp/client.py`, `app/mcp/gemini_mcp_adapter.py`)
- Discovers tools dynamically via `list_tools()`.
- Maps MCP tool schemas into Google Gemini FunctionDeclarations.
- Manages multi-turn conversations:
  - Detects `function_call` parts in Gemini response.
  - Executes tool through MCP client with strict timeouts (15s).
  - Feeds tool output back as `function_response` to Gemini.
  - Caps execution at `MAX_TOOL_ROUNDS` (4) to prevent infinite recursion.
- Returns comprehensive metadata including executed tool list, execution timings, and execution states.

### 3. Backend & Security (`ArvaNet_Backend`)
- Enforces role checks before executing sensitive operations.
- Audits all AI tool executions with caller identities.
- Non-bypassable physical actuation guardrails.

### 4. Frontend UX (`ArvaNet_Frontend`)
- Renders tool execution progress pills (e.g. `Checking PAGASA weather...`, `Retrieving sensor telemetry...`).
- Displays execution status chips (Pending, Running, Completed, Failed, Requires Confirmation).
- Preserves responsive layouts across all screen breakpoints.
