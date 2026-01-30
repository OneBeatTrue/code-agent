"""GitHub API client for GitHub App integration."""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

import httpx

from .github_app.auth import github_app_auth
from .config import settings

logger = logging.getLogger(__name__)


class GitHubAppClient:
    """GitHub API client using GitHub App authentication."""
    
    def __init__(self, installation_id: int):
        self.installation_id = installation_id
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self._client = await github_app_auth.get_authenticated_client(self.installation_id)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
    
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get issue details."""
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request details."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str) -> Dict[str, Any]:
        """Create a new branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/refs"
        
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha
        }
        
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def update_branch(self, owner: str, repo: str, branch_name: str, new_sha: str) -> Dict[str, Any]:
        """Update an existing branch to point to a new commit."""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch_name}"
        
        data = {
            "sha": new_sha,
            "force": True  # Force update even if it's not a fast-forward
        }
        
        response = await self._client.patch(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_default_branch(self, owner: str, repo: str) -> str:
        """Get repository default branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        repo_data = response.json()
        return repo_data["default_branch"]
    
    async def get_branch_sha(self, owner: str, repo: str, branch: str) -> str:
        """Get SHA of a branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        ref_data = response.json()
        return ref_data["object"]["sha"]
    
    async def create_or_update_file(
        self,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str,
        sha: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create or update a file in the repository."""
        import base64
        
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode()).decode()
        
        data = {
            "message": message,
            "content": encoded_content,
            "branch": branch
        }
        
        if sha:
            data["sha"] = sha
        
        response = await self._client.put(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_file_content(
        self,
        owner: str,
        repo: str,
        path: str,
        branch: str = None
    ) -> Optional[Dict[str, Any]]:
        """Get file content from repository."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        params = {}
        if branch:
            params["ref"] = branch
        
        try:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str
    ) -> Dict[str, Any]:
        """Create a pull request."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        
        data = {
            "title": title,
            "body": body,
            "head": head,
            "base": base
        }
        
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: Optional[str] = None,
        body: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a pull request."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        
        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        
        response = await self._client.patch(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def create_issue_comment(
        self,
        owner: str,
        repo: str,
        issue_number: int,
        body: str
    ) -> Dict[str, Any]:
        """Create a comment on an issue or pull request."""
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
        
        data = {"body": body}
        
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def create_pull_request_review(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
        event: str = "COMMENT"  # APPROVE, REQUEST_CHANGES, COMMENT
    ) -> Dict[str, Any]:
        """Create a pull request review."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        
        data = {
            "body": body,
            "event": event
        }
        
        response = await self._client.post(url, json=data)
        response.raise_for_status()
        return response.json()
    
    async def get_pull_request_files(
        self,
        owner: str,
        repo: str,
        pr_number: int
    ) -> List[Dict[str, Any]]:
        """Get files changed in a pull request."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_workflow_runs(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow runs for a repository."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        
        params = {}
        if branch:
            params["branch"] = branch
        if status:
            params["status"] = status
        
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()["workflow_runs"]
    
    async def get_workflow_run(
        self,
        owner: str,
        repo: str,
        run_id: int
    ) -> Dict[str, Any]:
        """Get specific workflow run."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_workflow_run_jobs(
        self,
        owner: str,
        repo: str,
        run_id: int
    ) -> List[Dict[str, Any]]:
        """Get jobs for a workflow run."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()["jobs"]
    
    async def get_commit_status(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> Dict[str, Any]:
        """Get commit status."""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/status"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()
    
    async def get_check_runs(
        self,
        owner: str,
        repo: str,
        sha: str
    ) -> List[Dict[str, Any]]:
        """Get check runs for a commit."""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}/check-runs"
        
        response = await self._client.get(url)
        response.raise_for_status()
        return response.json()["check_runs"]
    
    async def list_repository_files(
        self,
        owner: str,
        repo: str,
        path: str = "",
        branch: str = None
    ) -> List[Dict[str, Any]]:
        """List files in repository directory."""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        params = {}
        if branch:
            params["ref"] = branch
        
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()


async def get_github_client(installation_id: int) -> GitHubAppClient:
    """Get authenticated GitHub client for installation."""
    return GitHubAppClient(installation_id)