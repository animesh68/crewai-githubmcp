import asyncio
import logging
import os
import sys
import threading
from typing import Dict, Any, List, Type
from pydantic import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

class MCPClientManager:
    """
    Manages the lifecycle of a connection to a Model Context Protocol (MCP) server
    and dynamically registers its tools as CrewAI/LangChain compatible tools.
    """
    def __init__(self, command: str, args: List[str], env: Dict[str, str] = None):
        self.command = command
        self.args = args
        self.env = env or {}
        # Ensure PATH is available in the environment to locate npx/node
        if "PATH" not in self.env:
            self.env["PATH"] = os.environ.get("PATH", "")
        
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        self._session = None
        self._client_ctx = None
        self._connected = False
        
        # Connect to the MCP server
        try:
            future = asyncio.run_coroutine_threadsafe(self._connect(), self.loop)
            future.result(timeout=15.0)  # Wait up to 15 seconds to connect
            self._connected = True
            logger.info("Successfully connected to MCP Server via stdio.")
        except Exception as e:
            logger.error(f"Failed to connect to MCP Server: {e}", exc_info=True)
            self.disconnect()
            raise RuntimeError(f"Could not initialize MCP Client: {e}")

    def _run_loop(self):
        """Runs the background event loop."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _connect(self):
        """Establishes the stdio subprocess and initializes the session."""
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env
        )
        logger.info(f"Spawning MCP Server subprocess: {self.command} {self.args}")
        self._client_ctx = stdio_client(server_params)
        self.read, self.write = await self._client_ctx.__aenter__()
        self._session = ClientSession(self.read, self.write)
        await self._session.__aenter__()
        await self._session.initialize()

    def disconnect(self):
        """Gracefully shuts down the session and terminates the background loop."""
        if not self.loop.is_closed():
            async def _disconnect():
                try:
                    if self._session:
                        await self._session.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error closing MCP session: {e}")
                try:
                    if self._client_ctx:
                        await self._client_ctx.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning(f"Error exiting stdio client context: {e}")
            
            try:
                future = asyncio.run_coroutine_threadsafe(_disconnect(), self.loop)
                future.result(timeout=5.0)
            except Exception as e:
                logger.error(f"Error during async disconnect cleanup: {e}")
            
            self.loop.call_soon_threadsafe(self.loop.stop)
            if self.thread.is_alive():
                self.thread.join(timeout=3.0)
            self._connected = False
            logger.info("MCP Client Manager disconnected and thread stopped.")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> str:
        """Invokes a tool on the MCP server and returns the output string."""
        if not self._connected:
            raise RuntimeError("MCP Client is not connected to the server.")
        
        async def _call():
            logger.debug(f"Calling MCP Tool: {name} with args: {arguments}")
            result = await self._session.call_tool(name, arguments)
            output = []
            for block in result.content:
                # TextContent is the typical block type returned by tools
                if hasattr(block, 'text'):
                    output.append(block.text)
                elif hasattr(block, 'content'):
                    output.append(str(block.content))
                else:
                    output.append(str(block))
            return "\n".join(output)
            
        try:
            future = asyncio.run_coroutine_threadsafe(_call(), self.loop)
            return future.result()
        except Exception as e:
            error_msg = f"Error executing tool '{name}': {e}"
            logger.error(error_msg, exc_info=True)
            return f"Error: {error_msg}"

    def _create_pydantic_model(self, schema_dict: Dict[str, Any], model_name: str) -> Type[BaseModel]:
        """Dynamically generates a Pydantic model class from a JSON input schema."""
        properties = schema_dict.get("properties", {})
        required = schema_dict.get("required", [])
        
        fields = {}
        for name, prop in properties.items():
            prop_type = prop.get("type", "string")
            prop_desc = prop.get("description", "")
            
            # Map JSON schema types to Python types
            py_type = Any
            if prop_type == "string":
                py_type = str
            elif prop_type == "integer":
                py_type = int
            elif prop_type == "number":
                py_type = float
            elif prop_type == "boolean":
                py_type = bool
            elif prop_type == "array":
                py_type = list
            elif prop_type == "object":
                py_type = dict
                
            if name in required:
                fields[name] = (py_type, Field(description=prop_desc))
            else:
                fields[name] = (py_type, Field(default=None, description=prop_desc))
                
        return create_model(model_name, **fields)

    def get_crewai_tools(self) -> List[StructuredTool]:
        """
        Retrieves the list of tools from the MCP server and wraps them
        into LangChain StructuredTool instances compatible with CrewAI.
        """
        if not self._connected:
            return []
            
        async def _list():
            return await self._session.list_tools()
            
        try:
            future = asyncio.run_coroutine_threadsafe(_list(), self.loop)
            mcp_tools = future.result()
        except Exception as e:
            logger.error(f"Failed to list MCP tools: {e}")
            return []
            
        crew_tools = []
        for t in mcp_tools.tools:
            name = t.name
            description = t.description or f"GitHub MCP tool: {name}"
            schema_dict = t.inputSchema if hasattr(t, 'inputSchema') else {}
            
            # Generate the dynamic Pydantic schema model
            schema_model = self._create_pydantic_model(schema_dict, f"{name}Input")
            
            # Define wrapper execution closure
            def make_executor(tool_name=name):
                def execute(**kwargs):
                    return self.call_tool(tool_name, kwargs)
                return execute
                
            structured_tool = StructuredTool(
                name=name,
                description=description,
                args_schema=schema_model,
                func=make_executor()
            )
            crew_tools.append(structured_tool)
            logger.debug(f"Wrapped MCP tool as StructuredTool: {name}")
            
        logger.info(f"Registered {len(crew_tools)} tools from GitHub MCP server.")
        return crew_tools

# Factory function to launch the GitHub MCP server
def create_github_mcp_client(github_token: str) -> MCPClientManager:
    """Helper factory to instantiate the GitHub MCP Server stdio client."""
    # Handle Windows vs Unix command resolution
    command = "npx.cmd" if sys.platform == "win32" else "npx"
    args = ["-y", "@modelcontextprotocol/server-github"]
    
    env = {
        "GITHUB_PERSONAL_ACCESS_TOKEN": github_token,
    }
    
    return MCPClientManager(command=command, args=args, env=env)
