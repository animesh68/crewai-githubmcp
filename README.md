# Autonomous AI Engineering Team Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-000000?style=for-the-badge&logo=crewai)](https://crewai.com)
[![Model Context Protocol](https://img.shields.io/badge/MCP-GitHub-181717?style=for-the-badge&logo=github)](https://github.com/modelcontextprotocol)
[![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)

An enterprise-grade autonomous software engineering platform that orchestrates a multi-agent AI team using **CrewAI** and connects directly to codebases and GitHub services using the **Model Context Protocol (MCP)**. It clones target repositories, performs security audits, generates code updates, writes and runs unit tests, pushes branches, and opens pull requests autonomously.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User["User / API Client"] -->|HTTPS POST| FastAPI["FastAPI Server (api/server.py)"]
    FastAPI -->|Enqueue Async Task| BackgroundWorker["FastAPI Background Tasks"]
    BackgroundWorker -->|Initialize| Orchestrator["Agentic Workflow Orchestrator"]
    Orchestrator -->|Clone / Setup Repo| Sandbox["Sandbox Environment (workspace_repos/)"]
    Orchestrator -->|Start Session| MCPClient["MCP Client Manager (Stdio)"]
    MCPClient -->|Spawn Subprocess| GithubMCP["GitHub MCP Server (npx)"]
    
    subgraph Multi-Agent Crew (CrewAI)
        direction TB
        Analyzer["Repository Analyzer"]
        Auditor["Security Auditor"]
        Generator["Code Generator"]
        Tester["Testing Specialist"]
        PRAgent["PR Coordinator"]
        PM["AI Project Manager"]
    end
    
    Orchestrator -->|Assemble Crew| PM
    PM --> Analyzer
    Analyzer --> Auditor
    Auditor --> Generator
    Generator --> Tester
    Tester --> PRAgent
    
    Analyzer -.->|Read| Sandbox
    Auditor -.->|Read / Audit| Sandbox
    Generator -.->|Write Fixes| Sandbox
    Tester -.->|Write & Run Tests| Sandbox
    PRAgent -.->|Git Commit & Push| Sandbox
    PRAgent -.->|Open PR| GithubMCP
    GithubMCP -->|GitHub REST API| GithubAPI["GitHub.com REST API"]
```

---

## 📂 Project Structure

*   [`api/server.py`](file:///c:/Users/Animesh/Desktop/crewai/api/server.py): FastAPI application defining API endpoints, managing routing, and running async background processes.
*   [`workflows/orchestrator.py`](file:///c:/Users/Animesh/Desktop/crewai/workflows/orchestrator.py): The main lifecycle coordinator handling git clones, sandbox setups, MCP stdio loops, and CrewAI execution.
*   [`crew.py`](file:///c:/Users/Animesh/Desktop/crewai/crew.py): Configures the execution engine with ChromaDB memory persistence and sequential flow semantics.
*   [`agents/crew_agents.py`](file:///c:/Users/Animesh/Desktop/crewai/agents/crew_agents.py): Dynamic agent assembly factory mapping model providers (Gemini/OpenAI) and custom MCP tools.
*   [`tasks/crew_tasks.py`](file:///c:/Users/Animesh/Desktop/crewai/tasks/crew_tasks.py): Task mapping factory translating YAML declarations into CrewAI task execution blocks.
*   [`configs/`](file:///c:/Users/Animesh/Desktop/crewai/configs):
    *   [`agents.yaml`](file:///c:/Users/Animesh/Desktop/crewai/configs/agents.yaml): Formulated goals, roles, and backstories for the 6 agent personas.
    *   [`tasks.yaml`](file:///c:/Users/Animesh/Desktop/crewai/configs/tasks.yaml): Execution blueprints and validation thresholds for code tasks.
*   [`tools/`](file:///c:/Users/Animesh/Desktop/crewai/tools):
    *   [`mcp_client.py`](file:///c:/Users/Animesh/Desktop/crewai/tools/mcp_client.py): Multi-threaded event loop manager for stdio MCP connections, featuring dynamic JSON-schema-to-Pydantic parameter translation.
    *   [`custom_tools.py`](file:///c:/Users/Animesh/Desktop/crewai/tools/custom_tools.py): Local tools for secure path read/writes, git push controls, and constrained sandbox test execution.

---

## 🕵️‍♂️ Agent Personas & Workflow Map

| Agent | Core Objective | Tools Utilized |
| :--- | :--- | :--- |
| **Repository Analyzer** | Detect frameworks, map architectural layouts, and understand dependency setups. | `read_local_file`, `get_file_contents`, `search_code`, `get_repo` |
| **Security Auditor** | Locate hardcoded secrets, dangerous injection points, and vulnerable packages. | `read_local_file`, `get_file_contents`, `search_code` |
| **Code Generator** | Implement code modifications, refactor files, and follow existing codebase formatting. | `read_local_file`, `write_local_file`, `run_local_tests`, `create_or_update_file` |
| **Testing Specialist** | Generate unit and integration test coverage for modifications. Supports Pytest, unittest, etc. | `read_local_file`, `write_local_file`, `run_local_tests` |
| **PR Coordinator** | Commit code changes, push to origin, and open GitHub PRs with thorough changelogs. | `git_commit_and_push`, `create_branch`, `create_pull_request` |
| **AI Project Manager** | Review agent logs, compile output summaries, and structure execution reports. | `get_issue`, `list_issues`, `add_issue_comment`, `get_pull_request` |

---

## 🛠️ Getting Started

### Prerequisites
*   **Python:** `3.12+`
*   **Node.js:** `v18+` and `npm` (required to dynamically launch the GitHub MCP server via `npx`)
*   **Git:** Installed and available on your system path.

---

### Method 1: Local Installation

1.  **Configure GitHub MCP Server globally:**
    ```bash
    npm install -g @modelcontextprotocol/server-github
    ```

2.  **Clone this repository and create a virtual environment:**
    ```bash
    git clone https://github.com/your-org/crewai-mcp-platform.git
    cd crewai-mcp-platform
    python -m venv venv
    ```
    *   **Activate Environment:**
        *   *Windows (PowerShell):* `.\venv\Scripts\Activate.ps1`
        *   *Linux/macOS:* `source venv/bin/activate`

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Setup Environment Variables:**
    Create a `.env` file from the template:
    ```bash
    cp .env.example .env
    ```
    Configure the following values inside your `.env` file:
    ```ini
    MODEL_PROVIDER=gemini # Or "openai"
    MODEL_NAME=gemini-1.5-pro # Or "gpt-4o"
    GEMINI_API_KEY=your_gemini_api_key_here
    GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token_here
    WORKSPACE_DIR=./workspace_repos
    ```

5.  **Run the API Server:**
    ```bash
    python app.py
    ```
    Access the interactive Swagger documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

---

### Method 2: Docker Compose (Recommended for Production/Sandbox isolation)

Using Docker Compose completely sandboxes the execution environment, preventing the agent from modifying files or running commands outside of the Docker container.

```bash
docker-compose up --build
```

The container automatically installs Node.js, Python, Git, and routes API requests to port `8000`.

---

## 🔌 API Endpoints & Request Payloads

### 1. Health check
*   **Endpoint:** `GET /api/health`
*   **Response:**
    ```json
    {
      "status": "healthy",
      "service": "CrewAI-MCP-Workflow-Platform"
    }
    ```

### 2. Run Repository Analysis
*   **Endpoint:** `POST /api/workflows/analyze`
*   **Request Payload:**
    ```json
    {
      "repo_url": "https://github.com/octocat/Hello-World.git",
      "branch": "master"
    }
    ```
*   **Response:**
    ```json
    {
      "task_id": "b3e0c0f8-c2b2-4d20-b08e-8a9d1872df0d",
      "status": "pending",
      "message": "Repository analysis has been queued in the background."
    }
    ```

### 3. Run Autonomous Issue/Feature Fix
*   **Endpoint:** `POST /api/workflows/fix-issue`
*   **Request Payload:**
    ```json
    {
      "repo_url": "https://github.com/my-profile/sample-calculator.git",
      "branch": "main",
      "issue_description": "Implement a divide function in math_ops.py. Catch ZeroDivisionError, log a warning, and return 0."
    }
    ```
*   **Response:**
    ```json
    {
      "task_id": "f8a02c91-9de2-4c28-9411-dc45688abdc5",
      "status": "pending",
      "message": "Autonomous bug fix/feature workflow has been queued in the background."
    }
    ```

### 4. Fetch Task Status and Reports
*   **Endpoint:** `GET /api/workflows/status/{task_id}`
*   **Response (Complete):**
    ```json
    {
      "status": "completed",
      "result": {
        "status": "success",
        "summary": "### Executive Summary...",
        "details": {
          "repository": "my-profile/sample-calculator",
          "base_branch": "main",
          "target_branch": "ai-patch-8aefd2",
          "analysis": "### Structure Analysis...",
          "security_audit": "No issues detected...",
          "code_generation": "Modified math_ops.py...",
          "tests_generated": "Created tests/test_math_ops.py...",
          "pull_request": "Pull Request opened at https://github.com/..."
        }
      },
      "error": null
    }
    ```

---

## 🔒 Security & Sandboxing (Production Best Practices)

Running LLM-generated code and test commands locally carries security risks. When deploying this platform in a production setup, enforce the following guidelines:

1.  **Isolated Execution (VPC/Containers):** Always run the platform inside a containerized sandbox environment (like Docker or AWS ECS). Set resource memory/CPU limits to prevent denial-of-service (DoS) from rogue loops.
2.  **Constrained Test Commands:** The tool [`run_local_tests`](file:///c:/Users/Animesh/Desktop/crewai/tools/custom_tools.py#L69) restricts test execution to specific binaries (`pytest`, `npm test`, `jest`, etc.). Do not relax this constraint to run arbitrary bash scripts.
3.  **Scoped GitHub PATs:** Use a GitHub fine-grained Personal Access Token (PAT) restricted strictly to the repositories you intend to modify. Grant only `Contents: write`, `Pull Requests: write`, and `Issues: write` permissions.
4.  **Stateless Workspace Cleanup:** Regularly clean up or prune directory clones inside `workspace_repos/` using automated cron jobs to prevent disk fills.

---

## ⚙️ Transitioning to Production Architecture

For an enterprise deployment, make the following modifications:

*   **Task Queue:** Replace the in-memory FastAPI `BackgroundTasks` queue with a robust distributed queue system like **Celery**, **RabbitMQ**, or **Redis Queue (RQ)**.
*   **Persistent Database:** Replace the in-memory dictionary `tasks_db` in [`api/server.py`](file:///c:/Users/Animesh/Desktop/crewai/api/server.py) with a database (e.g., PostgreSQL) to persist audit runs and reports.
*   **Vector DB Remote Host:** Move the internal ChromaDB memory to an external managed instance (like Pinecone, Qdrant, or a standalone Chroma cluster) to prevent database locking issues across container replicas.

---

## 🧪 Development & Testing

Run unit tests locally using pytest to ensure the endpoints, tools, factories, and parsers function correctly:
```bash
pytest tests/
```
