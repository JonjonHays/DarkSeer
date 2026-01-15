#!/usr/bin/env python3
"""
Collect training data from verified catastrophes.

This script:
1. Loads verified catastrophes
2. Uses surgical fetch to get commit windows
3. Extracts code diffs (before/after)
4. Collects safe commits from the same repos (component-aware sampling)
5. Outputs training dataset in JSON format
"""

import json
import sys
import tempfile
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from training.types import CatastropheRecord, CatastropheType, TrainingExample
from training.surgical_fetch import SurgicalFetcher, FetchConfig


@dataclass
class CollectionConfig:
    """Configuration for data collection."""
    ancestors_count: int = 10       # Commits before fix
    descendants_count: int = 10     # Commits after fix
    safe_ratio: int = 100           # Safe commits per catastrophic commit
    max_safe_per_repo: int = 500    # Cap on safe commits per repo
    output_dir: Path = Path("data/training")


def load_verified_catastrophes() -> List[CatastropheRecord]:
    """Load only verified catastrophes from JSON."""
    json_path = Path(__file__).parent.parent / "data" / "verified_catastrophes.json"
    
    with open(json_path) as f:
        data = json.load(f)
    
    records = []
    for cat in data.get("catastrophes", []):
        if not cat.get("verified"):
            continue
        if not cat.get("fixing_commits"):
            continue
            
        record = CatastropheRecord(
            id=cat["id"],
            name=cat["name"],
            cve=cat.get("cve"),
            repo_url=cat["repo_url"],
            breaking_commits=cat.get("breaking_commits", []),
            fixing_commits=cat.get("fixing_commits", []),
            catastrophe_type=CatastropheType(cat.get("catastrophe_type", "sudden")),
            is_systemic=cat.get("is_systemic", False),
            latency_years=cat.get("latency_years"),
            language=cat.get("language", "c"),
            affected_files=cat.get("affected_files", []),
            severity_score=cat.get("severity_score", 5),
            deaths=cat.get("deaths", 0),
            financial_loss_usd=cat.get("financial_loss_usd", 0),
            year=cat.get("year", 2020),
            description=cat.get("description", ""),
            verified=True,
        )
        records.append(record)
    
    return records


def collect_catastrophic_examples(
    record: CatastropheRecord,
    fetcher: SurgicalFetcher,
    work_dir: Path,
) -> List[TrainingExample]:
    """Collect catastrophic examples from a single catastrophe."""
    examples = []
    
    try:
        repo_dir, windows = fetcher.fetch_catastrophe_window(record, work_dir)
        
        for window in windows:
            # Get diff for the target commit
            before, after, files = fetcher.get_commit_diff(repo_dir, window.target_sha)
            
            if not before and not after:
                continue
                
            example = TrainingExample(
                commit_sha=window.target_sha,
                repo_url=record.repo_url,
                before_code=before,
                after_code=after,
                changed_files=files,
                is_catastrophic=True,
                catastrophe_id=record.id,
                category="FIXING",  # This is the fix commit
            )
            examples.append(example)
            
    except Exception as e:
        print(f"  ❌ Error collecting {record.id}: {e}")
    
    return examples


def collect_safe_examples(
    record: CatastropheRecord,
    fetcher: SurgicalFetcher,
    work_dir: Path,
    catastrophic_files: List[str],
    count: int,
) -> List[TrainingExample]:
    """
    Collect safe commits from the same repo.
    
    Uses component-aware sampling: prioritize commits that touch
    the same files/components as the catastrophic change.
    """
    examples = []
    
    try:
        repo_dir, windows = fetcher.fetch_catastrophe_window(record, work_dir)
        
        if not windows:
            return []
        
        # Get ancestors as safe commits (they existed before the fix)
        window = windows[0]
        safe_candidates = window.ancestors + window.descendants
        
        # Score by component overlap
        scored = []
        for sha in safe_candidates:
            try:
                before, after, files = fetcher.get_commit_diff(repo_dir, sha)
                if not files:
                    continue
                    
                # Calculate component overlap
                overlap = len(set(files) & set(catastrophic_files)) / max(len(catastrophic_files), 1)
                scored.append((sha, before, after, files, overlap))
            except:
                continue
        
        # Sort by overlap (higher = more similar to catastrophic)
        scored.sort(key=lambda x: x[4], reverse=True)
        
        # Take top N
        for sha, before, after, files, overlap in scored[:count]:
            example = TrainingExample(
                commit_sha=sha,
                repo_url=record.repo_url,
                before_code=before,
                after_code=after,
                changed_files=files,
                is_catastrophic=False,
                catastrophe_id=None,
                category="SAFE_NEARBY",
                component_overlap=overlap,
            )
            examples.append(example)
            
    except Exception as e:
        print(f"  ⚠️  Error collecting safe examples: {e}")
    
    return examples


def main():
    print("=" * 60)
    print("  DarkSeer Training Data Collection")
    print("=" * 60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = CollectionConfig()
    config.output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load verified catastrophes
    records = load_verified_catastrophes()
    print(f"\nLoaded {len(records)} verified catastrophes")
    
    # Configure fetcher
    fetch_config = FetchConfig(
        ancestors_count=config.ancestors_count,
        descendants_count=config.descendants_count,
    )
    fetcher = SurgicalFetcher(fetch_config)
    
    all_catastrophic = []
    all_safe = []
    
    for i, record in enumerate(records):
        print(f"\n[{i+1}/{len(records)}] Processing {record.name} ({record.cve})")
        print(f"  Repo: {record.repo_url}")
        
        with tempfile.TemporaryDirectory(prefix="darkseer_collect_") as temp_dir:
            work_dir = Path(temp_dir)
            
            # Collect catastrophic examples
            print("  Collecting catastrophic examples...")
            catastrophic = collect_catastrophic_examples(record, fetcher, work_dir)
            print(f"  ✓ Found {len(catastrophic)} catastrophic examples")
            
            # Get files from catastrophic commits for component-aware sampling
            cat_files = []
            for ex in catastrophic:
                cat_files.extend(ex.changed_files)
            cat_files = list(set(cat_files))
            
            # Collect safe examples
            print("  Collecting safe examples...")
            safe_count = min(len(catastrophic) * config.safe_ratio, config.max_safe_per_repo)
            safe = collect_safe_examples(record, fetcher, work_dir, cat_files, safe_count)
            print(f"  ✓ Found {len(safe)} safe examples")
            
            all_catastrophic.extend(catastrophic)
            all_safe.extend(safe)
    
    # Summary
    print("\n" + "=" * 60)
    print("  COLLECTION SUMMARY")
    print("=" * 60)
    print(f"  Catastrophic examples: {len(all_catastrophic)}")
    print(f"  Safe examples: {len(all_safe)}")
    print(f"  Total: {len(all_catastrophic) + len(all_safe)}")
    print(f"  Ratio: 1:{len(all_safe) // max(len(all_catastrophic), 1)}")
    
    # Save to JSON
    output = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "catastrophes_count": len(records),
            "catastrophic_examples": len(all_catastrophic),
            "safe_examples": len(all_safe),
        },
        "catastrophic": [asdict(ex) for ex in all_catastrophic],
        "safe": [asdict(ex) for ex in all_safe],
    }
    
    output_path = config.output_dir / "training_data.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n  ✓ Saved to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
