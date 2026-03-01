"""
Module: repo_scanner
Description: Handles the secure, in-memory retrieval and filtering of GitHub repository contents.
This module specifically avoids utilizing 'git clone' to prevent local directory traversal
vulnerabilities (e.g., CVE-2024-56074) associated with malicious symlinks.
"""

import logging
import requests
import pathspec
from urllib.parse import urlparse
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class RepoScanner:
    """
    Scans and filters public GitHub repositories using the GitHub REST API.
    
    This class relies on in-memory traversal (via the Git Trees API) rather than 
    executing local 'git clone' commands. This fundamentally mitigates local 
    directory traversal vulnerabilities and protects the host server's file system.
    """
    
    def __init__(self):
        self.base_api_url = "https://api.github.com/repos"
        self.raw_base_url = "https://raw.githubusercontent.com"
        
        # Using a session object persists TCP connections, significantly speeding up 
        # the dozens of HTTP requests we'll make during the context assembly phase.
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GitHub-To-LLM-API-Student-Project",
            "Accept": "application/vnd.github.v3+json"
        })

        # Aggressive exclusion list to protect the LLM's context window.
        # Passing compressed archives (.zip) or databases (.sqlite) will 
        # instantly max out token limits with unreadable binary garbage.
        self.excluded_extensions = (
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.svg',
            '.zip', '.whl', '.tar.gz', '.tar', '.db', '.sqlite', '.csv',
            '.parquet', '.bin', '.wasm', '.pyc', '.pyd', '.exe'
        )
        
        # Hard-blocking massive, machine-generated lock files which provide 
        # zero architectural signal to the LLM.
        self.excluded_files = {
            'package-lock.json', 'yarn.lock', 'poetry.lock', 'Pipfile.lock'
        }

    def _extract_owner_repo(self, github_url: str) -> tuple[str, str]:
        """
        Robustly extracts the owner and repository name from a GitHub URL.
        Using urllib.parse safely handles deep directory links (e.g., /tree/main/src)
        and prevents the index-out-of-bounds errors common with string splitting.
        """
        parsed = urlparse(github_url)
        path_parts = parsed.path.strip("/").split("/")
        
        if len(path_parts) >= 2:
            owner, repo = path_parts[0], path_parts[1]
            # Strip the .git suffix if the user pasted an SSH-style clone link
            if repo.endswith(".git"):
                repo = repo[:-4]
            return owner, repo
            
        raise ValueError(f"Invalid GitHub URL structure: {github_url}")

    def get_repo_tree(self, github_url: str) -> List[Dict]:
        """
        Fetches the complete file tree of the repository's default branch.
        """
        try:
            owner, repo = self._extract_owner_repo(github_url)
            
            # Fetching via 'HEAD' automatically resolves the repo's default branch 
            # (whether main, master, dev, etc.) without us having to guess or hardcode it.
            api_url = f"{self.base_api_url}/{owner}/{repo}/git/trees/HEAD?recursive=1"
            
            logger.info(f"Fetching repository tree from: {api_url}")
            response = self.session.get(api_url, timeout=10)
            
            # Automatically raises an exception for 4xx/5xx responses (e.g., 404 Not Found)
            response.raise_for_status()
            
            # We parse JSON *inside* the try block. If GitHub hits us with a temporary 
            # 403 rate limit, they return an HTML page. This catches the resulting 
            # JSONDecodeError gracefully instead of crashing the server.
            return response.json().get("tree", [])
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching repository tree: {e}")
            return []
        except ValueError as e:
            logger.error(f"Invalid JSON response from GitHub (possible rate limit): {e}")
            return []

    def get_raw_content(self, download_url: str) -> str:
            """
            Fetches the raw text content of a specific file using its direct download URL.
            """
            try:
                response = self.session.get(download_url, timeout=10)
                response.raise_for_status()
                return response.text
            except requests.exceptions.RequestException as e:
                logger.warning(f"Network error fetching file {download_url}: {e}")
                return ""

    def fetch_gitignore(self, owner: str, repo: str) -> Optional[pathspec.PathSpec]:
        """
        Fetches the repository's native .gitignore file to dynamically filter 
        out junk directories like node_modules/ or __pycache__/.
        """
        # Targeting HEAD ensures we get the exact gitignore for the default branch
        url = f"{self.raw_base_url}/{owner}/{repo}/HEAD/.gitignore"
        try:
            res = self.session.get(url, timeout=5)
            res.raise_for_status()
            
            lines = res.text.splitlines()
            lines.append(".git/") # Always ignore the .git directory implicitly
            logger.info(f"Successfully loaded .gitignore with {len(lines)} rules.")
            
            return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, lines)
            
        except requests.exceptions.RequestException as e:
            logger.warning(f"No .gitignore found or network error: {e}")
            # Fallback: manually ignore .git even if the fetch fails
            return pathspec.PathSpec.from_lines(pathspec.patterns.GitWildMatchPattern, [".git/"])

    def filter_files(self, tree: List[Dict], github_url: str) -> List[Dict]:
        """
        Applies strict filtering and prioritization to the repository tree.
        Returns a list of dictionaries containing paths and direct download URLs.
        """
        owner, repo = self._extract_owner_repo(github_url)
        spec = self.fetch_gitignore(owner, repo)
        
        filtered_files = []
        
        for item in tree:
            if item.get('type') != 'blob':
                continue
                
            path = item.get('path', '')
            filename = path.split('/')[-1]
            
            # 1. Apply native .gitignore rules
            if spec and spec.match_file(path):
                continue
                
            # 2. Hard-block known binary/compressed extensions
            if path.endswith(self.excluded_extensions):
                continue
                
            # 3. Hard-block specific low-signal files
            if filename in self.excluded_files or any(ignored in path for ignored in self.excluded_files):
                continue
                
            # Store the exact download URL so the prompt_builder doesn't have to guess it later
            filtered_files.append({
                "path": path,
                "download_url": f"{self.raw_base_url}/{owner}/{repo}/HEAD/{path}"
            })
            
        # Priority Sorting: 
        # LLMs perform significantly better when high-level context (READMEs, architecture docs) 
        # is presented at the beginning of the prompt before raw source code.
        def get_priority(file_item: Dict) -> int:
            path_lower = file_item["path"].lower()
            if path_lower.endswith("readme.md"):
                return 0  # Highest priority
            if path_lower.endswith(("dockerfile", "docker-compose.yml", "requirements.txt", "package.json", "pyproject.toml")):
                return 1  # Configuration / Dependencies
            return 2      # Standard Source Code
            
        # Sort files in-place based on priority
        filtered_files.sort(key=get_priority)
        
        return filtered_files