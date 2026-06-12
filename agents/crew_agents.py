import os
import yaml
import logging
from typing import List, Dict, Any
from crewai import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

def get_llm():
    """Configures and returns the LangChain LLM backend according to the environment configurations."""
    provider = os.getenv("MODEL_PROVIDER", "gemini").lower()
    model_name = os.getenv("MODEL_NAME")
    
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
        logger.info(f"Configuring Gemini LLM backend with model: {model_name or 'gemini-1.5-pro'}")
        return ChatGoogleGenerativeAI(
            model=model_name or "gemini-1.5-pro",
            google_api_key=api_key,
            temperature=0.2
        )
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        logger.info(f"Configuring OpenAI LLM backend with model: {model_name or 'gpt-4o'}")
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            api_key=api_key,
            temperature=0.2
        )
    else:
        raise ValueError(f"Unsupported MODEL_PROVIDER '{provider}'. Must be 'gemini' or 'openai'.")

class CrewAgentsFactory:
    """Factory to create CrewAI Agents with YAML configurations and specific tool lists."""
    def __init__(self, mcp_tools: List[Any] = None, local_tools: List[Any] = None):
        self.mcp_tools = mcp_tools or []
        self.local_tools = local_tools or []
        self.llm = get_llm()
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads agent configuration from YAML file."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs",
            "agents.yaml"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load agents config from {config_path}: {e}")
            raise

    def _filter_mcp_tools(self, keywords: List[str]) -> List[Any]:
        """Filters MCP tools based on key substrings in their names."""
        return [t for t in self.mcp_tools if any(kw in t.name for kw in keywords)]

    def _get_local_tool(self, name: str) -> Any:
        """Retrieves a local custom tool by its name."""
        for tool in self.local_tools:
            if tool.name == name:
                return tool
        return None

    def create_repository_analyzer(self) -> Agent:
        cfg = self.config["repository_analyzer"]
        # Repository Analyzer needs read MCP tools and local read tool
        tools = self._filter_mcp_tools(["get_file_contents", "search_code", "get_repo"])
        local_read = self._get_local_tool("read_local_file")
        if local_read:
            tools.append(local_read)
            
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True,
            memory=True
        )

    def create_security_auditor(self) -> Agent:
        cfg = self.config["security_auditor"]
        # Security Auditor needs read MCP tools and local read tool
        tools = self._filter_mcp_tools(["get_file_contents", "search_code", "get_repo"])
        local_read = self._get_local_tool("read_local_file")
        if local_read:
            tools.append(local_read)
            
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True,
            memory=True
        )

    def create_code_generator(self) -> Agent:
        cfg = self.config["code_generator"]
        # Code Generator needs write/file-update MCP tools and local read/write/test tools
        tools = self._filter_mcp_tools(["create_or_update_file", "search_code", "get_file_contents"])
        local_read = self._get_local_tool("read_local_file")
        local_write = self._get_local_tool("write_local_file")
        local_test = self._get_local_tool("run_local_tests")
        
        if local_read: tools.append(local_read)
        if local_write: tools.append(local_write)
        if local_test: tools.append(local_test)
        
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True,
            memory=True
        )

    def create_testing_agent(self) -> Agent:
        cfg = self.config["testing_agent"]
        # Testing Agent needs file edit tools and running test tools
        tools = self._filter_mcp_tools(["create_or_update_file", "get_file_contents"])
        local_read = self._get_local_tool("read_local_file")
        local_write = self._get_local_tool("write_local_file")
        local_test = self._get_local_tool("run_local_tests")
        
        if local_read: tools.append(local_read)
        if local_write: tools.append(local_write)
        if local_test: tools.append(local_test)
        
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True,
            memory=True
        )

    def create_pr_agent(self) -> Agent:
        cfg = self.config["pr_agent"]
        # PR agent needs branch creation, commit and pull request MCP tools
        tools = self._filter_mcp_tools([
            "create_branch", 
            "create_pull_request", 
            "create_or_update_file",
            "get_file_contents"
        ])
        local_git = self._get_local_tool("git_commit_and_push")
        if local_git:
            tools.append(local_git)
        
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True
        )

    def create_project_manager(self) -> Agent:
        cfg = self.config["project_manager"]
        # PM needs issues and comment management tools to overview the work
        tools = self._filter_mcp_tools([
            "get_issue", 
            "list_issues", 
            "add_issue_comment", 
            "get_pull_request", 
            "list_pull_requests"
        ])
        
        return Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            tools=tools,
            llm=self.llm,
            verbose=True
        )
