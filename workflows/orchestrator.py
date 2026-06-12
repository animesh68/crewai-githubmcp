import os
import re
import random
import string
import logging
import subprocess
from typing import Dict, Any, Tuple
from dotenv import load_dotenv

from tools.mcp_client import create_github_mcp_client
from tools.custom_tools import read_local_file, write_local_file, run_local_tests, git_commit_and_push
from agents.crew_agents import CrewAgentsFactory
from tasks.crew_tasks import CrewTasksFactory
from crew import create_engineering_crew

load_dotenv()
logger = logging.getLogger(__name__)

class AgenticWorkflowOrchestrator:
    """
    Coordinates repository setup, branches, MCP connection lifecycle, 
    CrewAI execution, and outputs for the agent workflows.
    """
    def __init__(self):
        self.github_token = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN")
        self.workspace_dir = os.getenv("WORKSPACE_DIR", "./workspace_repos")
        
        # Resolve path to be absolute inside workspace
        self.workspace_dir = os.path.abspath(self.workspace_dir)
        
        if not self.github_token:
            logger.warning("GITHUB_PERSONAL_ACCESS_TOKEN is not set in environment.")

    def parse_github_url(self, repo_url: str) -> Tuple[str, str]:
        """Extracts owner and repository name from various GitHub URL formats."""
        pattern = r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?"
        match = re.search(pattern, repo_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        return match.group(1), match.group(2)

    def _clone_and_setup_repo(self, repo_owner: str, repo_name: str, branch: str) -> str:
        """Clones the repository and checkouts target branch locally."""
        if not self.github_token:
            raise ValueError("Cannot clone repository: GITHUB_PERSONAL_ACCESS_TOKEN is not set.")
            
        os.makedirs(self.workspace_dir, exist_ok=True)
        local_path = os.path.join(self.workspace_dir, f"{repo_owner}_{repo_name}")
        
        # Authenticated URL
        clone_url = f"https://{self.github_token}@github.com/{repo_owner}/{repo_name}.git"
        
        try:
            if os.path.exists(local_path):
                logger.info(f"Directory '{local_path}' exists. Fetching and pulling latest.")
                subprocess.run(["git", "fetch", "origin"], cwd=local_path, check=True, capture_output=True)
                subprocess.run(["git", "checkout", branch], cwd=local_path, check=True, capture_output=True)
                subprocess.run(["git", "pull", "origin", branch], cwd=local_path, check=True, capture_output=True)
            else:
                logger.info(f"Cloning repository into '{local_path}'")
                subprocess.run(["git", "clone", "-b", branch, clone_url, local_path], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err_msg = f"Git operation failed: {e.stderr.decode('utf-8') if e.stderr else str(e)}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)
            
        return local_path

    def _create_target_branch(self, local_path: str, base_branch: str) -> str:
        """Creates and checks out a new branch for the fix."""
        rand_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        target_branch = f"ai-patch-{rand_id}"
        try:
            logger.info(f"Creating local branch '{target_branch}' from '{base_branch}'")
            subprocess.run(["git", "checkout", base_branch], cwd=local_path, check=True, capture_output=True)
            subprocess.run(["git", "checkout", "-b", target_branch], cwd=local_path, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            err_msg = f"Failed to create branch: {e.stderr.decode('utf-8') if e.stderr else str(e)}"
            logger.error(err_msg)
            raise RuntimeError(err_msg)
        return target_branch

    def run_analysis_workflow(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """Runs the Repository Analysis and Security Audit workflow."""
        owner, name = self.parse_github_url(repo_url)
        logger.info(f"Starting Analysis Workflow for {owner}/{name} on branch {branch}")
        
        # Clone repo locally for local read operations
        local_path = self._clone_and_setup_repo(owner, name, branch)
        
        # Establish MCP Client
        mcp_client = create_github_mcp_client(self.github_token)
        
        try:
            # Get tools
            mcp_tools = mcp_client.get_crewai_tools()
            local_tools = [read_local_file]
            
            # Setup factories
            agents_factory = CrewAgentsFactory(mcp_tools=mcp_tools, local_tools=local_tools)
            
            # Instantiate agents required for analysis
            analyzer = agents_factory.create_repository_analyzer()
            auditor = agents_factory.create_security_auditor()
            pm = agents_factory.create_project_manager()
            
            agents_dict = {
                "repository_analyzer": analyzer,
                "security_auditor": auditor,
                "project_manager": pm
            }
            
            tasks_factory = CrewTasksFactory(agents=agents_dict)
            
            # Instantiate analysis tasks
            analysis_task = tasks_factory.create_repo_analysis_task()
            audit_task = tasks_factory.create_security_audit_task()
            report_task = tasks_factory.create_final_report_task()
            
            crew = create_engineering_crew(
                agents=[analyzer, auditor, pm],
                tasks=[analysis_task, audit_task, report_task]
            )
            
            inputs = {
                "repo_owner": owner,
                "repo_name": name,
                "branch": branch,
                "repo_dir": local_path
            }
            
            logger.info("Executing CrewAI flow...")
            result = crew.kickoff(inputs=inputs)
            
            return {
                "status": "success",
                "summary": result.raw,
                "details": {
                    "repository": f"{owner}/{name}",
                    "branch": branch,
                    "local_path": local_path,
                    "analysis": analysis_task.output.raw if analysis_task.output else "",
                    "security_audit": audit_task.output.raw if audit_task.output else ""
                }
            }
            
        finally:
            mcp_client.disconnect()

    def run_fix_workflow(self, repo_url: str, branch: str = "main", issue_description: str = "") -> Dict[str, Any]:
        """Runs the complete autonomous engineering workflow to generate a fix and submit a PR."""
        owner, name = self.parse_github_url(repo_url)
        logger.info(f"Starting Issue Fixing Workflow for {owner}/{name} on branch {branch}")
        
        # Clone repo locally
        local_path = self._clone_and_setup_repo(owner, name, branch)
        
        # Setup branch
        target_branch = self._create_target_branch(local_path, branch)
        
        # Establish MCP Client
        mcp_client = create_github_mcp_client(self.github_token)
        
        try:
            # Retrieve tools
            mcp_tools = mcp_client.get_crewai_tools()
            local_tools = [read_local_file, write_local_file, run_local_tests, git_commit_and_push]
            
            # Instantiate Agent blueprints
            agents_factory = CrewAgentsFactory(mcp_tools=mcp_tools, local_tools=local_tools)
            
            analyzer = agents_factory.create_repository_analyzer()
            auditor = agents_factory.create_security_auditor()
            generator = agents_factory.create_code_generator()
            tester = agents_factory.create_testing_agent()
            pr_agent = agents_factory.create_pr_agent()
            pm = agents_factory.create_project_manager()
            
            agents_dict = {
                "repository_analyzer": analyzer,
                "security_auditor": auditor,
                "code_generator": generator,
                "testing_agent": tester,
                "pr_agent": pr_agent,
                "project_manager": pm
            }
            
            # Instantiate Task configurations
            tasks_factory = CrewTasksFactory(agents=agents_dict)
            
            analysis_task = tasks_factory.create_repo_analysis_task()
            audit_task = tasks_factory.create_security_audit_task()
            codegen_task = tasks_factory.create_code_generation_task()
            test_task = tasks_factory.create_unit_testing_task()
            pr_task = tasks_factory.create_pull_request_task()
            report_task = tasks_factory.create_final_report_task()
            
            # Assemble the complete multi-agent crew
            crew = create_engineering_crew(
                agents=[analyzer, auditor, generator, tester, pr_agent, pm],
                tasks=[analysis_task, audit_task, codegen_task, test_task, pr_task, report_task]
            )
            
            inputs = {
                "repo_owner": owner,
                "repo_name": name,
                "branch": branch,
                "target_branch": target_branch,
                "repo_dir": local_path,
                "issue_description": issue_description
            }
            
            logger.info("Executing CrewAI autonomous engineering team workflow...")
            result = crew.kickoff(inputs=inputs)
            
            return {
                "status": "success",
                "summary": result.raw,
                "details": {
                    "repository": f"{owner}/{name}",
                    "base_branch": branch,
                    "target_branch": target_branch,
                    "local_path": local_path,
                    "analysis": analysis_task.output.raw if analysis_task.output else "",
                    "security_audit": audit_task.output.raw if audit_task.output else "",
                    "code_generation": codegen_task.output.raw if codegen_task.output else "",
                    "tests_generated": test_task.output.raw if test_task.output else "",
                    "pull_request": pr_task.output.raw if pr_task.output else ""
                }
            }
            
        finally:
            mcp_client.disconnect()
