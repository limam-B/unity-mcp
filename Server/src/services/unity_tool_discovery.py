"""
Unity Tool Discovery Service
Dynamically discovers and registers Unity custom tools for stdio transport.
"""

import asyncio
import logging
from typing import Any, Dict, List

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from models.models import MCPResponse
from transport.legacy.unity_connection import (
    async_send_command_with_retry,
    get_unity_connection_pool,
)
from transport.unity_transport import send_with_unity_instance
from services.tools import get_unity_instance_from_context

logger = logging.getLogger("mcp-for-unity-server")


async def discover_and_register_unity_tools(mcp: FastMCP, unity_instance: str | None = None) -> Dict[str, Any]:
    """
    Queries Unity for custom tool definitions and dynamically registers them with FastMCP.

    Args:
        mcp: FastMCP instance to register tools with
        unity_instance: Optional Unity instance identifier. If None, uses default.

    Returns:
        Dict with discovery results (success, tool_count, tools)
    """
    try:
        logger.error(f"[Unity Tool Discovery] ⚠️⚠️⚠️ DISCOVERY FUNCTION CALLED ⚠️⚠️⚠️ instance={unity_instance}")
        logger.info(f"[Unity Tool Discovery] Querying Unity for custom tools (instance={unity_instance})")

        # Call Unity's list_unity_tools command to get custom tool definitions
        params = {"include_builtin": False}  # Only get custom tools

        response = await send_with_unity_instance(
            async_send_command_with_retry,
            unity_instance,
            "list_unity_tools",
            params,
        )

        if not isinstance(response, dict) or not response.get("success"):
            error_msg = response.get("message", "Unknown error") if isinstance(response, dict) else str(response)
            logger.error(f"[Unity Tool Discovery] Failed to query Unity tools: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "tool_count": 0,
                "tools": []
            }

        # Extract tool definitions from response
        logger.info(f"[Unity Tool Discovery] Raw response type: {type(response)}, keys: {response.keys() if isinstance(response, dict) else 'N/A'}")
        data = response.get("data", {})
        logger.info(f"[Unity Tool Discovery] Data keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        tools = data.get("tools", [])
        logger.info(f"[Unity Tool Discovery] Found {len(tools)} tools to register")

        if not tools:
            logger.info("[Unity Tool Discovery] No custom tools found in Unity")
            return {
                "success": True,
                "tool_count": 0,
                "tools": [],
                "message": "No custom tools to register"
            }

        # Register each custom tool dynamically
        registered_tools = []
        for tool_def in tools:
            try:
                tool_name = tool_def.get("name")
                if not tool_name:
                    logger.warning("[Unity Tool Discovery] Skipping tool with no name")
                    continue

                # Create a wrapper function for this custom tool
                logger.info(f"[Unity Tool Discovery] Processing tool: {tool_name}")
                wrapper_func = create_custom_tool_wrapper(tool_name, tool_def)

                # Register with FastMCP
                description = tool_def.get("description", f"Custom Unity tool: {tool_name}")
                annotations = ToolAnnotations(
                    title=tool_name,
                    destructiveHint=True,  # Custom tools may modify Unity state
                )

                # Apply @mcp.tool decorator
                # Note: FastMCP infers inputSchema from function signature, no need to pass it
                logger.info(f"[Unity Tool Discovery] Registering {tool_name} with FastMCP...")
                mcp.tool(
                    name=tool_name,
                    description=description,
                    annotations=annotations
                )(wrapper_func)

                registered_tools.append(tool_name)
                logger.info(f"[Unity Tool Discovery] ✓ Registered custom tool: {tool_name}")

            except Exception as ex:
                logger.error(f"[Unity Tool Discovery] Failed to register tool {tool_def.get('name')}: {ex}")

        result = {
            "success": True,
            "tool_count": len(registered_tools),
            "tools": registered_tools,
            "message": f"Registered {len(registered_tools)} custom Unity tools"
        }

        logger.info(f"[Unity Tool Discovery] Successfully registered {len(registered_tools)} custom tools: {', '.join(registered_tools)}")
        return result

    except Exception as ex:
        logger.error(f"[Unity Tool Discovery] Failed to discover Unity tools: {ex}", exc_info=True)
        return {
            "success": False,
            "error": str(ex),
            "tool_count": 0,
            "tools": []
        }


def create_custom_tool_wrapper(tool_name: str, tool_def: Dict[str, Any]):
    """
    Creates a wrapper function that forwards calls to Unity's custom tool.

    Uses exec() to dynamically generate functions with proper signatures
    since FastMCP doesn't support **kwargs.

    Args:
        tool_name: Name of the Unity custom tool
        tool_def: Tool definition metadata from Unity

    Returns:
        Async function that can be registered as an MCP tool
    """
    # Extract parameter definitions
    param_defs = tool_def.get("parameters", [])

    # Build parameter list for function signature
    param_list = ["ctx: Context"]
    param_names = []

    for param in param_defs:
        param_name = param.get("name")
        param_type_str = param.get("type", "string").lower()
        param_required = param.get("required", False)

        # Map Unity types to Python type hints
        type_mapping = {
            "string": "str",
            "int": "int",
            "integer": "int",
            "float": "float",
            "number": "float",
            "bool": "bool",
            "boolean": "bool",
            "object": "dict",
            "array": "list",
        }

        py_type = type_mapping.get(param_type_str, "Any")

        # Make optional if not required
        if not param_required:
            param_list.append(f"{param_name}: {py_type} | None = None")
        else:
            param_list.append(f"{param_name}: {py_type}")

        param_names.append(param_name)

    # Generate function code dynamically
    func_params = ", ".join(param_list)
    params_dict = "{" + ", ".join([f"'{p}': {p}" for p in param_names]) + "}"

    func_code = f'''
async def {tool_name}_wrapper({func_params}) -> MCPResponse:
    """Dynamically generated wrapper for Unity custom tool."""
    unity_instance = get_unity_instance_from_context(ctx)
    if not unity_instance:
        return MCPResponse(
            success=False,
            message="No active Unity instance. Call set_active_instance with Name@hash from mcpforunity://instances.",
        )

    # Build parameters dict
    params = {params_dict}
    # Remove None values for optional parameters
    params = {{k: v for k, v in params.items() if v is not None}}

    try:
        response = await send_with_unity_instance(
            async_send_command_with_retry,
            unity_instance,
            "{tool_name}",
            params,
        )

        # Normalize response
        if isinstance(response, MCPResponse):
            return response

        if isinstance(response, dict):
            return MCPResponse(
                success=response.get("success", True),
                message=response.get("message"),
                error=response.get("error"),
                data=response.get("data", response) if "data" not in response else response["data"],
            )

        # Fallback for non-dict responses
        return MCPResponse(
            success=True,
            data=response,
            message=f"Tool {tool_name} executed successfully"
        )

    except Exception as ex:
        logger.error(f"[Unity Tool Wrapper] Failed to execute {tool_name}: {{ex}}")
        return MCPResponse(
            success=False,
            error=str(ex),
            message=f"Failed to execute Unity tool {tool_name}"
        )
'''

    # Execute the function definition
    namespace = {
        "Context": Context,
        "MCPResponse": MCPResponse,
        "get_unity_instance_from_context": get_unity_instance_from_context,
        "send_with_unity_instance": send_with_unity_instance,
        "async_send_command_with_retry": async_send_command_with_retry,
        "logger": logger,
        "Any": Any,
    }

    exec(func_code, namespace)
    wrapper_func = namespace[f"{tool_name}_wrapper"]

    # Set metadata
    wrapper_func.__name__ = tool_name
    wrapper_func.__doc__ = tool_def.get("description", f"Custom Unity tool: {tool_name}")

    return wrapper_func
