import os
import yaml
import logging
from typing import Dict, Any
from crewai import Task

logger = logging.getLogger(__name__)

class CrewTasksFactory:
    """Factory to load task definitions from YAML and map them to agents."""
    def __init__(self, agents: Dict[str, Any]):
        self.agents = agents
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads task configuration from YAML file."""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "configs",
            "tasks.yaml"
        )
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load tasks config from {config_path}: {e}")
            raise

    def create_repo_analysis_task(self) -> Task:
        cfg = self.config["repo_analysis_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["repository_analyzer"]
        )

    def create_security_audit_task(self) -> Task:
        cfg = self.config["security_audit_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["security_auditor"]
        )

    def create_code_generation_task(self) -> Task:
        cfg = self.config["code_generation_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["code_generator"]
        )

    def create_unit_testing_task(self) -> Task:
        cfg = self.config["unit_testing_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["testing_agent"]
        )

    def create_pull_request_task(self) -> Task:
        cfg = self.config["pull_request_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["pr_agent"]
        )

    def create_final_report_task(self) -> Task:
        cfg = self.config["final_report_task"]
        return Task(
            description=cfg["description"],
            expected_output=cfg["expected_output"],
            agent=self.agents["project_manager"]
        )
