import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from workflows.orchestrator import AgenticWorkflowOrchestrator

# Setup Logging
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Autonomous AI Engineering Team Platform",
    description="An agentic workflow platform built with CrewAI and GitHub MCP servers.",
    version="1.0.0"
)

# Enable CORS for dashboard integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory database to keep track of asynchronous agent tasks
# In a production setup, this would be replaced with Redis/SQLAlchemy
tasks_db: Dict[str, Dict[str, Any]] = {}

# Pydantic schemas for requests/responses
class AnalysisRequest(BaseModel):
    repo_url: str = Field(..., description="The HTTPS or SSH URL of the GitHub repository.")
    branch: str = Field("main", description="The branch name to analyze.")

class FixRequest(BaseModel):
    repo_url: str = Field(..., description="The HTTPS or SSH URL of the GitHub repository.")
    branch: str = Field("main", description="The base branch to branch off of and merge into.")
    issue_description: str = Field(..., description="Detailed description of the issue or feature to implement.")

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# Background worker functions
def execute_analysis_workflow(task_id: str, repo_url: str, branch: str):
    logger.info(f"Background task {task_id}: Starting repository analysis...")
    tasks_db[task_id]["status"] = "running"
    
    try:
        orchestrator = AgenticWorkflowOrchestrator()
        result = orchestrator.run_analysis_workflow(repo_url=repo_url, branch=branch)
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["result"] = result
        logger.info(f"Background task {task_id}: Repository analysis completed successfully.")
    except Exception as e:
        error_msg = str(e)
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = error_msg
        logger.error(f"Background task {task_id}: Repository analysis failed: {error_msg}", exc_info=True)

def execute_fix_workflow(task_id: str, repo_url: str, branch: str, issue_description: str):
    logger.info(f"Background task {task_id}: Starting issue fixing workflow...")
    tasks_db[task_id]["status"] = "running"
    
    try:
        orchestrator = AgenticWorkflowOrchestrator()
        result = orchestrator.run_fix_workflow(
            repo_url=repo_url, 
            branch=branch, 
            issue_description=issue_description
        )
        tasks_db[task_id]["status"] = "completed"
        tasks_db[task_id]["result"] = result
        logger.info(f"Background task {task_id}: Issue fixing workflow completed successfully.")
    except Exception as e:
        error_msg = str(e)
        tasks_db[task_id]["status"] = "failed"
        tasks_db[task_id]["error"] = error_msg
        logger.error(f"Background task {task_id}: Issue fixing workflow failed: {error_msg}", exc_info=True)


# Routes
@app.get("/api/health", status_code=status.HTTP_200_OK)
def health_check():
    """Simple API health check endpoint."""
    return {"status": "healthy", "service": "CrewAI-MCP-Workflow-Platform"}

@app.post("/api/workflows/analyze", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
def analyze_repository(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Triggers an asynchronous repository architecture scan and security audit.
    Returns a task ID immediately to poll for results.
    """
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {
        "status": "pending",
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(
        execute_analysis_workflow,
        task_id=task_id,
        repo_url=request.repo_url,
        branch=request.branch
    )
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="Repository analysis has been queued in the background."
    )

@app.post("/api/workflows/fix-issue", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED)
def fix_issue(request: FixRequest, background_tasks: BackgroundTasks):
    """
    Triggers the full multi-agent loop to analyze the repo, audit security,
    generate a fix, write tests, push to a new branch, and open a GitHub PR.
    Returns a task ID immediately to poll for results.
    """
    task_id = str(uuid.uuid4())
    tasks_db[task_id] = {
        "status": "pending",
        "result": None,
        "error": None
    }
    
    background_tasks.add_task(
        execute_fix_workflow,
        task_id=task_id,
        repo_url=request.repo_url,
        branch=request.branch,
        issue_description=request.issue_description
    )
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        message="Autonomous bug fix/feature workflow has been queued in the background."
    )

@app.get("/api/workflows/status/{task_id}", response_model=Dict[str, Any])
def get_task_status(task_id: str):
    """Retrieves the status, results, or error logs of a queued workflow task."""
    if task_id not in tasks_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Task with ID {task_id} not found."
        )
    return tasks_db[task_id]

@app.get("/api/workflows/reports", response_model=List[Dict[str, Any]])
def list_completed_reports():
    """Lists summary info for all completed task runs in memory."""
    completed_tasks = []
    for tid, info in tasks_db.items():
        if info["status"] == "completed" and info["result"]:
            details = info["result"].get("details", {})
            completed_tasks.append({
                "task_id": tid,
                "repository": details.get("repository", "Unknown"),
                "branch": details.get("branch") or details.get("base_branch", "Unknown"),
                "type": "Fix Issue" if "code_generation" in details else "Analysis",
                "status": "completed"
            })
    return completed_tasks
