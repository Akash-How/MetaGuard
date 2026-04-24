import json
import os
import asyncio
from typing import Any, AsyncGenerator

from contextlib import AsyncExitStack
from groq import Groq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core.config import get_settings

# Configure logging to a file for runtime debugging
import logging
runtime_logger = logging.getLogger("mcp_agent_runtime")
runtime_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(os.path.join(os.getcwd(), "agent_runtime.log"), mode="a", encoding="utf-8")
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
runtime_logger.addHandler(file_handler)

class McpAgent:
    """
    The central orchestration engine that connects to multiple MCP servers 
    and handles the agentic loop using Groq.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.persistence_path = os.path.join(os.getcwd(), ".groq_rotation.json")
        self._current_groq_idx = self._load_rotation_index()
        self._init_groq_client()
        self.config_path = os.path.join(os.getcwd(), "mcp_config.json")
        self.sessions: dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self.history: dict[str, list[dict]] = {}

    def _load_rotation_index(self) -> int:
        """Loads the last used Groq key index from disk."""
        try:
            if os.path.exists(self.persistence_path):
                with open(self.persistence_path, "r") as f:
                    data = json.load(f)
                    return data.get("current_idx", 0)
        except Exception as e:
            runtime_logger.warning(f"Failed to load rotation index: {e}")
        return 0

    def _save_rotation_index(self):
        """Saves the current Groq key index to disk."""
        try:
            with open(self.persistence_path, "w") as f:
                json.dump({"current_idx": self._current_groq_idx}, f)
        except Exception as e:
            runtime_logger.warning(f"Failed to save rotation index: {e}")

    def _init_groq_client(self):
        keys = self.settings.groq_api_key_list
        runtime_logger.info(f"GROQ_DEBUG: Found {len(keys)} keys in settings.")
        if not keys:
            runtime_logger.error("No Groq API keys found in settings.")
            self.groq_client = None
            return
        
        idx = self._current_groq_idx % len(keys)
        selected_key = keys[idx]
        # Only log the prefix for security
        runtime_logger.info(f"Initialized Groq client with key starting with: {selected_key[:7]}...")
        self.groq_client = Groq(api_key=selected_key)

    async def _get_config(self) -> dict:
        if not os.path.exists(self.config_path):
            return {"mcpServers": {}}
        with open(self.config_path, "r") as f:
            return json.load(f)

    async def connect_servers(self):
        """Initializes connections to all configured MCP servers."""
        config = await self._get_config()
        servers = config.get("mcpServers", {})

        for name, params in servers.items():
            if name in self.sessions:
                continue
            
            try:
                print(f"Connecting to MCP server: {name}...")
                server_params = StdioServerParameters(
                    command=params["command"],
                    args=params.get("args", []),
                    env={**os.environ, **params.get("env", {})}
                )
                
                # Using ExitStack to manage the context managers for each server connection
                stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
                read, write = stdio_transport
                session = await self.exit_stack.enter_async_context(ClientSession(read, write))
                
                await session.initialize()
                self.sessions[name] = session
                print(f"Connected to {name} successfully.")
            except Exception as e:
                print(f"Failed to connect to MCP server '{name}': {str(e)}")
                # Continue to next server instead of crashing everything
                continue

    def _sanitize_json_schema(self, schema: Any) -> Any:
        """
        Recursively cleans up JSON schemas to make them Groq/OpenAI compatible.
        - Converts type arrays ['string', 'null'] -> 'string'
        - Simplifies oneOf/anyOf to the first valid object/type
        - Removes unsupported keywords for function calling
        """
        if not isinstance(schema, dict):
            return schema

        new_schema = {}
        for k, v in schema.items():
            if k == "type" and isinstance(v, list):
                # Groq requires a single type string. Default to the most conservative one.
                # Usually ['string', 'null'] or ['boolean', 'string']
                potential_types = [t for t in v if t != "null"]
                new_schema[k] = potential_types[0] if potential_types else "string"
            elif k in ["anyOf", "oneOf"] and isinstance(v, list) and len(v) > 0:
                # Use the first option in the choice list
                return self._sanitize_json_schema(v[0])
            elif isinstance(v, dict):
                new_schema[k] = self._sanitize_json_schema(v)
            elif isinstance(v, list):
                new_schema[k] = [self._sanitize_json_schema(i) if isinstance(i, dict) else i for i in v]
            else:
                new_schema[k] = v
        return new_schema

    async def get_all_tools(self) -> list[dict[str, Any]]:
        """Aggregates tool definitions from all active MCP sessions with selective filtering."""
        all_tools = []
        
        # Define whitelists for external servers to keep token count low
        WHITELISTS = {
            "slack": ["slack_list_channels"]
        }

        for name, session in self.sessions.items():
            result = await session.list_tools()
            for tool in result.tools:
                # If a whitelist exists for this server, skip tools not on it
                if name in WHITELISTS and tool.name not in WHITELISTS[name]:
                    continue

                # Sanitize the input schema for Groq compatibility
                sanitized_params = self._sanitize_json_schema(tool.inputSchema)
                
                groq_tool = {
                    "type": "function",
                    "function": {
                        "name": f"{name}__{tool.name}",
                        "description": tool.description,
                        "parameters": sanitized_params
                    }
                }
                all_tools.append(groq_tool)
        return all_tools

    async def run_loop(self, user_query: str, session_id: str = "default", entity_id: str = None) -> str:
        """The core agentic loop: Prompt -> Tool Call -> Execution -> Final Response."""
        if not self.sessions:
            await self.connect_servers()

        tools = await self.get_all_tools()
        
        # System instructions
        system_content = (
            f"You are the MetaGuard AI Orchestrator, a high-intelligence agent designed to discover, understand, and protect data assets using OpenMetadata.\n"
            f"Current Active Context: You are assisting with the asset: '{entity_id}'.\n\n"
            "MISSION & TONE:\n"
            "- Be proactive and impactful. You don't just report; you solve.\n"
            "- If you see data waste (Dead Data) or stability risks (Storm Warning/Blast Radius), ADVOCATE for action.\n"
            "- Always prefer dynamic tool use over static explanations.\n\n"
            "TECHNICAL CAPABILITIES:\n"
            "1. MetaGuard Hub (`metaguard__` prefix): Audit health, lineage, and cost. Create Google Sheets for deep-dives. Post actionable summaries to Slack.\n"
            "2. Slack Hub (`slack__` prefix): Manage communications.\n\n"
            "OPERATIONAL GUIDELINES:\n"
            "- DYNAMIC EXPORTS: When users ask for reports or summaries, proactively offer to 'Create a Google Sheet' for them. Do not rely on pre-existing templates; build them dynamically.\n"
            "- CROSS-TOOL CHAINING: You are encouraged to chain tools. Example: `list_dead_data` -> `create_google_sheet` (to log findings) -> `post_to_slack_with_link` (to notify the team).\n"
            "- SLACK LINKS: When using `metaguard__post_to_slack_with_link`, always provide the returned URL in your final response as a clickable Markdown link: `[🔗 View Thread on Slack](URL)`.\n"
            "- GOOGLE SHEETS: Ensure the `rows` parameter is always an array of arrays. If you create a sheet, give it a professional title like 'MetaGuard Audit: [Topic]'.\n\n"
            "GOVERNANCE & TRUST:\n"
            "- You respect OpenMetadata ownership. If you recommend a deletion, mention the owner found in the metadata.\n"
            "- Never hallucinate IDs. Use search tools if you don't have a specific ID.\n"
            "- If an operation fails, explain the technical root cause (e.g., API permissions) and suggest a workaround."
        )

        # Retrieve or initialize session history
        if session_id not in self.history:
            self.history[session_id] = []
        
        # Always enforce the latest system context at index 0
        if not self.history[session_id] or self.history[session_id][0]["role"] != "system":
            self.history[session_id].insert(0, {"role": "system", "content": system_content})
        else:
            self.history[session_id][0]["content"] = system_content
        
        # Add the new user query to the history
        messages = self.history[session_id]
        messages.append({"role": "user", "content": user_query})

        # Keep a sliding window of history to prevent context overflow (keep system + last 10 messages)
        messages = messages[0:1] + messages[-11:]
        self.history[session_id] = messages

        # Track executed tools in THIS session to prevent loops
        executed_signatures = set()

        # Limit to 10 iterations to prevent infinite loops
        for _ in range(10):
            if not self.groq_client:
                return "MetaGuard Configuration Error: Your GROQ_API_KEY is missing or invalid on the server. Please check your Railway environment variables."
                
            try:
                response = self.groq_client.chat.completions.create(
                    model=self.settings.groq_model_default,
                    messages=messages,
                    tools=tools if tools else None,
                    tool_choice="auto"
                )
            except Exception as api_err:
                error_details = str(api_err)
                is_rate_limit = "429" in error_details or "rate_limit_exceeded" in error_details
                is_auth_error = "401" in error_details or "invalid_api_key" in error_details
                is_tool_error = "400" in error_details or "tool_use_failed" in error_details
                
                # Handle rotation for 401/429
                if (is_rate_limit or is_auth_error) and self.settings.groq_api_key_list:
                    runtime_logger.warning(f"Groq Key failed ({'Rate Limit' if is_rate_limit else 'Invalid Key'}). Rotating...")
                    self._current_groq_idx += 1
                    self._save_rotation_index()
                    self._init_groq_client()
                    continue

                # RECOVERY LOGIC: If Groq failed because the model's text looked like a bad tool call,
                # but it actually contains a useful final answer (like a link), harvest it!
                if is_tool_error:
                    try:
                        import re
                        # Extract the 'failed_generation' from the Groq error payload
                        failed_gen = ""
                        if hasattr(api_err, "body") and isinstance(api_err.body, dict):
                            failed_gen = api_err.body.get("error", {}).get("failed_generation", "")
                        
                        # If the failed generation contains a markdown link or a URL, it's likely a valid response
                        if "[" in failed_gen and "http" in failed_gen:
                            runtime_logger.info(f"Harvested valid response from failed tool call: {failed_gen}")
                            return failed_gen
                    except Exception as harvest_err:
                        runtime_logger.warning(f"Failed to harvest response: {harvest_err}")

                    runtime_logger.warning(f"Tool call failed formatting. Hinting to model. Details: {error_details}")
                    messages.append({"role": "system", "content": f"ERROR: Your last tool call was malformed. Ensure you use the standard tool-call API and valid JSON. Details: {error_details}"})
                    continue

                runtime_logger.error(f"Terminal Groq API Error. Details: {error_details}")
                
                # Only fallback if it's truly a persistent rate limit or unknown terminal error
                fallback_messages = messages + [{"role": "system", "content": "SYSTEM ALERT: High latency detected. Attempting to answer without some technical tools. Explain this gracefully."}]
                
                response = self.groq_client.chat.completions.create(
                    model=self.settings.groq_model_default,
                    messages=fallback_messages
                )

            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            if not assistant_message.tool_calls:
                # Once we have a final assistant content, ensure it's in history
                return assistant_message.content

            # Keep track if we were in a tool-calling sequence
            had_tool_calls = True
            for tool_call in assistant_message.tool_calls:
                full_name = tool_call.function.name
                
                # SAFETY CATCH: If the model 'hallucinates' a link as a tool name, convert it to context
                if "[" in full_name or "(" in full_name:
                    runtime_logger.warning(f"Trapped link-as-function hallucination: {full_name}")
                    return f"I've generated your report/link: {full_name}"
                
                # Auto-correction for missing prefixes (very common in 17b models)
                if "__" not in full_name:
                    matching_tools = [t["function"]["name"] for t in tools if t["function"]["name"].endswith(f"__{full_name}")]
                    if matching_tools:
                        runtime_logger.info(f"Auto-correcting {full_name} -> {matching_tools[0]}")
                        full_name = matching_tools[0]
                
                if "__" in full_name:
                    server_name, tool_name = full_name.split("__", 1)
                else:
                    server_name, tool_name = "unknown", full_name
                
                arguments = json.loads(tool_call.function.arguments)

                # LOOP SUPPRESSION: Prevent exact same tool/args call twice in one turn
                call_sig = f"{full_name}:{json.dumps(arguments, sort_keys=True)}"
                if call_sig in executed_signatures:
                    runtime_logger.warning(f"Suppressed redundant tool call: {call_sig}")
                    continue
                executed_signatures.add(call_sig)

                # HEURISTIC FIX: Llama models often hallucinate template tags like "{{#rows}}" 
                # or flat arrays when they should send nested ones.
                if tool_name == "create_google_sheet" and "rows" in arguments:
                    rows = arguments["rows"]
                    # If it's a string hallucination (likely a template tag), clear it or try to recover
                    if isinstance(rows, str):
                        runtime_logger.warning(f"Agent sent string for rows: '{rows}'. Resetting to empty list.")
                        arguments["rows"] = []
                    # If it's a flat array of strings, wrap it into an array of arrays (1 row)
                    elif isinstance(rows, list) and len(rows) > 0 and not isinstance(rows[0], (list, dict)):
                        runtime_logger.warning("Agent sent flat array for rows. Auto-correcting to array-of-arrays.")
                        arguments["rows"] = [rows]

                runtime_logger.info(f"Calling {server_name}:{tool_name} with {arguments}")
                
                if server_name not in self.sessions:
                    tool_result = f"Error: Server {server_name} not found."
                else:
                    try:
                        session = self.sessions[server_name]
                        result = await session.call_tool(tool_name, arguments)
                        # Extract only the text content from the MCP result objects
                        tool_result = "\n".join([c.text for c in result.content if hasattr(c, "text")])
                    except Exception as e:
                        tool_result = f"Error executing tool: {str(e)}"

                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": full_name,
                    "content": tool_result
                })

            # After processing all tool calls in an iteration, if we are about to call the LLM again,
            # we can add a small hint if it's the 10th iteration or if we just finished a complex tool
            if had_tool_calls:
                messages.append({
                    "role": "system", 
                    "content": "You have all the information needed. Provide your FINAL ANSWER to the user now. Do not call any more tools unless absolutely necessary."
                })

        return "Agentic loop exceeded maximum iterations."

    async def close(self):
        await self.exit_stack.aclose()

# Singleton instance
_agent = None

async def get_mcp_agent() -> McpAgent:
    global _agent
    if _agent is None:
        _agent = McpAgent()
        await _agent.connect_servers()
    return _agent
