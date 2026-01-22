#!/usr/bin/env python3
import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.environ.pop('UNITY_MCP_SKIP_STARTUP_CONNECT', None)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)

from main import create_mcp_server, server_lifespan

async def test():
    mcp = create_mcp_server(project_scoped_tools=False)
    async with server_lifespan(mcp) as state:
        print(f"\n[TEST] Getting tools...")
        tools = await mcp.get_tools()
        print(f"[TEST] Total tools: {len(tools)}")

        weapon_tools = [t for t in tools if 'weapon' in t.lower()]
        print(f"[TEST] Weapon tools found: {len(weapon_tools)}")
        for tool in weapon_tools:
            print(f"  - {tool}")

            # Get tool details
            tool_obj = await mcp.get_tool(tool)
            if tool_obj:
                print(f"    inputSchema: {tool_obj.inputSchema}")

asyncio.run(test())
