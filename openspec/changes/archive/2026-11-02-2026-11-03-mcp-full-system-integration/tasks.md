# Tasks: Full System Model Context Protocol (MCP) Integration

## Task Ordering & Execution Plan

- [x] 1. **MCP Server Architecture Implementation**
  - [x] 1.1 Implement core protocol schemas and definitions in `ArvaAI/app/mcp/protocol.py`.
  - [x] 1.2 Implement the MCP Server in `ArvaAI/app/mcp/server.py` supporting Tools, Resources, and Prompts.
  - [x] 1.3 Register tools for Information Retrieval, AI Context, Operations, and External Integrations.
  - [x] 1.4 Expose MCP endpoints (`/api/v1/mcp/tools`, `/api/v1/mcp/call`, `/api/v1/mcp/resources`, `/api/v1/mcp/prompts`) in FastAPI.

- [x] 2. **MCP Client & Gemini 2.5 Flash Orchestration**
  - [x] 2.1 Implement MCP Client in `ArvaAI/app/mcp/client.py` with discovery and execution resilience.
  - [x] 2.2 Implement Gemini Function Calling Adapter in `ArvaAI/app/mcp/gemini_mcp_adapter.py`.
  - [x] 2.3 Integrate MCP orchestration loop into `ArvaGeminiAdvisor` and `FarmingChatPlanner`.
  - [x] 2.4 Add loop prevention (max 4 rounds), timeout controls, and adversarial sanitization.

- [x] 3. **Backend Service Coordination & Security**
  - [x] 3.1 Update Spring Boot `FarmingChatbotServiceImpl` with tool execution audit tracking and DTO metadata.
  - [x] 3.2 Ensure backend validation and role-based permissions cannot be bypassed by tool outputs.

- [x] 4. **Chatbot UI/UX Integration**
  - [x] 4.1 Update Flutter models in `farming_chat_models.dart` to support `ToolExecutionRecord` and execution states.
  - [x] 4.2 Add tool execution badges and status indicators to `farming_chatbot_screen.dart`.
  - [x] 4.3 Preserve full responsiveness and consistent sidebar behavior across all breakpoints.

- [x] 5. **Testing, Documentation & Deployment**
  - [x] 5.1 Implement comprehensive unit and integration tests for MCP Server, Client, and Gemini Adapter.
  - [x] 5.2 Validate all tests pass in ArvaAI test suite.
  - [x] 5.3 Write complete architectural and integration documentation (`Documentations/MCP_SYSTEM_INTEGRATION.md`).
  - [x] 5.4 Update deployment scripts (`scripts/redeploy-ai.sh`) and verify health checks.
