"""
GitHub Writer — Lets Ultron edit its own source code directly on GitHub.

When deployed in the cloud (Railway, etc), there's no local git repo.
This module uses the GitHub API to:
  - Read files from the repo
  - Create/update files with new content  
  - Commit changes with messages
  - All without needing a local git clone

Required env var: GITHUB_TOKEN (personal access token with 'repo' scope)
Get one at: https://github.com/settings/tokens → Generate new token → check 'repo'
"""

import os
import json
import base64
import urllib.request
import urllib.error
from typing import Optional, Dict, Any


GITHUB_API = "https://api.github.com"
REPO_OWNER = "Eman59"
REPO_NAME = "ultron"
BRANCH = "main"


def get_token() -> Optional[str]:
    return os.environ.get("GITHUB_TOKEN", "")


def read_file(file_path: str) -> Optional[str]:
    """Read a file from the GitHub repo."""
    if not file_path:
        return None

    token = get_token()
    if not token:
        return None

    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}?ref={BRANCH}"
    
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode())
            if "content" not in data:
                return None
            content = base64.b64decode(data["content"]).decode("utf-8")
            return content
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


def write_file(file_path: str, content: str, commit_message: str) -> Dict[str, Any]:
    """
    Write/update a file on GitHub (creates a commit).
    
    Returns: {"success": bool, "commit_url": str, "error": str}
    """
    if not file_path or not content or not commit_message:
        return {"success": False, "error": "Invalid input: file_path, content, and commit_message are required"}

    token = get_token()
    if not token:
        return {"success": False, "error": "No GITHUB_TOKEN set. Get one at github.com/settings/tokens"}

    # First, get the current file's SHA (needed for updates)
    sha = _get_file_sha(file_path, token)

    # Encode content to base64
    content_b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")

    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    
    payload = {
        "message": commit_message,
        "content": content_b64,
        "branch": BRANCH,
    }
    
    if sha:
        payload["sha"] = sha  # Required for updating existing files

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="PUT", headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 201:
                return {"success": False, "error": f"Failed to create commit (status {resp.status})"}
            result = json.loads(resp.read().decode())
            return {
                "success": True,
                "commit_url": result.get("commit", {}).get("html_url", ""),
                "sha": result.get("content", {}).get("sha", ""),
            }
    except urllib.error.HTTPError as e:
        return {"success": False, "error": f"Failed to create commit (status {e.code})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_file_sha(file_path: str, token: str) -> Optional[str]:
    url = f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}?ref={BRANCH}"
    
    try:
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode())
            if "sha" not in data:
                return None
            return data["sha"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None