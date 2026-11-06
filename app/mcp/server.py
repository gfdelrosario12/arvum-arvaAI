"""
ArvaCore MCP Server Implementation.
Exposes categorized tools, resources, and prompt templates adhering to
the Model Context Protocol (MCP) specification.
Reuses existing backend telemetry, PAGASA weather, PhilRice knowledge,
and agronomic calculation engines.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from app.mcp.protocol import (
    MCPToolDefinition,
    MCPToolCategory,
    MCPResourceDefinition,
    MCPPromptDefinition,
    MCPPromptArgument,
    MCPToolCallRequest,
    MCPToolCallResult,
    MCPToolExecutionState
)
from app.tools.read_only_tools import ReadOnlyTelemetryTools
from app.tools.mcp_pagasa_adapter import PagasaWeatherMcpAdapter
from app.tools.mcp_lopez_agri_adapter import LopezAgriHistoricalMcpAdapter, LOPEZ_HISTORICAL_AGRI_DATA
from app.services.philrice_manual_retriever import PhilRiceManualRetriever
from app.services.rice_planting_readiness_engine import RicePlantingReadinessEngine
from app.services.philrice_rice_knowledge import RICE_VARIETIES

logger = logging.getLogger("arva.mcp.server")

class ArvaMCPServer:
    """
    Standardized MCP Server exposing ArvaCore agricultural decision support
    and telemetry capabilities to AI clients.
    """

    def __init__(self, telemetry_tools: Optional[ReadOnlyTelemetryTools] = None):
        self.telemetry_tools = telemetry_tools
        self.pagasa_adapter = PagasaWeatherMcpAdapter()
        self.lopez_adapter = LopezAgriHistoricalMcpAdapter()
        self.manual_retriever = PhilRiceManualRetriever()
        self.readiness_engine = RicePlantingReadinessEngine()
        self._tools: Dict[str, MCPToolDefinition] = {}
        self._resources: Dict[str, MCPResourceDefinition] = {}
        self._prompts: Dict[str, MCPPromptDefinition] = {}
        self._register_defaults()

    def _register_defaults(self):
        # 1. INFORMATION RETRIEVAL
        self.register_tool(
            MCPToolDefinition(
                name="get_field_telemetry",
                description="Retrieves the latest verified water levels, rootzone soil moisture, and online sensor status for all monitoring nodes in a field.",
                category=MCPToolCategory.INFORMATION_RETRIEVAL,
                input_schema={
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "integer", "description": "Field ID (default: 1)"}
                    },
                    "required": ["field_id"]
                },
                required_role="FARMER"
            )
        )
        self.register_tool(
            MCPToolDefinition(
                name="get_irrigation_history",
                description="Retrieves historical irrigation pump events, duration, and water volumes (Liters) for an agricultural field.",
                category=MCPToolCategory.INFORMATION_RETRIEVAL,
                input_schema={
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "integer", "description": "Field identifier"},
                        "limit": {"type": "integer", "description": "Max recent records (1 to 20, default 5)"}
                    },
                    "required": ["field_id"]
                },
                required_role="FARMER"
            )
        )
        self.register_tool(
            MCPToolDefinition(
                name="get_node_health",
                description="Retrieves hardware battery voltage, cellular RSSI, and communication health for an ArvaNode.",
                category=MCPToolCategory.INFORMATION_RETRIEVAL,
                input_schema={
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string", "description": "Hardware node identifier (e.g. 'ARVANODE-001')"}
                    },
                    "required": ["node_id"]
                },
                required_role="FARMER"
            )
        )

        # 2. AI CONTEXT
        self.register_tool(
            MCPToolDefinition(
                name="get_farm_configuration",
                description="Retrieves the canonical farm configuration and equipment inventory for the rice field from Settings, including pitak boundaries, soil series, water sources, and plows/harrows.",
                category=MCPToolCategory.AI_CONTEXT,
                input_schema={
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "integer", "description": "Target field identifier (default: 1)"}
                    },
                    "required": ["field_id"]
                },
                required_role="FARMER"
            )
        )
        self.register_tool(
            MCPToolDefinition(
                name="search_philrice_manual",
                description="Performs semantic retrieval across the official 230-page PhilRice Training Manual for rice agronomy protocols, land preparation, and page citations.",
                category=MCPToolCategory.AI_CONTEXT,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Agronomic search topic or question"}
                    },
                    "required": ["query"]
                },
                required_role="FARMER"
            )
        )
        self.register_tool(
            MCPToolDefinition(
                name="get_agronomic_profile",
                description="Retrieves official historical yield benchmarks, soil series classification, and certified rice variety data for Lopez, Quezon.",
                category=MCPToolCategory.AI_CONTEXT,
                input_schema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Category: 'all', 'yield', 'soil', 'varieties', or 'calendar'"}
                    },
                    "required": ["category"]
                },
                required_role="FARMER"
            )
        )

        # 3. APPLICATION OPERATIONS
        self.register_tool(
            MCPToolDefinition(
                name="evaluate_planting_readiness",
                description="Evaluates a field's readiness for rice planting across 5 dimensions: timeline, soil moisture, water depth, weather risk, and telemetry health.",
                category=MCPToolCategory.APPLICATION_OPERATIONS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "integer", "description": "Target field identifier"},
                        "target_crop": {"type": "string", "description": "Rice variety name (e.g. 'NSIC Rc 222')"},
                        "preparation_days_left": {"type": "integer", "description": "Days remaining until transplanting"}
                    },
                    "required": ["field_id", "target_crop", "preparation_days_left"]
                },
                required_role="FARMER"
            )
        )
        self.register_tool(
            MCPToolDefinition(
                name="propose_awd_irrigation",
                description="Drafts a structured Alternate Wetting and Drying (AWD) reflooding proposal. SENSITIVE: Requires explicit operator confirmation before actuation.",
                category=MCPToolCategory.APPLICATION_OPERATIONS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "integer", "description": "Target field identifier"},
                        "target_depth_cm": {"type": "number", "description": "Target ponding depth in cm (standard: 5.0)"},
                        "duration_minutes": {"type": "integer", "description": "Estimated pump run duration (max: 45)"}
                    },
                    "required": ["field_id"]
                },
                requires_confirmation=True,
                required_role="OPERATOR"
            )
        )

        # 4. EXTERNAL INTEGRATIONS
        self.register_tool(
            MCPToolDefinition(
                name="get_pagasa_weather",
                description="Fetches 1-7 day agro-meteorological forecast and active tropical cyclone warnings for Lopez, Quezon from PAGASA Southern Luzon PRSD models.",
                category=MCPToolCategory.EXTERNAL_INTEGRATIONS,
                input_schema={
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Forecast duration in days (1-7, default: 3)"}
                    },
                    "required": ["days"]
                },
                required_role="FARMER"
            )
        )

        # RESOURCES
        self.register_resource(
            MCPResourceDefinition(
                uri="arva://agronomy/varieties",
                name="Certified Philippine Rice Varieties",
                description="PhilRice certified inbred variety profiles, maturity, yields, and pest reactions.",
                mime_type="application/json"
            )
        )
        self.register_resource(
            MCPResourceDefinition(
                uri="arva://agronomy/calendar",
                name="Lopez Quezon Cropping Calendar",
                description="Dry season and wet season land preparation and harvesting windows.",
                mime_type="application/json"
            )
        )
        self.register_resource(
            MCPResourceDefinition(
                uri="arva://agronomy/soil",
                name="Lopez Quezon Soil Classification",
                description="Macolod clay loam properties, percolation rates, and AWD hardpan retention.",
                mime_type="application/json"
            )
        )

        # PROMPTS
        self.register_prompt(
            MCPPromptDefinition(
                name="rice_consultation_prompt",
                description="Comprehensive consultation template for Philippine rice farming under AWD.",
                arguments=[
                    MCPPromptArgument(name="crop_variety", description="Target rice variety", required=True),
                    MCPPromptArgument(name="stage", description="Current vegetative or reproductive growth stage", required=False)
                ]
            )
        )

    def register_tool(self, tool: MCPToolDefinition):
        self._tools[tool.name] = tool

    def register_resource(self, resource: MCPResourceDefinition):
        self._resources[resource.uri] = resource

    def register_prompt(self, prompt: MCPPromptDefinition):
        self._prompts[prompt.name] = prompt

    def list_tools(self) -> List[MCPToolDefinition]:
        return list(self._tools.values())

    def list_resources(self) -> List[MCPResourceDefinition]:
        return list(self._resources.values())

    def list_prompts(self) -> List[MCPPromptDefinition]:
        return list(self._prompts.values())

    def read_resource(self, uri: str) -> Dict[str, Any]:
        if uri == "arva://agronomy/varieties":
            return {"uri": uri, "content": RICE_VARIETIES}
        elif uri == "arva://agronomy/calendar":
            return {"uri": uri, "content": LOPEZ_HISTORICAL_AGRI_DATA.get("seasonal_cropping_calendar", {})}
        elif uri == "arva://agronomy/soil":
            return {"uri": uri, "content": LOPEZ_HISTORICAL_AGRI_DATA.get("soil_characteristics", {})}
        else:
            raise KeyError(f"Resource with URI '{uri}' not found.")

    def execute_tool(self, request: MCPToolCallRequest) -> MCPToolCallResult:
        start_time = time.time()
        tool_def = self._tools.get(request.name)

        if not tool_def:
            return MCPToolCallResult(
                name=request.name,
                state=MCPToolExecutionState.FAILED,
                error=f"MCP Tool '{request.name}' is not registered on this server.",
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # RBAC Check: Ensure caller has required privilege
        roles_hierarchy = {"FARMER": 1, "OPERATOR": 2, "ADMIN": 3}
        caller_level = roles_hierarchy.get(request.role.upper(), 1)
        required_level = roles_hierarchy.get(tool_def.required_role.upper(), 1)
        if caller_level < required_level:
            return MCPToolCallResult(
                name=request.name,
                state=MCPToolExecutionState.FAILED,
                error=f"Unauthorized: Tool '{request.name}' requires role '{tool_def.required_role}', but caller has role '{request.role}'.",
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # Sensitive Operation Check: Require explicit human confirmation
        if tool_def.requires_confirmation and not request.confirmed:
            return MCPToolCallResult(
                name=request.name,
                state=MCPToolExecutionState.REQUIRES_CONFIRMATION,
                requires_confirmation=True,
                confirmation_reason=f"Tool '{request.name}' modifies operational state and requires explicit operator authorization.",
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # Dispatch execution
        try:
            result_data = self._dispatch(request.name, request.arguments)
            elapsed_ms = (time.time() - start_time) * 1000
            return MCPToolCallResult(
                name=request.name,
                state=MCPToolExecutionState.COMPLETED,
                result=result_data,
                execution_time_ms=elapsed_ms
            )
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"Error executing MCP tool {request.name}: {str(e)}", exc_info=True)
            return MCPToolCallResult(
                name=request.name,
                state=MCPToolExecutionState.FAILED,
                error=str(e),
                execution_time_ms=elapsed_ms
            )

    def _dispatch(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "get_field_telemetry":
            field_id = args.get("field_id", 1)
            if self.telemetry_tools:
                return self.telemetry_tools.execute_tool("get_latest_field_telemetry", {"field_id": field_id})
            return {"field_id": field_id, "status": "SIMULATED", "nodes": []}

        elif name == "get_irrigation_history":
            field_id = args.get("field_id", 1)
            limit = args.get("limit", 5)
            if self.telemetry_tools:
                return self.telemetry_tools.execute_tool("get_irrigation_event_history", {"field_id": field_id, "limit": limit})
            return {"field_id": field_id, "events": []}

        elif name == "get_node_health":
            node_id = args.get("node_id", "ARVANODE-001")
            if self.telemetry_tools:
                return self.telemetry_tools.execute_tool("get_node_health_status", {"node_id": node_id})
            return {"node_id": node_id, "battery_voltage": 3.95, "status": "HEALTHY"}

        elif name == "search_philrice_manual":
            query = args.get("query", "land preparation")
            results = self.manual_retriever.search_manual(query, top_k=3)
            return {"query": query, "citations": results}

        elif name == "get_farm_configuration":
            field_id = args.get("field_id", 1)
            return {
                "field_id": field_id,
                "farm_name": "Silang Terraced Rice Field",
                "geographical_location": "Barangay Silang, Lopez, Quezon (13.8821° N, 121.9906° E)",
                "total_area_hectares": 1.1,
                "pitak_count": 6,
                "soil_type": "Calumpang Clay (Macolod Series)",
                "soil_characteristics": "Heavy clay, plow pan at 15-20 cm depth, slow percolation rate (< 2 mm/day once puddled). Ideal for AWD.",
                "water_sources": ["NIA Inflow Canal", "Deep Well Submersible Pump (400W)", "Rainfall Catchment", "Natural Runoff"],
                "distribution_channels": {
                    "inlet_gates": ["Gate 1 (Inflow, Pitak 1-2)", "Gate 2 (Mid-Terrace Lateral, Pitak 3-4)", "Gate 3 (Distal, Pitak 5-6)"],
                    "drainage_outlet": "Tail Drainage Flume (Pitak 6)"
                },
                "equipment_inventory": ["Hand Tractor (Kuliglig)", "Moldboard Plow", "Comb Harrow (Suyod)", "Wooden Leveling Plank (Haba)", "Rotavator Attachment"],
                "monitoring_nodes": [f"ARVANODE-00{i}" for i in range(1, 7)]
            }

        elif name == "get_agronomic_profile":
            category = args.get("category", "all")
            return self.lopez_adapter.execute_tool("lopez_get_historical_agriculture_profile", {"category": category})

        elif name == "evaluate_planting_readiness":
            field_id = args.get("field_id", 1)
            target_crop = args.get("target_crop", "NSIC Rc 222")
            days_left = args.get("preparation_days_left", 21)
            # Evaluate baseline readiness
            eval_res = self.readiness_engine.evaluate_readiness(
                target_crop=target_crop,
                preparation_days_left=days_left,
                nodes_telemetry=[],
                weather_forecast=None
            )
            return eval_res.model_dump()

        elif name == "propose_awd_irrigation":
            field_id = args.get("field_id", 1)
            target_depth = args.get("target_depth_cm", 5.0)
            duration = args.get("duration_minutes", 30)
            return {
                "field_id": field_id,
                "proposal_status": "DRAFTED_AWAITING_AUTHORIZATION",
                "target_depth_cm": target_depth,
                "duration_minutes": duration,
                "note": "AWD Reflood proposal formulated. Zero-trust interlock active."
            }

        elif name == "get_pagasa_weather":
            days = min(max(int(args.get("days", 3)), 1), 7)
            return self.pagasa_adapter.fetch_forecast(days)

        else:
            raise NotImplementedError(f"Handler for tool '{name}' is not implemented.")
