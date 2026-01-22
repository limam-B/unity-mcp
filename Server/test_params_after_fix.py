#!/usr/bin/env python3
"""Test parameter visibility after Unity-side fix"""

import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_params():
    try:
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "--directory", "/home/limam/Desktop/Github/unity-mcp/Server", "python", "-m", "main"],
            env=None,
        )

        print("[TEST] Connecting to MCP server...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("[TEST] Initializing...")
                await session.initialize()

                print("[TEST] Listing tools...")
                tools = await session.list_tools()

                weapon_tools = ['validate_weapon', 'create_weapon_base', 'configure_attachment_hooks',
                               'add_weapon_processors', 'create_weapon_preset']

                print(f"\n[TEST] Found {len(tools.tools)} total tools")
                print(f"[TEST] Checking weapon tools for parameters...\n")

                for tool in tools.tools:
                    if tool.name in weapon_tools:
                        print(f"===== {tool.name} =====")
                        print(f"Description: {tool.description[:80]}...")

                        # Check inputSchema
                        if hasattr(tool, 'inputSchema') and tool.inputSchema:
                            schema = tool.inputSchema
                            if isinstance(schema, dict):
                                props = schema.get('properties', {})
                                required = schema.get('required', [])

                                if props:
                                    print(f"✓ Parameters found: {len(props)}")
                                    for param_name, param_schema in props.items():
                                        req_marker = " (required)" if param_name in required else ""
                                        param_type = param_schema.get('type', 'unknown')
                                        param_desc = param_schema.get('description', 'No description')
                                        print(f"  - {param_name}: {param_type}{req_marker}")
                                        print(f"    {param_desc}")
                                else:
                                    print("✗ No parameters (empty schema)")
                            else:
                                print(f"✗ inputSchema is not a dict: {type(schema)}")
                        else:
                            print("✗ No inputSchema attribute")

                        print()

    except Exception as ex:
        print(f"[TEST] ERROR: {ex}")
        import traceback
        traceback.print_exc()

asyncio.run(test_params())
