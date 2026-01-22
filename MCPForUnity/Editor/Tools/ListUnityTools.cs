// ------------------------------------------------------------------------------
// <summary>
//     ListUnityTools.cs
//     MCP tool for listing all Unity tool definitions (used by stdio transport)
// </summary>
// ------------------------------------------------------------------------------

using System;
using System.Collections.Generic;
using System.Linq;
using MCPForUnity.Editor.Helpers;
using MCPForUnity.Editor.Services;
using Newtonsoft.Json.Linq;

namespace MCPForUnity.Editor.Tools
{
    [McpForUnityTool("list_unity_tools",
        Description = "Lists all Unity tool definitions with metadata. Used by Python MCP server to dynamically register custom tools for stdio transport.",
        AutoRegister = true)]
    public static class ListUnityTools
    {
        public class Parameters
        {
            [ToolParameter("Include built-in tools (default: false)", Required = false)]
            public bool include_builtin = false;
        }

        public static object HandleCommand(JObject @params)
        {
            try
            {
                McpLog.Info("[ListUnityTools] Listing Unity tool definitions");

                // Parse parameters
                bool includeBuiltin = @params["include_builtin"]?.Value<bool>() ?? false;

                // Get tool discovery service
                var toolDiscoveryService = MCPServiceLocator.ToolDiscovery;
                if (toolDiscoveryService == null)
                {
                    return new ErrorResponse("ToolDiscoveryService not available");
                }

                // Get all enabled tools
                var allTools = toolDiscoveryService.GetEnabledTools();

                // Filter based on includeBuiltin parameter
                var tools = includeBuiltin
                    ? allTools
                    : allTools.Where(t => !t.IsBuiltIn).ToList();

                // Convert to JSON-friendly format
                var toolDefinitions = tools.Select(tool => new
                {
                    name = tool.Name,
                    description = tool.Description ?? "",
                    is_builtin = tool.IsBuiltIn,
                    requires_polling = tool.RequiresPolling,
                    poll_action = tool.PollAction ?? "status",
                    parameters = tool.Parameters?.Select(p => new
                    {
                        name = p.Name,
                        description = p.Description ?? "",
                        type = p.Type ?? "string",
                        required = p.Required,
                        default_value = p.DefaultValue
                    }).ToArray() ?? new object[0]
                }).ToArray();

                var responseData = new
                {
                    success = true,
                    tool_count = toolDefinitions.Length,
                    tools = toolDefinitions
                };

                McpLog.Info($"[ListUnityTools] Found {toolDefinitions.Length} tools (includeBuiltin={includeBuiltin})");
                return new SuccessResponse($"Listed {toolDefinitions.Length} Unity tools", responseData);
            }
            catch (Exception ex)
            {
                McpLog.Error($"[ListUnityTools] Failed to list tools: {ex.Message}");
                McpLog.Error($"[ListUnityTools] Stack trace: {ex.StackTrace}");
                return new ErrorResponse($"Failed to list Unity tools: {ex.Message}");
            }
        }
    }
}
