#!/usr/bin/env python3
"""Quick test to check if parameters are now visible"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_params():
    try:
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "--directory", "/home/limam/Desktop/Github/unity-mcp/Server", "python", "-m", "main"],
            env=None,
        )

        print("[TEST] Connecting...")
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                print("[TEST] Initializing...")
                await session.initialize()
                print("[TEST] Listing tools...")
                tools = await session.list_tools()

                print(f"[TEST] Found {len(tools.tools)} total tools")

                # Check validate_weapon
                found = False
                for tool in tools.tools:
                    if tool.name == "validate_weapon":
                        found = True
                        print(f"\n===== {tool.name} =====")
                        print(f"Description: {tool.description}")
                        print(f"Input Schema: {tool.inputSchema}")
                        break

                if not found:
                    print("[TEST] validate_weapon not found!")

    except Exception as ex:
        print(f"[TEST] ERROR: {ex}")
        import traceback
        traceback.print_exc()

asyncio.run(test_params())
