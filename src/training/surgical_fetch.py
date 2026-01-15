"""
Surgical Git Fetcher

Efficiently fetches only the commits we need for training,
without downloading entire repository history.

Strategy:
1. Use GitHub API to find child commits (git doesn't have "children")
2. Use --filter=blob:none for blobless clone (metadata only)
3. Use --deepen to get exactly N ancestors
4. Lazy-fetch blobs only on checkout

This minimizes bandwidth and disk usage while getting exact commit windows.
"""

import os
import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple, Callable
from urllib.parse import urlparse

from .types import CatastropheRecord, CommitWindow, TrainingExample


@dataclass
class FetchConfig:
    """Configuration for surgical fetch."""
    ancestors_count: int = 10  # N commits before target
    descendants_count: int = 10  # N commits after target
    use_sparse_checkout: bool = False  # Future optimization
    github_token: Optional[str] = None  # For API calls
    skip_verification_check: bool = False  # For verification scripts


class SurgicalFetcher:
    """
    Fetches minimal git data for training.
    
    Uses blobless clones and targeted fetches to minimize
    bandwidth while getting complete commit windows.
    
    Requires Git 2.19+ for partial clone support.
    """
    
    MIN_GIT_VERSION = (2, 19)
    
    def __init__(self, config: FetchConfig = None):
        self.config = config or FetchConfig()
        self._check_git_version()
    
    def _check_git_version(self):
        """Verify git version supports partial clone."""
        try:
            result = subprocess.run(
                ["git", "--version"],
                capture_output=True, text=True
            )
            # "git version 2.15.1" -> (2, 15)
            version_str = result.stdout.strip().replace("git version ", "")
            parts = version_str.split(".")[:2]
            version = tuple(int(p) for p in parts if p.isdigit())
            
            if version < self.MIN_GIT_VERSION:
                raise RuntimeError(
                    f"\n❌ Git {version_str} is too old!\n"
                    f"   DarkSeer requires Git {'.'.join(map(str, self.MIN_GIT_VERSION))}+ "
                    f"for partial clone support.\n"
                    f"   Please upgrade: https://git-scm.com/downloads\n"
                    f"   Or via Homebrew: brew upgrade git"
                )
        except FileNotFoundError:
            raise RuntimeError("Git not found. Please install Git 2.19+.")
    
    def fetch_catastrophe_window(
        self,
        record: CatastropheRecord,
        work_dir: Optional[Path] = None,
    ) -> Tuple[Path, List[CommitWindow]]:
        """
        Fetch commit windows for a catastrophe.
        
        Args:
            record: Verified catastrophe record
            work_dir: Directory for git operations (temp if None)
            
        Returns:
            Tuple of (repo_dir, list of CommitWindows)
        """
        if not record.verified and not self.config.skip_verification_check:
            raise ValueError(f"CatastropheRecord {record.id} not verified!")
        
        # Create work directory
        if work_dir is None:
            work_dir = Path(tempfile.mkdtemp(prefix="darkseer_fetch_"))
        
        repo_dir = work_dir / "repo"
        repo_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize repo
        self._run_git(["init"], repo_dir)
        self._run_git(["remote", "add", "origin", record.repo_url], repo_dir)
        
        windows = []
        
        # Fetch windows around breaking commits
        for sha in record.breaking_commits:
            window = self._fetch_commit_window(
                repo_dir, record.repo_url, sha, "breaking"
            )
            if window:
                windows.append(window)
        
        # Fetch windows around fixing commits
        for sha in record.fixing_commits:
            window = self._fetch_commit_window(
                repo_dir, record.repo_url, sha, "fixing"
            )
            if window:
                windows.append(window)
        
        return repo_dir, windows
    
    def _fetch_commit_window(
        self,
        repo_dir: Path,
        repo_url: str,
        target_sha: str,
        window_type: str,
    ) -> Optional[CommitWindow]:
        """
        Fetch a window of commits around a target.
        
        Strategy (simple - option A):
        - Fetch target commit with enough depth to get N ancestors
        - Use rev-list to enumerate ancestors (works regardless of branch topology)
        - Optionally get descendants via API (GitHub compare)
        """
        
        N = self.config.ancestors_count
        M = self.config.descendants_count
        
        print(f"   Fetching {window_type} window for {target_sha[:8]}...")
        
        # 1. Fetch target commit with N+1 depth (target + N ancestors)
        # Using --filter=blob:none for blobless clone (fetch blobs on demand)
        print(f"      Fetching target + {N} ancestors...")
        stdout, stderr, code = self._run_git(
            ["fetch", "--filter=blob:none", f"--depth={N + 1}", "origin", target_sha],
            repo_dir
        )
        if code != 0:
            print(f"      ❌ Fetch failed: {stderr[:100]}")
            return None
        
        # 2. Get ancestors using rev-list (works on any branch)
        # --reverse gives oldest-first order
        stdout, _, code = self._run_git(
            ["rev-list", target_sha, f"--max-count={N + 1}", "--reverse"],
            repo_dir
        )
        if code != 0:
            print(f"      ❌ rev-list failed")
            return None
            
        all_commits = [c for c in stdout.strip().split('\n') if c]
        
        # Split: ancestors are before target, target is last
        if target_sha in all_commits:
            target_idx = all_commits.index(target_sha)
            ancestors = all_commits[:target_idx]
        else:
            # Target might be abbreviated, find by prefix
            for i, c in enumerate(all_commits):
                if c.startswith(target_sha) or target_sha.startswith(c):
                    ancestors = all_commits[:i]
                    break
            else:
                ancestors = all_commits[:-1] if all_commits else []
        
        # 3. Get descendants via API (optional - can fail gracefully)
        descendants = []
        if M > 0:
            api_descendants = self._get_descendants(repo_url, target_sha, M)
            if api_descendants:
                # Fetch tip to get descendants
                tip_sha = api_descendants[-1]
                descendant_depth = len(api_descendants) + 10
                print(f"      Fetching {len(api_descendants)} descendants (tip={tip_sha[:8]})...")
                self._run_git(
                    ["fetch", "--filter=blob:none", f"--depth={descendant_depth}", "origin", tip_sha],
                    repo_dir
                )
                # Verify we can traverse from target to tip
                stdout, _, _ = self._run_git(
                    ["rev-list", f"{target_sha}..{tip_sha}", "--reverse", f"--max-count={M}"],
                    repo_dir
                )
                descendants = [c for c in stdout.strip().split('\n') if c]
        
        print(f"      ✓ Window: {len(ancestors)} ancestors, {len(descendants)} descendants")
        
        return CommitWindow(
            target_sha=target_sha,
            ancestors=ancestors,
            descendants=descendants,
        )
    
    def _get_descendants(self, repo_url: str, target_sha: str, count: int) -> List[str]:
        """
        Get descendant commits using GitHub/GitLab API.
        
        Falls back to empty list for non-supported hosts.
        """
        # Parse repo URL to get owner/repo
        parsed = urlparse(repo_url)
        
        if "github.com" in parsed.netloc:
            return self._get_github_descendants(repo_url, target_sha, count)
        elif "gitlab" in parsed.netloc:
            return self._get_gitlab_descendants(repo_url, target_sha, count)
        else:
            print(f"      ⚠️ Unknown host {parsed.netloc}, skipping descendants")
            return []
    
    def _get_github_descendants(
        self, repo_url: str, target_sha: str, count: int
    ) -> List[str]:
        """Get descendants via GitHub Compare API."""
        # Extract owner/repo from URL
        # https://github.com/owner/repo.git -> owner/repo
        path = urlparse(repo_url).path.strip('/')
        if path.endswith('.git'):
            path = path[:-4]
        
        # Use gh CLI or curl
        try:
            # Try gh CLI first
            api_path = f"repos/{path}/compare/{target_sha}...HEAD"
            result = subprocess.run(
                ["gh", "api", api_path],
                capture_output=True, text=True, timeout=30
            )
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                commits = data.get('commits', [])
                return [c['sha'] for c in commits[:count]]
        except Exception as e:
            print(f"      ⚠️ GitHub API failed: {e}")
        
        return []
    
    def _get_gitlab_descendants(
        self, repo_url: str, target_sha: str, count: int
    ) -> List[str]:
        """Get descendants via GitLab API."""
        # GitLab API is different, for now just return empty
        # Can implement later if needed
        return []
    
    def iterate_commits(
        self,
        repo_dir: Path,
        window: CommitWindow,
        callback: Callable[[str, Path], None],
    ):
        """
        Iterate through commits in a window, checking out each.
        
        Blobs are lazy-fetched on checkout (blobless clone magic).
        
        Args:
            repo_dir: Repository directory
            window: CommitWindow to iterate
            callback: Function to call for each commit (sha, repo_dir)
        """
        for sha in window.all_commits:
            # Checkout triggers lazy blob fetch
            stdout, stderr, code = self._run_git(
                ["checkout", sha, "--quiet"],
                repo_dir
            )
            
            if code != 0:
                print(f"      ⚠️ Checkout failed for {sha[:8]}: {stderr[:50]}")
                continue
            
            callback(sha, repo_dir)
    
    def get_commit_diff(
        self,
        repo_dir: Path,
        commit_sha: str,
    ) -> Tuple[str, str, List[str]]:
        """
        Get before/after code for a commit WITHOUT full checkout.
        
        Uses git show to get file contents directly.
        
        Returns:
            Tuple of (before_code, after_code, changed_files)
        """
        # Get changed files
        stdout, _, _ = self._run_git(
            ["show", "--name-only", "--format=", commit_sha],
            repo_dir
        )
        files = [f.strip() for f in stdout.strip().split('\n') if f.strip()]
        
        if not files:
            return "", "", []
        
        # Filter to source files
        SOURCE_EXTS = {'.c', '.cpp', '.h', '.java', '.py', '.js', '.ts', '.go', '.rs', '.rb'}
        source_files = [f for f in files if any(f.endswith(ext) for ext in SOURCE_EXTS)]
        target = source_files[0] if source_files else files[0]
        
        # Get parent
        stdout, _, _ = self._run_git(["rev-parse", f"{commit_sha}^"], repo_dir)
        parent = stdout.strip()
        
        # Get before (from parent)
        stdout, _, code = self._run_git(
            ["show", f"{parent}:{target}"],
            repo_dir
        )
        before = stdout if code == 0 else ""
        
        # Get after (from commit)
        stdout, _, code = self._run_git(
            ["show", f"{commit_sha}:{target}"],
            repo_dir
        )
        after = stdout if code == 0 else ""
        
        return before, after, files
    
    def _run_git(
        self, args: List[str], cwd: Path, timeout: int = 120
    ) -> Tuple[str, str, int]:
        """Run a git command."""
        try:
            result = subprocess.run(
                ["git"] + args,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "timeout", 1
        except Exception as e:
            return "", str(e), 1


# Verified catastrophe records (commit hashes confirmed)
VERIFIED_CATASTROPHES = [
    # TODO: Add verified records after confirming commit hashes
]

