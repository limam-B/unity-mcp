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
        data = response.get("data", {})
        tools = data.get("tools", [])

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
                wrapper_func = create_custom_tool_wrapper(tool_name, tool_def)

                # Register with FastMCP
                description = tool_def.get("description", f"Custom Unity tool: {tool_name}")
                annotations = ToolAnnotations(
                    title=tool_name,
                    destructiveHint=True,  # Custom tools may modify Unity state
                )

                # Apply @mcp.tool decorator
                mcp.tool(
                    name=tool_name,
                    description=description,
                    annotations=annotations
                )(wrapper_func)

                registered_tools.append(tool_name)
                logger.info(f"[Unity Tool Discovery] Registered custom tool: {tool_name}")

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

    Args:
        tool_name: Name of the Unity custom tool
        tool_def: Tool definition metadata from Unity

    Returns:
        Async function that can be registered as an MCP tool
    """
    # Extract parameter definitions
    param_defs = tool_def.get("parameters", [])

    # Create the wrapper function with dynamic signature
    async def wrapper_func(ctx: Context, **kwargs) -> MCPResponse:
        """Dynamically generated wrapper for Unity custom tool."""
        unity_instance = get_unity_instance_from_context(ctx)
        if not unity_instance:
            return MCPResponse(
                success=False,
                message="No active Unity instance. Call set_active_instance with Name@hash from mcpforunity://instances.",
            )

        # Forward all kwargs to Unity
        try:
            response = await send_with_unity_instance(
                async_send_command_with_retry,
                unity_instance,
                tool_name,
                kwargs,
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
            logger.error(f"[Unity Tool Wrapper] Failed to execute {tool_name}: {ex}")
            return MCPResponse(
                success=False,
                error=str(ex),
                message=f"Failed to execute Unity tool {tool_name}"
            )

    # Set function metadata for FastMCP
    wrapper_func.__name__ = tool_name
    wrapper_func.__doc__ = tool_def.get("description", f"Custom Unity tool: {tool_name}")

    # Add parameter annotations dynamically
    # FastMCP will introspect the function signature
    annotations = wrapper_func.__annotations__ = {"ctx": Context, "return": MCPResponse}

    # Add parameter types from Unity metadata
    for param in param_defs:
        param_name = param.get("name")
        param_type = param.get("type", "string")

        # Map Unity types to Python types
        type_mapping = {
            "string": str,
            "int": int,
            "float": float,
            "bool": bool,
            "object": dict,
            "array": list,
        }

        python_type = type_mapping.get(param_type.lower(), Any)

        # Make parameter optional if not required
        if not param.get("required", False):
            python_type = python_type | None

        annotations[param_name] = python_type

    return wrapper_func
