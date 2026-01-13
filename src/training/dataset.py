"""
DarkSeer Training Dataset

Prepares data for training the ArchIdx encoder.
Converts catastrophe examples → ArchPackets → training features.
"""

import sys
import json
import torch
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from torch.utils.data import Dataset
import numpy as np

# Add ArchIdx to path
ARCHIDX_PATH = Path(__file__).parent.parent.parent / "archidx" / "src"
if not ARCHIDX_PATH.exists():
    ARCHIDX_PATH = Path(__file__).parent.parent.parent.parent / "ArchIdx" / "src"

sys.path.insert(0, str(ARCHIDX_PATH))

try:
    from arch_packet.generator import ArchPacketGenerator
    from arch_packet.ast_invariant_detector import ASTInvariantDetector
    from arch_packet.phase2_detectors import detect_phase2_invariants
    ARCHIDX_AVAILABLE = True
except ImportError:
    print("⚠️  ArchIdx not available for training")
    ARCHIDX_AVAILABLE = False


@dataclass
class TrainingExample:
    """A single training example."""
    # Code
    before_code: str
    after_code: str
    language: str
    
    # Labels
    is_catastrophic: bool  # True for catastrophes, False for safe changes
    category: str
    root_cause: str
    severity_score: float  # 0.0-1.0 based on impact
    
    # Metadata
    example_id: str
    project: str
    
    # Computed features (filled during processing)
    before_invariants: List[str] = None
    after_invariants: List[str] = None
    invariants_added: List[str] = None
    invariants_removed: List[str] = None
    
    def compute_severity(self) -> float:
        """Compute severity score from deaths/financial impact."""
        # This would be computed from the original data
        if self.category == 'death':
            return 1.0
        elif self.category in ['data_breach', 'financial']:
            return 0.8
        elif self.category == 'security':
            return 0.6
        else:
            return 0.4


class DarkSeerDataset(Dataset):
    """
    PyTorch dataset for training ArchIdx encoder.
    
    Features:
    - Invariant vectors (which invariants are present/missing)
    - Code complexity metrics
    - Language encoding
    
    Labels:
    - is_catastrophic (binary classification)
    - severity_score (regression)
    """
    
    def __init__(
        self,
        examples: List[TrainingExample],
        include_safe_examples: bool = True,
    ):
        """
        Initialize dataset.
        
        Args:
            examples: List of training examples (catastrophes + safe changes)
            include_safe_examples: Whether to include safe changes as negatives
        """
        self.examples = examples
        
        if not include_safe_examples:
            self.examples = [e for e in examples if e.is_catastrophic]
        
        # Compute features for all examples
        self._compute_features()
        
        # Build vocabulary of invariants
        self.invariant_vocab = self._build_invariant_vocab()
        
        print(f"📊 Dataset: {len(self.examples)} examples")
        print(f"   Catastrophic: {sum(1 for e in self.examples if e.is_catastrophic)}")
        print(f"   Safe: {sum(1 for e in self.examples if not e.is_catastrophic)}")
        print(f"   Invariant vocabulary: {len(self.invariant_vocab)} types")
    
    def __len__(self):
        return len(self.examples)
    
    def __getitem__(self, idx):
        """Get a training example as tensors."""
        example = self.examples[idx]
        
        # Convert to feature vector
        features = self._example_to_features(example)
        
        # Labels
        is_catastrophic = torch.tensor([1.0 if example.is_catastrophic else 0.0], dtype=torch.float32)
        severity = torch.tensor([example.severity_score], dtype=torch.float32)
        
        return {
            'features': features,
            'is_catastrophic': is_catastrophic,
            'severity': severity,
            'example_id': example.example_id,
        }
    
    def _compute_features(self):
        """Compute features for all examples."""
        if not ARCHIDX_AVAILABLE:
            return
        
        detector = ASTInvariantDetector()
        
        for example in self.examples:
            # Detect invariants in before/after code
            before_invs = detector.detect_invariants(
                example.before_code,
                example.language,
                f"{example.example_id}_before",
            )
            
            after_invs = detector.detect_invariants(
                example.after_code,
                example.language,
                f"{example.example_id}_after",
            )
            
            # Also detect Phase 2 invariants
            phase2_before = detect_phase2_invariants(example.before_code, example.language)
            phase2_after = detect_phase2_invariants(example.after_code, example.language)
            
            # Extract invariant types
            example.before_invariants = [i.invariant_type.value for i in before_invs]
            example.before_invariants.extend([i['type'].value for i in phase2_before if 'type' in i])
            
            example.after_invariants = [i.invariant_type.value for i in after_invs]
            example.after_invariants.extend([i['type'].value for i in phase2_after if 'type' in i])
            
            # Compute delta
            before_set = set(example.before_invariants)
            after_set = set(example.after_invariants)
            
            example.invariants_added = list(after_set - before_set)
            example.invariants_removed = list(before_set - after_set)
    
    def _build_invariant_vocab(self) -> Dict[str, int]:
        """Build vocabulary of all invariant types seen."""
        all_invariants = set()
        
        for example in self.examples:
            if example.before_invariants:
                all_invariants.update(example.before_invariants)
            if example.after_invariants:
                all_invariants.update(example.after_invariants)
        
        # Create index mapping
        vocab = {inv: idx for idx, inv in enumerate(sorted(all_invariants))}
        return vocab
    
    def _example_to_features(self, example: TrainingExample) -> torch.Tensor:
        """
        Convert example to feature vector.
        
        Features:
        - Invariant presence vector (one-hot for each invariant type)
        - Invariant delta vector (which were added/removed)
        - Code complexity (number of lines, functions, etc.)
        - Language encoding
        """
        features = []
        
        # 1. Invariant presence (before)
        inv_vector_before = self._invariants_to_vector(example.before_invariants or [])
        features.extend(inv_vector_before)
        
        # 2. Invariant presence (after)
        inv_vector_after = self._invariants_to_vector(example.after_invariants or [])
        features.extend(inv_vector_after)
        
        # 3. Invariant delta
        added_vector = self._invariants_to_vector(example.invariants_added or [])
        removed_vector = self._invariants_to_vector(example.invariants_removed or [])
        features.extend(added_vector)
        features.extend(removed_vector)
        
        # 4. Code complexity features
        before_lines = len(example.before_code.split('\n'))
        after_lines = len(example.after_code.split('\n'))
        features.extend([
            before_lines / 1000.0,  # Normalize
            after_lines / 1000.0,
            abs(after_lines - before_lines) / 1000.0,  # Size of change
        ])
        
        # 5. Language encoding (one-hot)
        languages = ['c', 'cpp', 'java', 'python', 'javascript', 'go', 'rust', 'other']
        lang_vector = [1.0 if example.language.lower() in lang else 0.0 for lang in languages]
        features.extend(lang_vector)
        
        return torch.tensor(features, dtype=torch.float32)
    
    def _invariants_to_vector(self, invariants: List[str]) -> List[float]:
        """Convert list of invariants to one-hot vector."""
        vector = [0.0] * len(self.invariant_vocab)
        for inv in invariants:
            if inv in self.invariant_vocab:
                idx = self.invariant_vocab[inv]
                vector[idx] = 1.0
        return vector
    
    def get_feature_dim(self) -> int:
        """Get dimensionality of feature vector."""
        # Invariants before + after + added + removed
        inv_dim = len(self.invariant_vocab) * 4
        # Code complexity
        complexity_dim = 3
        # Language
        lang_dim = 8
        return inv_dim + complexity_dim + lang_dim


def load_catastrophes(json_path: Path) -> List[TrainingExample]:
    """Load catastrophe examples from JSON."""
    with open(json_path) as f:
        data = json.load(f)
    
    examples = []
    for ex_data in data.get('examples', []):
        # Compute severity score
        deaths = ex_data.get('deaths', 0)
        financial = ex_data.get('financial_loss_usd', 0)
        
        if deaths > 0:
            severity = 1.0
        elif financial >= 1_000_000_000:  # $1B+
            severity = 0.9
        elif financial >= 100_000_000:  # $100M+
            severity = 0.7
        else:
            severity = 0.5
        
        example = TrainingExample(
            before_code=ex_data.get('before_code', ''),
            after_code=ex_data.get('after_code', ''),
            language=ex_data.get('language', 'unknown'),
            is_catastrophic=True,
            category=ex_data.get('category', 'unknown'),
            root_cause=ex_data.get('root_cause', 'unknown'),
            severity_score=severity,
            example_id=ex_data.get('id', ''),
            project=ex_data.get('project', 'unknown'),
        )
        examples.append(example)
    
    return examples


def load_safe_commits(json_path: Path, max_count: int = 100) -> List[TrainingExample]:
    """
    Load safe commits as negative examples.
    
    Args:
        json_path: Path to safe_commits.json from DarkSeer-v3
        max_count: Maximum number to load (safe commits are numerous)
    """
    with open(json_path) as f:
        data = json.load(f)
    
    examples = []
    commits = data.get('commits', [])[:max_count]
    
    for commit in commits:
        example = TrainingExample(
            before_code=commit.get('diff', ''),  # Simplified
            after_code=commit.get('diff', ''),
            language=commit.get('language', 'unknown'),
            is_catastrophic=False,
            category='safe',
            root_cause='none',
            severity_score=0.0,
            example_id=commit.get('sha', ''),
            project=commit.get('repo', 'unknown'),
        )
        examples.append(example)
    
    return examples

