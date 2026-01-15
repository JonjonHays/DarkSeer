"""
Training data types for DarkSeer.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class CatastropheType(Enum):
    """Type of catastrophe for training purposes."""
    SUDDEN = "sudden"           # Single commit introduced the bug (e.g., Heartbleed)
    SYSTEMIC = "systemic"       # Architectural flaw since inception (e.g., libpng)
    GRADUAL = "gradual"         # Technical debt accumulation over time
    SUPPLY_CHAIN = "supply_chain"  # Malicious code injection (e.g., xz backdoor)


@dataclass
class CatastropheRecord:
    """
    A catastrophe with verified git information.
    
    This is the source of truth for training data collection.
    """
    # Identity
    id: str
    name: str
    cve: Optional[str] = None
    
    # Git info (MUST be verified before use)
    repo_url: str = ""
    breaking_commits: List[str] = field(default_factory=list)  # Commits that introduced the bug
    fixing_commits: List[str] = field(default_factory=list)    # Commits that fixed the bug
    
    # Classification
    catastrophe_type: CatastropheType = CatastropheType.SUDDEN
    is_systemic: bool = False  # True = existed since code was written
    latency_years: Optional[float] = None  # How long before discovery
    
    # Language/context
    language: str = "c"
    affected_files: List[str] = field(default_factory=list)
    
    # Impact (for prioritization)
    severity_score: int = 5  # 1-10
    deaths: int = 0
    financial_loss_usd: int = 0
    
    # Metadata
    year: int = 2020
    description: str = ""
    verified: bool = False  # Set True only after commit hashes confirmed


@dataclass 
class CommitWindow:
    """
    A window of commits around a target for training.
    
    Used to collect context around breaking/fixing commits.
    """
    target_sha: str
    ancestors: List[str] = field(default_factory=list)   # N commits before
    descendants: List[str] = field(default_factory=list)  # N commits after
    
    @property
    def all_commits(self) -> List[str]:
        """All commits in chronological order (oldest first)."""
        return self.ancestors + [self.target_sha] + self.descendants


@dataclass
class TrainingExample:
    """
    A single training example (catastrophic or safe).
    """
    commit_sha: str
    repo_url: str
    
    # Code diff
    before_code: str
    after_code: str
    changed_files: List[str]
    
    # Labels
    is_catastrophic: bool
    catastrophe_id: Optional[str] = None  # Links to CatastropheRecord if catastrophic
    
    # Context
    category: str = "unknown"  # BREAKING, FIXING, SAFE_BEFORE, SAFE_AFTER, etc.
    component_overlap: float = 0.0  # For component-aware sampling

