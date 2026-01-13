"""
Catastrophe Data Collector

Fetches real catastrophe examples from git repos and processes them for training.
All repos are cloned to temp directories and cleaned up automatically.
"""

import json
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from tqdm import tqdm


@dataclass
class CatastropheExample:
    """A single catastrophe training example."""
    id: str
    name: str
    cve: Optional[str]
    
    # Code
    before_code: str
    after_code: str
    language: str
    file_path: str
    
    # Commits
    commit_introducing: Optional[str]
    commit_fixing: Optional[str]
    
    # Labels
    category: str  # security, death, financial, etc.
    root_cause: str
    complexity_score: int
    
    # Impact
    deaths: int
    financial_loss_usd: int
    affected_systems: int
    
    # Metadata
    project: str
    year: int
    description: str


class CatastropheDataCollector:
    """
    Collects catastrophe examples for training.
    
    Uses temporary directories for all repo operations - nothing is stored permanently.
    """
    
    def __init__(self, output_dir: Path):
        """
        Initialize collector.
        
        Args:
            output_dir: Where to save processed training data (NOT repos)
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Will be cleaned up automatically
        self.temp_dir = None
    
    def collect_from_catastrophe_files(
        self,
        catastrophe_dir: Path,
    ) -> List[CatastropheExample]:
        """
        Load catastrophe examples from JSON files.
        
        Args:
            catastrophe_dir: Directory containing catastrophe JSON files
                            (e.g., /Users/jonhays/DarkSeer-v3/data/catastrophes/)
        
        Returns:
            List of CatastropheExample objects
        """
        catastrophe_dir = Path(catastrophe_dir)
        
        if not catastrophe_dir.exists():
            raise ValueError(f"Catastrophe directory not found: {catastrophe_dir}")
        
        examples = []
        json_files = list(catastrophe_dir.glob("*.json"))
        
        print(f"📂 Found {len(json_files)} catastrophe files")
        
        for json_file in tqdm(json_files, desc="Loading catastrophes"):
            try:
                with open(json_file) as f:
                    data = json.load(f)
                
                # Extract data
                example = CatastropheExample(
                    id=data.get("id", json_file.stem),
                    name=data.get("name", "Unknown"),
                    cve=data.get("cve"),
                    
                    # Code (may be reconstructed for older incidents)
                    before_code=data.get("vulnerable_code", {}).get("code", ""),
                    after_code=data.get("fix_code", {}).get("code", ""),
                    language=data.get("language", "unknown"),
                    file_path=data.get("vulnerable_code", {}).get("file", "unknown"),
                    
                    # Commits
                    commit_introducing=data.get("vulnerable_code", {}).get("commit_introducing"),
                    commit_fixing=data.get("fix_code", {}).get("commit_fixing"),
                    
                    # Labels
                    category=data.get("labels", {}).get("category", "unknown"),
                    root_cause=data.get("labels", {}).get("root_cause", "unknown"),
                    complexity_score=data.get("labels", {}).get("complexity_score", 5),
                    
                    # Impact
                    deaths=data.get("labels", {}).get("deaths", 0),
                    financial_loss_usd=data.get("labels", {}).get("financial_loss_usd", 0),
                    affected_systems=data.get("labels", {}).get("affected_systems", 0),
                    
                    # Metadata
                    project=data.get("project", "Unknown"),
                    year=data.get("year", 0),
                    description=data.get("description", ""),
                )
                
                # Only include if we have code
                if example.before_code and example.after_code:
                    examples.append(example)
                else:
                    print(f"   ⚠️  Skipping {json_file.name}: no code available")
                    
            except Exception as e:
                print(f"   ❌ Error loading {json_file.name}: {e}")
        
        print(f"✅ Loaded {len(examples)} catastrophe examples with code")
        return examples
    
    def fetch_from_git(
        self,
        repo_url: str,
        commit_fixing: str,
        file_paths: List[str],
        project_name: str,
    ) -> Optional[Tuple[str, str, str]]:
        """
        Fetch before/after code from a git commit.
        
        Uses a temporary directory that is automatically cleaned up.
        
        Args:
            repo_url: Git repository URL
            commit_fixing: Commit hash that fixes the vulnerability
            file_paths: List of files to extract
            project_name: Name for logging
        
        Returns:
            (before_code, after_code, language) or None if fetch fails
        """
        # Create temp directory for this repo
        with tempfile.TemporaryDirectory(prefix=f"darkseer_{project_name}_") as temp_dir:
            temp_path = Path(temp_dir)
            repo_dir = temp_path / "repo"
            repo_dir.mkdir()
            
            print(f"   📥 Fetching {project_name} commit {commit_fixing[:8]}...")
            
            # Initialize repo
            self._run_cmd(["git", "init"], cwd=repo_dir)
            self._run_cmd(["git", "remote", "add", "origin", repo_url], cwd=repo_dir)
            
            # Fetch just the commit we need
            stdout, stderr, code = self._run_cmd(
                ["git", "fetch", "--depth=2", "origin", commit_fixing],
                cwd=repo_dir,
                timeout=120,
            )
            
            if code != 0:
                print(f"      ⚠️  Could not fetch commit: {stderr[:100]}")
                return None
            
            # Checkout
            self._run_cmd(["git", "checkout", commit_fixing], cwd=repo_dir)
            
            # Get file contents before and after
            before_code = ""
            after_code = ""
            
            for file_path in file_paths:
                # After (fixed)
                after = self._get_file_at_commit(repo_dir, commit_fixing, file_path)
                if after:
                    after_code += after + "\n\n"
                
                # Before (vulnerable)
                before = self._get_file_before_commit(repo_dir, commit_fixing, file_path)
                if before:
                    before_code += before + "\n\n"
            
            # Detect language from file extension
            language = self._detect_language(file_paths[0] if file_paths else "")
            
            # Temp directory automatically cleaned up when we exit this block
            return (before_code.strip(), after_code.strip(), language)
    
    def save_dataset(
        self,
        examples: List[CatastropheExample],
        output_file: str = "catastrophes.json",
    ):
        """
        Save processed examples to disk.
        
        Args:
            examples: List of catastrophe examples
            output_file: Output filename (saved in output_dir)
        """
        output_path = self.output_dir / output_file
        
        # Convert to serializable format
        data = {
            "num_examples": len(examples),
            "categories": self._count_categories(examples),
            "examples": [asdict(ex) for ex in examples],
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Saved {len(examples)} examples to {output_path}")
        
        # Print statistics
        print(f"\n📊 Dataset Statistics:")
        print(f"   Total examples: {len(examples)}")
        print(f"   Languages: {self._count_field(examples, 'language')}")
        print(f"   Categories: {self._count_field(examples, 'category')}")
        print(f"   Root causes: {self._count_field(examples, 'root_cause')}")
        print(f"   Death-causing: {sum(1 for e in examples if e.deaths > 0)}")
        print(f"   High financial impact ($100M+): {sum(1 for e in examples if e.financial_loss_usd >= 100000000)}")
    
    def _run_cmd(
        self,
        cmd: List[str],
        cwd: Path,
        timeout: int = 60,
    ) -> Tuple[str, str, int]:
        """Run a command and return output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            return "", "Timeout", 1
        except Exception as e:
            return "", str(e), 1
    
    def _get_file_at_commit(
        self,
        repo_dir: Path,
        commit: str,
        file_path: str,
    ) -> Optional[str]:
        """Get file contents at a commit."""
        stdout, stderr, code = self._run_cmd(
            ["git", "show", f"{commit}:{file_path}"],
            cwd=repo_dir,
        )
        return stdout if code == 0 else None
    
    def _get_file_before_commit(
        self,
        repo_dir: Path,
        commit: str,
        file_path: str,
    ) -> Optional[str]:
        """Get file contents before a commit."""
        stdout, stderr, code = self._run_cmd(
            ["git", "show", f"{commit}^:{file_path}"],
            cwd=repo_dir,
        )
        return stdout if code == 0 else None
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext = Path(file_path).suffix.lower()
        
        lang_map = {
            '.c': 'c',
            '.h': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.hpp': 'cpp',
            '.java': 'java',
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
        }
        
        return lang_map.get(ext, 'unknown')
    
    def _count_categories(self, examples: List[CatastropheExample]) -> Dict[str, int]:
        """Count examples by category."""
        counts = {}
        for ex in examples:
            counts[ex.category] = counts.get(ex.category, 0) + 1
        return counts
    
    def _count_field(self, examples: List[CatastropheExample], field: str) -> Dict[str, int]:
        """Count examples by field value."""
        counts = {}
        for ex in examples:
            value = getattr(ex, field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

