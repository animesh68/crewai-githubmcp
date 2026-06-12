import logging
from typing import List, Any
from crewai import Crew, Process

logger = logging.getLogger(__name__)

def create_engineering_crew(agents: List[Any], tasks: List[Any]) -> Crew:
    """
    Assembles and returns a CrewAI Crew with the given agents and tasks,
    enabling sequential execution process and default memory.
    """
    logger.info(f"Assembling CrewAI Crew with {len(agents)} agents and {len(tasks)} tasks.")
    return Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        memory=True,  # Enables ChromaDB memory persistence
        verbose=True
    )
