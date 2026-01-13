"""
Component-Aware Safe Commit Collector

Intelligently samples safe commits based on:
1. Temporal proximity to catastrophe
2. Architectural component overlap (K=3 hop subgraph)
3. Control groups (different component, different repo)

Sampling Strategy per Catastrophe:
- 20 SAFE_BEFORE: Same component, pre-vulnerability
- 20 SAFE_AFTER: Same component, post-fix
- 10 SAFE_DURING: Different component, same timeframe
- 10 SAFE_RANDOM: Different repos entirely

Total: ~2,000 examples from 32 catastrophes (3% catastrophic rate)
"""

import sys
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import random

# Add ArchIdx to path
ARCHIDX_PATH = Path(__file__).parent.parent.parent / "archidx" / "src"
if not ARCHIDX_PATH.exists():
    ARCHIDX_PATH = Path(__file__).parent.parent.parent.parent / "ArchIdx" / "src"

sys.path.insert(0, str(ARCHIDX_PATH))

try:
    from arch_packet.subgraph_extractor import SubgraphExtractor, extract_catastrophe_component
    from arch_packet.generator import ArchPacketGenerator
    ARCHIDX_AVAILABLE = True
except ImportError:
    print("⚠️  ArchIdx not available")
    ARCHIDX_AVAILABLE = False


@dataclass
class SafeCommit:
    """A safe commit for training."""
    commit_hash: str
    repo: str
    category: str  # SAFE_BEFORE, SAFE_AFTER, SAFE_DURING, SAFE_RANDOM
    
    # Code
    before_code: str
    after_code: str
    language: str
    files: List[str]
    
    # Metadata
    date: str
    message: str
    component_overlap: float  # 0.0-1.0, overlap with catastrophe component


class ComponentAwareCollector:
    """
    Collects safe commits with architectural awareness.
    
    Uses K-hop subgraph analysis to determine which commits affect
    the same component as a catastrophe.
    """
    
    def __init__(
        self,
        k_hops: int = 3,
        overlap_threshold: float = 0.1,
    ):
        """
        Initialize collector.
        
        Args:
            k_hops: Number of hops for component definition
            overlap_threshold: Minimum overlap to be "same component"
        """
        self.k_hops = k_hops
        self.overlap_threshold = overlap_threshold
        self.extractor = SubgraphExtractor(k=k_hops) if ARCHIDX_AVAILABLE else None
    
    def collect_for_catastrophe(
        self,
        repo_url: str,
        fix_commit: str,
        affected_files: List[str],
        language: str,
        catastrophe_before_code: str = "",  # Now optional - we'll fetch real diff
        catastrophe_after_code: str = "",   # Now optional - we'll fetch real diff
    ) -> Dict[str, List[SafeCommit]]:
        """
        Collect safe commits for a single catastrophe.
        
        Args:
            repo_url: Git repository URL
            fix_commit: Commit that fixes the vulnerability
            affected_files: List of files changed by the catastrophe
            language: Programming language
            catastrophe_before_code: (deprecated) Use real diff instead
            catastrophe_after_code: (deprecated) Use real diff instead
            
        Returns:
            Dict with keys: SAFE_BEFORE, SAFE_AFTER, SAFE_DURING, SAFE_RANDOM
        """
        # Fetch commits from git in temp directory FIRST
        # Then extract REAL diff for component analysis
        with tempfile.TemporaryDirectory(prefix="darkseer_safe_") as temp_dir:
            temp_path = Path(temp_dir)
            
            # Clone repo
            print(f"   📥 Cloning repository...")
            repo_dir = self._fetch_repo(repo_url, fix_commit, temp_path)
            if not repo_dir:
                print(f"      ❌ Clone failed")
                return {}
            
            # Get REAL diff from fix commit (not reconstructed snippets!)
            print(f"   📊 Extracting REAL diff from fix commit {fix_commit[:8]}...")
            real_before, real_after, real_files = self._get_commit_diff(repo_dir, fix_commit)
            
            if not real_before or not real_after:
                print(f"      ⚠️ Could not extract diff, falling back to provided code")
                real_before = catastrophe_before_code
                real_after = catastrophe_after_code
            else:
                print(f"      ✅ Got real diff: {len(real_files)} files, {len(real_before)} bytes")
                # Update affected_files with what we actually found
                if real_files:
                    affected_files = real_files
            
            # Extract catastrophe's component using REAL code
            print(f"   📊 Extracting K={self.k_hops} hop component from real diff...")
            catastrophe_component = extract_catastrophe_component(
                real_before,
                real_after,
                language,
                k=self.k_hops,
            )
            print(f"      Component size: {len(catastrophe_component)} symbols")
            
            # Get commit metadata
            parent_commit = self._get_parent_commit(repo_dir, fix_commit)
            
            # Collect safe commits in each category
            safe_before = self._collect_safe_before(
                repo_dir, parent_commit, affected_files, language,
                catastrophe_component, target_count=20,
            )
            
            safe_after = self._collect_safe_after(
                repo_dir, fix_commit, affected_files, language,
                catastrophe_component, target_count=20,
            )
            
            safe_during = self._collect_safe_during(
                repo_dir, parent_commit, fix_commit, affected_files, language,
                catastrophe_component, target_count=10,
            )
            
            # Clean up happens automatically (temp dir)
        
        # SAFE_RANDOM comes from different repos (collected separately)
        
        return {
            'SAFE_BEFORE': safe_before,
            'SAFE_AFTER': safe_after,
            'SAFE_DURING': safe_during,
            'SAFE_RANDOM': [],  # Filled in later
        }
    
    def _fetch_repo(self, repo_url: str, commit: str, temp_dir: Path) -> Optional[Path]:
        """Fetch repo to temp directory."""
        repo_dir = temp_dir / "repo"
        
        # Try shallow clone first (faster)
        stdout, stderr, code = self._run_cmd(
            ["git", "clone", "--depth=100", repo_url, str(repo_dir)],
            temp_dir,
            timeout=180,
        )
        
        if code != 0:
            print(f"      Shallow clone failed, trying full clone...")
            # Fall back to full clone for old commits (longer timeout)
            stdout, stderr, code = self._run_cmd(
                ["git", "clone", repo_url, str(repo_dir)],
                temp_dir,
                timeout=900,  # 15 min for large repos
            )
            if code != 0:
                print(f"      Full clone also failed: {stderr[:200]}")
                return None
        
        # Try to fetch the specific commit directly
        self._run_cmd(["git", "fetch", "origin", commit], repo_dir, timeout=120)
        
        # Try to checkout the specific commit
        stdout, stderr, code = self._run_cmd(
            ["git", "checkout", commit],
            repo_dir,
        )
        
        if code != 0:
            # Commit not in shallow history, unshallow
            print(f"      Commit not found, fetching full history...")
            stdout, stderr, code = self._run_cmd(
                ["git", "fetch", "--unshallow"],
                repo_dir,
                timeout=900,  # 15 min for large repos
            )
            if code != 0:
                print(f"      Unshallow failed: {stderr[:200]}")
                return None
            
            stdout, stderr, code = self._run_cmd(
                ["git", "checkout", commit],
                repo_dir,
            )
            if code != 0:
                print(f"      Checkout failed: {stderr[:200]}")
                return None
        
        return repo_dir
    
    def _collect_safe_before(
        self,
        repo_dir: Path,
        parent_commit: str,
        affected_files: List[str],
        language: str,
        catastrophe_component,
        target_count: int,
    ) -> List[SafeCommit]:
        """Collect safe commits BEFORE the vulnerability."""
        print(f"      Collecting SAFE_BEFORE (target: {target_count})...")
        
        # Get commits before parent, touching affected files
        commits = self._get_commits_before(repo_dir, parent_commit, affected_files, limit=100)
        
        # Filter to those affecting same component
        safe_commits = []
        for commit_hash in commits:
            if len(safe_commits) >= target_count:
                break
            
            safe_commit = self._analyze_commit(
                repo_dir, commit_hash, language,
                catastrophe_component, category="SAFE_BEFORE",
            )
            
            if safe_commit and safe_commit.component_overlap >= self.overlap_threshold:
                safe_commits.append(safe_commit)
        
        print(f"         Found {len(safe_commits)} same-component commits")
        return safe_commits
    
    def _collect_safe_after(
        self,
        repo_dir: Path,
        fix_commit: str,
        affected_files: List[str],
        language: str,
        catastrophe_component,
        target_count: int,
    ) -> List[SafeCommit]:
        """Collect safe commits AFTER the fix."""
        print(f"      Collecting SAFE_AFTER (target: {target_count})...")
        
        # Get commits after fix, touching affected files
        commits = self._get_commits_after(repo_dir, fix_commit, affected_files, limit=100)
        
        safe_commits = []
        for commit_hash in commits:
            if len(safe_commits) >= target_count:
                break
            
            safe_commit = self._analyze_commit(
                repo_dir, commit_hash, language,
                catastrophe_component, category="SAFE_AFTER",
            )
            
            if safe_commit and safe_commit.component_overlap >= self.overlap_threshold:
                safe_commits.append(safe_commit)
        
        print(f"         Found {len(safe_commits)} same-component commits")
        return safe_commits
    
    def _collect_safe_during(
        self,
        repo_dir: Path,
        parent_commit: str,
        fix_commit: str,
        affected_files: List[str],
        language: str,
        catastrophe_component,
        target_count: int,
    ) -> List[SafeCommit]:
        """Collect safe commits DURING vulnerable period (different component)."""
        print(f"      Collecting SAFE_DURING (target: {target_count})...")
        
        # Get commits between parent and fix, NOT touching affected files
        commits = self._get_commits_between(repo_dir, parent_commit, fix_commit, exclude_files=affected_files, limit=50)
        
        safe_commits = []
        for commit_hash in commits:
            if len(safe_commits) >= target_count:
                break
            
            safe_commit = self._analyze_commit(
                repo_dir, commit_hash, language,
                catastrophe_component, category="SAFE_DURING",
            )
            
            # Want DIFFERENT component (overlap < threshold)
            if safe_commit and safe_commit.component_overlap < self.overlap_threshold:
                safe_commits.append(safe_commit)
        
        print(f"         Found {len(safe_commits)} different-component commits")
        return safe_commits
    
    def _analyze_commit(
        self,
        repo_dir: Path,
        commit_hash: str,
        language: str,
        catastrophe_component,
        category: str,
    ) -> Optional[SafeCommit]:
        """Analyze a single commit to extract component overlap."""
        # Get commit diff
        before_code, after_code, files = self._get_commit_diff(repo_dir, commit_hash)
        
        if not before_code or not after_code:
            return None
        
        # Extract component for this commit
        try:
            commit_component = extract_catastrophe_component(
                before_code, after_code, language, k=self.k_hops
            )
        except Exception:
            return None
        
        # Compute overlap
        overlap = catastrophe_component.overlap_ratio(commit_component)
        
        # Get metadata
        date = self._get_commit_date(repo_dir, commit_hash)
        message = self._get_commit_message(repo_dir, commit_hash)
        
        return SafeCommit(
            commit_hash=commit_hash,
            repo=str(repo_dir),
            category=category,
            before_code=before_code,
            after_code=after_code,
            language=language,
            files=files,
            date=date,
            message=message,
            component_overlap=overlap,
        )
    
    # Git helper methods
    def _run_cmd(self, cmd: List[str], cwd: Path, timeout: int = 60) -> Tuple[str, str, int]:
        """Run git command."""
        try:
            result = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
            return result.stdout, result.stderr, result.returncode
        except Exception:
            return "", "", 1
    
    def _get_parent_commit(self, repo_dir: Path, commit: str) -> str:
        """Get parent commit hash."""
        stdout, _, _ = self._run_cmd(["git", "rev-parse", f"{commit}^"], repo_dir)
        return stdout.strip()
    
    def _get_commit_date(self, repo_dir: Path, commit: str) -> str:
        """Get commit date."""
        stdout, _, _ = self._run_cmd(["git", "show", "-s", "--format=%ci", commit], repo_dir)
        return stdout.strip()
    
    def _get_commit_message(self, repo_dir: Path, commit: str) -> str:
        """Get commit message."""
        stdout, _, _ = self._run_cmd(["git", "log", "-1", "--format=%s", commit], repo_dir)
        return stdout.strip()
    
    def _get_commits_before(self, repo_dir: Path, commit: str, files: List[str], limit: int) -> List[str]:
        """Get commits before a given commit."""
        cmd = ["git", "log", "--oneline", f"-{limit}", f"{commit}^", "--"] + files
        stdout, _, _ = self._run_cmd(cmd, repo_dir)
        return [line.split()[0] for line in stdout.strip().split('\n') if line]
    
    def _get_commits_after(self, repo_dir: Path, commit: str, files: List[str], limit: int) -> List[str]:
        """Get commits after a given commit."""
        cmd = ["git", "log", "--oneline", f"-{limit}", f"{commit}..HEAD", "--"] + files
        stdout, _, _ = self._run_cmd(cmd, repo_dir)
        return [line.split()[0] for line in stdout.strip().split('\n') if line]
    
    def _get_commits_between(self, repo_dir: Path, start: str, end: str, exclude_files: List[str], limit: int) -> List[str]:
        """Get commits between two commits, excluding certain files."""
        # Get all commits in range
        cmd = ["git", "log", "--oneline", f"-{limit}", f"{start}..{end}"]
        stdout, _, _ = self._run_cmd(cmd, repo_dir)
        all_commits = [line.split()[0] for line in stdout.strip().split('\n') if line]
        
        # Filter out commits that touch excluded files
        filtered = []
        for commit_hash in all_commits:
            files_changed = self._get_files_changed(repo_dir, commit_hash)
            if not any(f in exclude_files for f in files_changed):
                filtered.append(commit_hash)
        
        return filtered
    
    def _get_files_changed(self, repo_dir: Path, commit: str) -> List[str]:
        """Get list of files changed in a commit."""
        stdout, _, _ = self._run_cmd(["git", "show", "--name-only", "--format=", commit], repo_dir)
        return [line.strip() for line in stdout.strip().split('\n') if line]
    
    def _get_commit_diff(self, repo_dir: Path, commit: str) -> Tuple[str, str, List[str]]:
        """Get before/after code for a commit.
        
        Returns the FIRST source file's content (not concatenated).
        This ensures proper parsing by Tree-sitter.
        """
        # Get changed files
        files = self._get_files_changed(repo_dir, commit)
        
        if not files:
            return "", "", []
        
        # Filter to source files we can parse
        SOURCE_EXTS = {'.c', '.cpp', '.h', '.java', '.py', '.js', '.ts', '.go', '.rs', '.rb'}
        source_files = [f for f in files if any(f.endswith(ext) for ext in SOURCE_EXTS)]
        
        if not source_files:
            source_files = files  # Fall back to all files
        
        # Get parent commit
        parent = self._get_parent_commit(repo_dir, commit)
        
        # Get content for FIRST source file only (proper parsing)
        target_file = source_files[0]
        
        # Before
        stdout, _, code = self._run_cmd(["git", "show", f"{parent}:{target_file}"], repo_dir)
        before_code = stdout if code == 0 else ""
        
        # After
        stdout, _, code = self._run_cmd(["git", "show", f"{commit}:{target_file}"], repo_dir)
        after_code = stdout if code == 0 else ""
        
        return before_code, after_code, source_files

