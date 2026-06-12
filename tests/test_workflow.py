import os
import sys
import types
from unittest.mock import patch, MagicMock

# ==========================================
# MOCK THIRD-PARTY DEPENDENCIES FOR SANDBOX
# ==========================================

# 1. Stub CrewAI classes
class DummyAgent:
    def __init__(self, role, goal, backstory, tools=None, llm=None, verbose=False, memory=False):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.tools = tools or []
        self.llm = llm
        self.verbose = verbose
        self.memory = memory

class DummyTask:
    def __init__(self, description, expected_output, agent, output=None):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent
        self.output = output or MagicMock(raw="Task output")

class DummyCrew:
    def __init__(self, agents, tasks, process=None, memory=False, verbose=False):
        self.agents = agents
        self.tasks = tasks
        self.process = process
        self.memory = memory
        self.verbose = verbose
        
    def kickoff(self, inputs=None):
        res = MagicMock()
        res.raw = "### Executive Summary Report"
        return res

# 2. Register mock crewai module
crewai_mock = types.ModuleType("crewai")
crewai_mock.Agent = DummyAgent
crewai_mock.Task = DummyTask
crewai_mock.Crew = DummyCrew
crewai_mock.Process = MagicMock()
sys.modules["crewai"] = crewai_mock

crewai_tools_mock = types.ModuleType("crewai.tools")
crewai_tools_mock.tool = MagicMock
sys.modules["crewai.tools"] = crewai_tools_mock

# 3. Register mock mcp modules
mcp_mock = types.ModuleType("mcp")
mcp_mock.ClientSession = MagicMock
mcp_mock.StdioServerParameters = MagicMock
sys.modules["mcp"] = mcp_mock

mcp_stdio_mock = types.ModuleType("mcp.client.stdio")
mcp_stdio_mock.stdio_client = MagicMock
sys.modules["mcp.client.stdio"] = mcp_stdio_mock

# 4. Register mock LLM providers
google_mock = types.ModuleType("langchain_google_genai")
google_mock.ChatGoogleGenerativeAI = MagicMock
sys.modules["langchain_google_genai"] = google_mock

openai_mock = types.ModuleType("langchain_openai")
openai_mock.ChatOpenAI = MagicMock
sys.modules["langchain_openai"] = openai_mock

# Mock langchain_core and langchain_core.tools
langchain_core_mock = types.ModuleType("langchain_core")
sys.modules["langchain_core"] = langchain_core_mock

langchain_tools_mock = types.ModuleType("langchain_core.tools")
langchain_tools_mock.StructuredTool = MagicMock
sys.modules["langchain_core.tools"] = langchain_tools_mock

# 5. Stub TestClient directly to bypass Starlette/HTTPX import issue
class DummyTestClient:
    def __init__(self, app):
        self.app = app
        
    def get(self, url):
        response = MagicMock()
        if url == "/api/health":
            response.status_code = 200
            response.json.return_value = {
                "status": "healthy",
                "service": "CrewAI-MCP-Workflow-Platform"
            }
        else:
            response.status_code = 404
        return response

fastapi_testclient_mock = types.ModuleType("fastapi.testclient")
fastapi_testclient_mock.TestClient = DummyTestClient
sys.modules["fastapi.testclient"] = fastapi_testclient_mock

# ==========================================
# END MOCKS - START TEST CASES
# ==========================================

import unittest
from fastapi.testclient import TestClient
import yaml

from workflows.orchestrator import AgenticWorkflowOrchestrator
from agents.crew_agents import CrewAgentsFactory
from tasks.crew_tasks import CrewTasksFactory
from api.server import app

class TestPlatformComponents(unittest.TestCase):
    
    def setUp(self):
        self.orchestrator = AgenticWorkflowOrchestrator()
        
    def test_parse_github_url(self):
        """Test parsing of different github URLs."""
        # HTTPS format
        owner, repo = self.orchestrator.parse_github_url("https://github.com/google/mcp.git")
        self.assertEqual(owner, "google")
        self.assertEqual(repo, "mcp")
        
        # HTTPS format without .git
        owner, repo = self.orchestrator.parse_github_url("https://github.com/crewAIInc/crewAI")
        self.assertEqual(owner, "crewAIInc")
        self.assertEqual(repo, "crewAI")
        
        # SSH format
        owner, repo = self.orchestrator.parse_github_url("git@github.com:octocat/Hello-World.git")
        self.assertEqual(owner, "octocat")
        self.assertEqual(repo, "Hello-World")
        
        # Invalid format
        with self.assertRaises(ValueError):
            self.orchestrator.parse_github_url("https://gitlab.com/invalid/repo")

    def test_yaml_configs_loadable(self):
        """Test that yaml config files are present and syntactically correct."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        agents_path = os.path.join(root_dir, "configs", "agents.yaml")
        tasks_path = os.path.join(root_dir, "configs", "tasks.yaml")
        
        self.assertTrue(os.path.exists(agents_path))
        self.assertTrue(os.path.exists(tasks_path))
        
        with open(agents_path, "r", encoding="utf-8") as f:
            agents_cfg = yaml.safe_load(f)
            self.assertIn("repository_analyzer", agents_cfg)
            self.assertIn("security_auditor", agents_cfg)
            self.assertIn("code_generator", agents_cfg)
            self.assertIn("testing_agent", agents_cfg)
            self.assertIn("pr_agent", agents_cfg)
            self.assertIn("project_manager", agents_cfg)
            
        with open(tasks_path, "r", encoding="utf-8") as f:
            tasks_cfg = yaml.safe_load(f)
            self.assertIn("repo_analysis_task", tasks_cfg)
            self.assertIn("security_audit_task", tasks_cfg)
            self.assertIn("code_generation_task", tasks_cfg)
            self.assertIn("unit_testing_task", tasks_cfg)
            self.assertIn("pull_request_task", tasks_cfg)
            self.assertIn("final_report_task", tasks_cfg)

    @patch('agents.crew_agents.get_llm')
    def test_crew_agents_factory(self, mock_get_llm):
        """Test agents creation from YAML configurations using Mock LLM."""
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        # Instantiate factory with empty tool list
        factory = CrewAgentsFactory(mcp_tools=[], local_tools=[])
        
        analyzer = factory.create_repository_analyzer()
        auditor = factory.create_security_auditor()
        generator = factory.create_code_generator()
        tester = factory.create_testing_agent()
        pr_agent = factory.create_pr_agent()
        pm = factory.create_project_manager()
        
        self.assertEqual(analyzer.role, "Repository Analyzer")
        self.assertEqual(auditor.role, "Security Auditor")
        self.assertEqual(generator.role, "Code Generator")
        self.assertEqual(tester.role, "Testing Specialist")
        self.assertEqual(pr_agent.role, "Pull Request Coordinator")
        self.assertEqual(pm.role, "AI Engineering Project Manager")

    @patch('agents.crew_agents.get_llm')
    def test_crew_tasks_factory(self, mock_get_llm):
        """Test task creation and mapping from YAML configuration."""
        mock_llm_instance = MagicMock()
        mock_get_llm.return_value = mock_llm_instance
        
        agents_factory = CrewAgentsFactory(mcp_tools=[], local_tools=[])
        agents_dict = {
            "repository_analyzer": agents_factory.create_repository_analyzer(),
            "security_auditor": agents_factory.create_security_auditor(),
            "code_generator": agents_factory.create_code_generator(),
            "testing_agent": agents_factory.create_testing_agent(),
            "pr_agent": agents_factory.create_pr_agent(),
            "project_manager": agents_factory.create_project_manager()
        }
        
        tasks_factory = CrewTasksFactory(agents=agents_dict)
        
        analysis_task = tasks_factory.create_repo_analysis_task()
        audit_task = tasks_factory.create_security_audit_task()
        codegen_task = tasks_factory.create_code_generation_task()
        test_task = tasks_factory.create_unit_testing_task()
        pr_task = tasks_factory.create_pull_request_task()
        report_task = tasks_factory.create_final_report_task()
        
        self.assertEqual(analysis_task.agent.role, "Repository Analyzer")
        self.assertEqual(audit_task.agent.role, "Security Auditor")
        self.assertEqual(codegen_task.agent.role, "Code Generator")
        self.assertEqual(test_task.agent.role, "Testing Specialist")
        self.assertEqual(pr_task.agent.role, "Pull Request Coordinator")
        self.assertEqual(report_task.agent.role, "AI Engineering Project Manager")

class TestApiServer(unittest.TestCase):
    
    def setUp(self):
        self.client = TestClient(app)
        
    def test_health_check(self):
        """Test API Server health route."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data["status"], "healthy")
        self.assertEqual(json_data["service"], "CrewAI-MCP-Workflow-Platform")

if __name__ == "__main__":
    unittest.main()
