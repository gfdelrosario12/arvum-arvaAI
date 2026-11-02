"""
Model Context Protocol (MCP) Core Protocol Definitions & Data Models.
Conforms to MCP standard specification (2024-11-05).
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

class MCPToolCategory(str, Enum):
    INFORMATION_RETRIEVAL = "information_retrieval"
    AI_CONTEXT = "ai_context"
    APPLICATION_OPERATIONS = "application_operations"
    EXTERNAL_INTEGRATIONS = "external_integrations"

class MCPToolExecutionState(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"

class MCPToolDefinition(BaseModel):
    name: str = Field(..., description="Unique tool name (snake_case)")
    description: str = Field(..., description="Human and LLM-readable description of functionality")
    category: MCPToolCategory = Field(default=MCPToolCategory.INFORMATION_RETRIEVAL)
    input_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for parameters")
    requires_confirmation: bool = Field(default=False, description="True if human confirmation required")
    required_role: str = Field(default="FARMER", description="Minimum RBAC role required to execute")

    def to_gemini_declaration(self) -> Dict[str, Any]:
        """Convert MCP tool definition to Gemini function declaration format."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema
        }

class MCPResourceDefinition(BaseModel):
    uri: str = Field(..., description="URI scheme for resource (e.g. arva://agronomy/varieties)")
    name: str = Field(..., description="Human-readable title")
    description: Optional[str] = None
    mime_type: str = Field(default="application/json")

class MCPPromptArgument(BaseModel):
    name: str
    description: Optional[str] = None
    required: bool = False

class MCPPromptDefinition(BaseModel):
    name: str = Field(..., description="Unique prompt template name")
    description: Optional[str] = None
    arguments: List[MCPPromptArgument] = Field(default_factory=list)

class MCPToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    user_id: str = "anonymous"
    role: str = "FARMER"
    confirmed: bool = False

class MCPToolCallResult(BaseModel):
    name: str
    state: MCPToolExecutionState
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    requires_confirmation: bool = False
    confirmation_reason: Optional[str] = None
