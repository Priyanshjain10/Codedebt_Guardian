"""
GitHub Tool - Fetches repository contents using GitHub REST API.
Uses ZIP archive download for efficient bulk ingestion (2 API calls total).
Handles authentication, rate limiting, and content decoding.
"""

import io
import os
import re
import logging
import tempfile
import time
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from pathlib import PurePosixPath, Path

import requests

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
MAX_FILE_SIZE_BYTES = 100_000  # 100KB max per file


class GitHubTool:
    """
    Tool for interacting with the GitHub REST API.

    Uses ZIP archive download to fetch all repository files in a single
    API call, eliminating per-file content requests and drastically
    reducing rate limit consumption.

    Handles:
    - Repository metadata fetching (1 API call)
    - Bulk file retrieval via zipball (1 API call)
    - Rate limit management
    - Error handling with retries
    """

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeDebt-Guardian/1.0",
        })
        if self.token:
            self.session.headers["Authorization"] = f"token {self.token}"
        else:
            logger.warning("No GITHUB_TOKEN set — API rate limits will be very low (60 req/hour)")

    def parse_repo_url(self, repo_url: str) -> tuple[str, str]:
        """Extract owner and repo name from a GitHub URL."""
        # Handle formats: github.com/owner/repo, https://github.com/owner/repo
        repo_url = repo_url.rstrip("/")
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?$",
            r"^([^/]+)/([^/]+)$",  # owner/repo shorthand
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                return match.group(1), match.group(2)
        raise ValueError(f"Cannot parse GitHub URL: {repo_url}")

    def fetch_repo_contents(self, repo_url: str, branch: str = "main") -> Dict[str, Any]:
        """
        Fetch repository metadata and file contents via ZIP archive.

        Downloads the entire repository as a ZIP archive in a single API call,
        then extracts and filters files. This reduces GitHub API usage
        from N+2 calls (metadata + tree + N file fetches) to just 2 calls
        (metadata + zipball).

        Args:
            repo_url: Full GitHub repository URL
            branch: Branch to analyze

        Returns:
            Dict with repo_metadata and an iterator of files
        """
        owner, repo = self.parse_repo_url(repo_url)

        # Fetch repo metadata (1 API call)
        repo_metadata = self._fetch_repo_metadata(owner, repo)

        # Download and extract ZIP archive to disk (1 API call)
        try:
            file_iterator, temp_dir = self._fetch_zipball(owner, repo, branch)
        except Exception:
            # Fall back to default branch if specified branch fails
            default_branch = repo_metadata.get("default_branch", "main")
            if default_branch != branch:
                logger.info(f"Branch '{branch}' not found, using '{default_branch}'")
                file_iterator, temp_dir = self._fetch_zipball(owner, repo, default_branch)
            else:
                raise

        logger.info(f"Fetched files from {owner}/{repo}")

        return {
            "repo_metadata": repo_metadata,
            "files": file_iterator,  # This is now an iterator
            "owner": owner,
            "repo": repo,
            "_temp_dir": temp_dir,
        }

    def _fetch_repo_metadata(self, owner: str, repo: str) -> Dict:
        """Fetch basic repository metadata."""
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}"
        response = self._get(url)
        data = response.json()

        return {
            "name": data.get("name"),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "language": data.get("language"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "open_issues": data.get("open_issues_count", 0),
            "size_kb": data.get("size", 0),
            "default_branch": data.get("default_branch", "main"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "topics": data.get("topics", []),
            "has_wiki": data.get("has_wiki", False),
            "license": data.get("license", {}).get("name") if data.get("license") else None,
        }

    # File extensions considered "source code" — prioritized over config/docs
    _SOURCE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx"}

    def _fetch_zipball(
        self, owner: str, repo: str, branch: str
    ):
        """
        Download the repository as a ZIP archive and extract to a secure
        temporary directory on disk.

        DISK-BUFFERED STREAMING ARCHITECTURE:
        Instead of loading all file contents into RAM, this returns a
        generator that yields dict with file info and local_path.

        Returns:
            Tuple of (file_generator, temp_dir_handle).
            The temp_dir_handle MUST be kept alive until analysis is done.
        """
        url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/zipball/{branch}"
        logger.info(f"Downloading ZIP archive for {owner}/{repo}@{branch}")

        response = self._get(url, stream=True)

        # Create a secure temporary directory for extraction
        temp_dir = tempfile.TemporaryDirectory(prefix="codedebt_")
        temp_path = Path(temp_dir.name)

        # Extract ZIP to disk
        zip_bytes = io.BytesIO(response.content)
        all_files: List[Dict] = []

        def _file_generator():
            # For iteration efficiency without storing everything in RAM
            with zipfile.ZipFile(zip_bytes, "r") as zf:
                for entry in zf.infolist():
                    # Skip directories
                    if entry.is_dir():
                        continue

                    parts = PurePosixPath(entry.filename).parts
                    if len(parts) <= 1:
                        continue  # top-level file in the prefix dir itself
                    relative_path = str(PurePosixPath(*parts[1:]))

                    file_info = {
                        "path": relative_path,
                        "size": entry.file_size,
                    }

                    if not self._should_analyze(file_info):
                        continue

                    # Extract file to disk
                    try:
                        dest = temp_path / relative_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest, "wb") as out_f:
                            out_f.write(zf.read(entry.filename))
                    except Exception as e:
                        logger.debug(f"Could not extract {relative_path}: {e}")
                        continue

                    yield {
                        "name": relative_path,
                        "local_path": str(dest),
                        "size": entry.file_size,
                    }

        return _file_generator(), temp_dir

    @staticmethod
    def read_file_content(file_info: Dict, max_bytes: int = MAX_FILE_SIZE_BYTES) -> str:
        """
        Lazily read file content from disk (local_path) or fall back to
        in-memory content. This is the single point of file I/O for all
        downstream agents.

        Returns file content as a string, truncated to max_bytes.
        Returns empty string on any read failure.
        """
        # Prefer disk-buffered path
        local_path = file_info.get("local_path")
        if local_path:
            try:
                with open(local_path, "r", encoding="utf-8", errors="replace") as f:
                    return f.read(max_bytes)
            except Exception:
                return ""

        # Backward compat: return in-memory content if available
        return file_info.get("content", "")[:max_bytes]

    def _should_analyze(self, file_info: Dict) -> bool:
        """Determine if a file should be included in analysis."""
        path = file_info.get("path", "")
        size = file_info.get("size", 0)

        # Skip binary, large, and irrelevant files
        if size > MAX_FILE_SIZE_BYTES:
            return False

        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".eggs", "target", "vendor"}
        for skip in skip_dirs:
            if f"/{skip}/" in f"/{path}/" or path.startswith(f"{skip}/"):
                return False

        # Include Python files, JS files, config files, and docs
        include_extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".txt", ".md", ".toml", ".yaml", ".yml", ".cfg", ".ini", ".json"}
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
        return ext in include_extensions

    def _get(self, url: str, retries: int = 3, stream: bool = False) -> requests.Response:
        """Make a GET request with rate limit handling and retries."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30, stream=stream)

                # Handle rate limiting
                if response.status_code == 403 and "rate limit" in response.text.lower():
                    reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                    wait = max(0, reset_time - int(time.time())) + 1
                    logger.warning(f"Rate limited. Waiting {wait}s...")
                    time.sleep(min(wait, 60))
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.Timeout:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(f"GitHub API error for {url}: {e}") from e

        raise RuntimeError(f"Failed after {retries} attempts: {url}")
