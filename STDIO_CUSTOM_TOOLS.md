# Stdio Transport Custom Tools Support

## Overview

This feature enables custom Unity tools to be dynamically discovered and exposed to AI assistants (like Claude) when using stdio transport mode.

## Problem Solved

Previously, custom tools were only visible when using WebSocket transport because:
- Unity's WebSocket transport sends a `register_tools` message to the Python MCP server
- Stdio transport had no mechanism to communicate tool definitions
- The Python server only knew about its own built-in decorated tools

## Solution

### 1. Unity Tool: `list_unity_tools`

**File**: `MCPForUnity/Editor/Tools/ListUnityTools.cs`

A new MCP tool that queries Unity's `ToolDiscoveryService` and returns all enabled tool definitions in JSON format.

**Usage**:
```json
{
  "command": "list_unity_tools",
  "parameters": {
    "include_builtin": false
  }
}
```

**Response**:
```json
{
  "success": true,
  "data": {
    "tool_count": 4,
    "tools": [
      {
        "name": "create_weapon_base",
        "description": "Creates weapon base GameObject...",
        "is_builtin": false,
        "requires_polling": false,
        "parameters": [...]
      }
    ]
  }
}
```

### 2. Python Discovery Service

**File**: `Server/src/services/unity_tool_discovery.py`

Dynamically discovers and registers Unity custom tools:

**Key Functions**:
- `discover_and_register_unity_tools(mcp, unity_instance)`: Main discovery function
- `create_custom_tool_wrapper(tool_name, tool_def)`: Creates wrapper functions that forward to Unity

**How it works**:
1. Calls Unity's `list_unity_tools` command
2. For each custom tool, creates a Python wrapper function
3. Registers wrapper as a FastMCP tool with proper signature
4. Wrapper forwards all calls to Unity via stdio

### 3. Server Integration

**File**: `Server/src/main.py`

**Changes**:
- Line 8: Added import `from services.unity_tool_discovery import discover_and_register_unity_tools`
- Line 194-211: Added discovery call after Unity connection (2-second delay)

## Architecture Flow

```
1. Server starts (stdio transport)
   ↓
2. Connect to Unity via stdio
   ↓
3. After 2s delay → Call discover_and_register_unity_tools()
   ↓
4. Query Unity: list_unity_tools (returns custom tool definitions)
   ↓
5. For each custom tool:
   - Create Python wrapper function
   - Register as FastMCP tool
   ↓
6. AI assistant now sees custom tools as individual tools
   (e.g., create_weapon_base, create_weapon_preset, etc.)
```

## Files Modified/Created

### Unity (MCPForUnity)
- ✅ Created: `MCPForUnity/Editor/Tools/ListUnityTools.cs`
- ✅ Created: `MCPForUnity/Editor/Tools/ListUnityTools.cs.meta`

### Python (Server)
- ✅ Created: `Server/src/services/unity_tool_discovery.py`
- ✅ Modified: `Server/src/main.py` (added import and discovery call)

## Benefits

1. **Stdio Transport Compatible**: Custom tools work without WebSocket
2. **Automatic Discovery**: No manual registration needed
3. **Dynamic Registration**: Tools discovered at runtime
4. **Proper Signatures**: Each tool has its own signature with type hints
5. **First-Class Tools**: Custom tools appear as individual tools in AI tool list

## Testing

### 1. Verify Unity Compilation

```bash
# Open Unity Editor with MCPForUnity plugin
# Check Console for any errors
# Verify ListUnityTools appears in MCP for Unity window
```

### 2. Test Unity Tool Directly

In Unity Editor → MCP for Unity window → Tools tab:
- Find `list_unity_tools` in the tool list
- Click to test it

Expected: JSON response with custom tools.

### 3. Build and Install Package

```bash
cd /home/limam/Desktop/Github/unity-mcp/Server
python -m build
pip install --force-reinstall dist/mcpforunityserver-*.whl
```

### 4. Test with Claude

Start Claude with updated package:
```bash
# Claude Code should pick up the new version automatically
# Or restart Claude Code
```

From Claude, verify custom tools are visible:
- Check available tools
- Should see custom tools like `create_weapon_base`, etc.

### 5. Test Custom Tool Execution

From Claude:
```
Use the create_weapon_preset tool to create a simple_gun
```

Expected: Tool executes successfully and weapon is created in Unity.

## Limitations

1. **Startup Delay**: 2-second delay to avoid stdio handshake interference
2. **Runtime Registration**: Tools re-discovered if Unity restarts
3. **Single Instance**: Currently discovers from default Unity instance

## Future Improvements

1. Add `refresh_unity_tools` tool to manually trigger re-discovery
2. Support multi-instance tool discovery
3. Cache tool definitions to reduce startup latency
4. Add tool version tracking for change detection
