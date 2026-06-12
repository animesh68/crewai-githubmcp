import os
import subprocess
import logging
from typing import Optional
from crewai.tools import tool

logger = logging.getLogger(__name__)

def get_workspace_root(repo_dir: str) -> str:
    """Helper to get clean absolute path of local cloned repository."""
    return os.path.abspath(repo_dir)

def is_safe_path(base_dir: str, target_path: str) -> bool:
    """Checks if a target path is inside the allowed base directory."""
    abs_base = os.path.abspath(base_dir)
    abs_target = os.path.abspath(os.path.join(abs_base, target_path))
    return abs_target.startswith(abs_base)

@tool("read_local_file")
def read_local_file(repo_dir: str, file_path: str) -> str:
    """
    Reads the content of a file from the locally cloned repository.
    
    Args:
        repo_dir (str): The absolute or relative path to the cloned repository root.
        file_path (str): The relative path of the file to read within the repository.
    """
    base_dir = get_workspace_root(repo_dir)
    if not is_safe_path(base_dir, file_path):
        return f"Error: Access denied. File path '{file_path}' is outside the repository directory."
    
    full_path = os.path.join(base_dir, file_path)
    if not os.path.exists(full_path):
        return f"Error: File '{file_path}' does not exist."
        
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read local file {full_path}: {e}")
        return f"Error: Could not read file: {e}"

@tool("write_local_file")
def write_local_file(repo_dir: str, file_path: str, content: str) -> str:
    """
    Writes or overwrites content to a file in the locally cloned repository.
    
    Args:
        repo_dir (str): The absolute or relative path to the cloned repository root.
        file_path (str): The relative path of the file to write within the repository.
        content (str): The text content to write.
    """
    base_dir = get_workspace_root(repo_dir)
    if not is_safe_path(base_dir, file_path):
        return f"Error: Access denied. File path '{file_path}' is outside the repository directory."
    
    full_path = os.path.join(base_dir, file_path)
    # Create parent directories if they don't exist
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{file_path}' written successfully."
    except Exception as e:
        logger.error(f"Failed to write local file {full_path}: {e}")
        return f"Error: Could not write file: {e}"

@tool("run_local_tests")
def run_local_tests(repo_dir: str, test_command: str) -> str:
    """
    Runs a test command (e.g. 'pytest', 'pytest tests/test_math.py', 'npm test')
    inside the cloned repository directory.
    
    Args:
        repo_dir (str): The absolute or relative path to the cloned repository root.
        test_command (str): The exact test shell command to run.
    """
    base_dir = get_workspace_root(repo_dir)
    if not os.path.exists(base_dir):
        return f"Error: Cloned repository directory '{repo_dir}' does not exist."
    
    # Restrict execution commands to common testing frameworks for safety
    allowed_keywords = ["pytest", "python -m unittest", "npm test", "npm run test", "jest", "tox"]
    is_allowed = any(keyword in test_command for keyword in allowed_keywords)
    if not is_allowed:
        return f"Error: Command '{test_command}' is not permitted. Only standard test commands (pytest, npm test, etc.) are allowed."

    try:
        logger.info(f"Running test command '{test_command}' inside directory '{base_dir}'")
        # Run command with a timeout to prevent infinite loops (e.g., if tests hang)
        result = subprocess.run(
            test_command,
            cwd=base_dir,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        output = []
        if result.stdout:
            output.append("=== STDOUT ===")
            output.append(result.stdout)
        if result.stderr:
            output.append("=== STDERR ===")
            output.append(result.stderr)
            
        output_str = "\n".join(output)
        status = "PASSED" if result.returncode == 0 else "FAILED"
        return f"Tests {status} (Exit Code: {result.returncode})\n\n{output_str}"
        
    except subprocess.TimeoutExpired:
        logger.warning(f"Test command '{test_command}' timed out after 60s.")
        return "Error: Test command execution timed out after 60 seconds."
    except Exception as e:
        logger.error(f"Failed to run test command '{test_command}': {e}")
        return f"Error: Could not execute test command: {e}"

@tool("git_commit_and_push")
def git_commit_and_push(repo_dir: str, branch_name: str, commit_message: str) -> str:
    """
    Stages all local changes, commits them with a message, and pushes the branch to origin.
    
    Args:
        repo_dir (str): The absolute or relative path to the cloned repository root.
        branch_name (str): The name of the target branch to push.
        commit_message (str): The commit message describing the changes.
    """
    base_dir = get_workspace_root(repo_dir)
    if not os.path.exists(base_dir):
        return f"Error: Cloned repository directory '{repo_dir}' does not exist."
        
    try:
        logger.info(f"Staging, committing and pushing changes in '{base_dir}' to branch '{branch_name}'")
        
        # Configure local git config if not set
        subprocess.run(["git", "config", "user.name", "AI Engineering Assistant"], cwd=base_dir, check=True)
        subprocess.run(["git", "config", "user.email", "ai-assistant@users.noreply.github.com"], cwd=base_dir, check=True)
        
        # Check current status
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=base_dir, capture_output=True, text=True, check=True)
        if not status_res.stdout.strip():
            return "Warning: No changes found to commit."
            
        # Add, commit, and push
        subprocess.run(["git", "add", "."], cwd=base_dir, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=base_dir, check=True)
        
        # Push to origin
        push_res = subprocess.run(["git", "push", "origin", branch_name], cwd=base_dir, capture_output=True, text=True)
        if push_res.returncode != 0:
            # Try with force if required, or return error
            return f"Error: Git push failed.\nSTDOUT: {push_res.stdout}\nSTDERR: {push_res.stderr}"
            
        return f"Success: Committed and pushed changes to branch '{branch_name}' successfully."
        
    except Exception as e:
        logger.error(f"Failed to git commit and push in '{base_dir}': {e}")
        return f"Error: Git commit/push failed: {e}"
