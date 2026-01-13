#!/usr/bin/env python3
"""
Collect Component-Aware Training Data

Uses K=3 hop subgraph analysis to intelligently sample safe commits
that affect the same architectural component as each catastrophe.

For each of 32 catastrophes, collects:
- 20 SAFE_BEFORE (same component, pre-vulnerability)
- 20 SAFE_AFTER (same component, post-fix)
- 10 SAFE_DURING (different component, temporal control)
- 10 SAFE_RANDOM (different repos, overfitting control)

Total: ~2,000 examples (3% catastrophic, 97% safe)

This takes 5-10 minutes due to git operations in temp directories.
"""

import sys
import json
from pathlib import Path
from tqdm import tqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from training.component_aware_collector import ComponentAwareCollector, SafeCommit
from training.data_collector import CatastropheDataCollector


def load_catastrophe_repos(repos_json: Path) -> list:
    """
    Load catastrophe repo metadata from DarkSeer-v3.
    
    This has the actual repo URLs and fix commits.
    """
    with open(repos_json) as f:
        data = json.load(f)
    
    catastrophes_with_repos = []
    
    for repo in data.get('repos', []):
        repo_url = repo.get('url')
        repo_name = repo.get('name')
        language = repo.get('language')
        
        for catastrophe in repo.get('catastrophes', []):
            fix_commit = catastrophe.get('commit_fix')
            
            if repo_url and fix_commit:
                catastrophes_with_repos.append({
                    'name': catastrophe.get('name'),
                    'cve': catastrophe.get('cve'),
                    'project': repo_name,
                    'repo_url': repo_url,
                    'fix_commit': fix_commit,
                    'language': language,
                    'root_cause': catastrophe.get('root_cause'),
                })
    
    return catastrophes_with_repos


def main():
    """Collect component-aware training data."""
    
    print("=" * 70)
    print("  DarkSeer Component-Aware Data Collection")
    print("  K=3 Hop Architectural Analysis")
    print("=" * 70)
    print()
    
    # Paths
    catastrophe_code_path = Path(__file__).parent.parent / "data" / "training" / "catastrophes.json"
    catastrophe_repos_path = Path("/Users/jonhays/DarkSeer-v3/data/catastrophe_repos.json")
    output_path = Path(__file__).parent.parent / "data" / "training" / "component_aware_dataset.json"
    
    if not catastrophe_code_path.exists():
        print(f"❌ Catastrophe code data not found: {catastrophe_code_path}")
        print("   Run: python scripts/collect_training_data.py")
        return 1
    
    if not catastrophe_repos_path.exists():
        print(f"❌ Catastrophe repos data not found: {catastrophe_repos_path}")
        print("   Need DarkSeer-v3 project at /Users/jonhays/DarkSeer-v3/")
        return 1
    
    # Load catastrophe code (has before/after code)
    print("📂 Loading catastrophe code...")
    with open(catastrophe_code_path) as f:
        code_data = json.load(f)
    catastrophe_code = {ex['id']: ex for ex in code_data.get('examples', [])}
    print(f"   Loaded {len(catastrophe_code)} catastrophes with code")
    
    # Load catastrophe repos (has repo URLs and commits)
    print("📂 Loading catastrophe repo metadata...")
    catastrophes_with_repos = load_catastrophe_repos(catastrophe_repos_path)
    print(f"   Loaded {len(catastrophes_with_repos)} catastrophes with git repos")
    print()
    
    # Initialize collector
    collector = ComponentAwareCollector(
        k_hops=3,
        overlap_threshold=0.1,
    )
    
    print("🔧 Starting component-aware collection...")
    print(f"   K-hops: {collector.k_hops}")
    print(f"   Overlap threshold: {collector.overlap_threshold}")
    print(f"   Target per catastrophe:")
    print(f"      - 20 SAFE_BEFORE (same component)")
    print(f"      - 20 SAFE_AFTER (same component)")
    print(f"      - 10 SAFE_DURING (different component)")
    print(f"      - 10 SAFE_RANDOM (different repos)")
    print()
    
    # Collect for each catastrophe
    all_data = {
        'catastrophes': [],
        'safe_commits': [],
        'metadata': {
            'k_hops': collector.k_hops,
            'overlap_threshold': collector.overlap_threshold,
            'total_catastrophes': 0,
            'total_safe_commits': 0,
        }
    }
    
    processed = 0
    
    for catastrophe_repo in tqdm(catastrophes_with_repos, desc="Processing catastrophes"):
        project = catastrophe_repo.get('project')
        cve = catastrophe_repo.get('cve')
        repo_url = catastrophe_repo.get('repo_url')
        fix_commit = catastrophe_repo.get('fix_commit')
        language = catastrophe_repo.get('language', 'unknown').lower()
        
        # Find matching code data by CVE or name
        code_entry = None
        for cat_id, cat_data in catastrophe_code.items():
            if cat_data.get('cve') == cve or cat_data.get('name') == catastrophe_repo.get('name'):
                code_entry = cat_data
                break
        
        if not code_entry:
            print(f"   ⚠️  Skipping {project}/{cve} (no code match)")
            continue
        
        # Get code
        before_code = code_entry.get('before_code', '')
        after_code = code_entry.get('after_code', '')
        
        if not before_code or not after_code:
            print(f"   ⚠️  Skipping {project} (no code in match)")
            continue
        
        # Get affected files
        file_path = code_entry.get('file_path', '')
        affected_files = [file_path] if file_path and file_path != 'unknown' else []
        
        print(f"\n{'='*70}")
        print(f"   {project} ({cve or 'N/A'})")
        print(f"{'='*70}")
        
        try:
            # Collect safe commits for this catastrophe
            safe_commits = collector.collect_for_catastrophe(
                repo_url=repo_url,
                fix_commit=fix_commit,
                affected_files=affected_files,
                language=language,
                catastrophe_before_code=before_code,
                catastrophe_after_code=after_code,
            )
            
            # Store results
            result_entry = {
                'id': code_entry.get('id'),
                'project': project,
                'cve': cve,
                'fix_commit': fix_commit,
                'safe_commits': {
                    'SAFE_BEFORE': [c.commit_hash for c in safe_commits.get('SAFE_BEFORE', [])],
                    'SAFE_AFTER': [c.commit_hash for c in safe_commits.get('SAFE_AFTER', [])],
                    'SAFE_DURING': [c.commit_hash for c in safe_commits.get('SAFE_DURING', [])],
                }
            }
            
            all_data['catastrophes'].append(result_entry)
            
            # Add safe commits to global list
            for category, commits in safe_commits.items():
                for commit in commits:
                    all_data['safe_commits'].append({
                        'commit_hash': commit.commit_hash,
                        'category': commit.category,
                        'project': project,
                        'catastrophe_id': code_entry.get('id'),
                        'component_overlap': commit.component_overlap,
                        'files': commit.files,
                        'date': commit.date,
                        'message': commit.message,
                    })
            
            processed += 1
            
        except Exception as e:
            print(f"   ❌ Error processing {project}: {e}")
            continue
    
    # Update metadata
    all_data['metadata']['total_catastrophes'] = processed
    all_data['metadata']['total_safe_commits'] = len(all_data['safe_commits'])
    
    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(all_data, f, indent=2)
    
    print(f"\n{'='*70}")
    print("  COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"\n📊 Results:")
    print(f"   Catastrophes processed: {processed}")
    print(f"   Safe commits collected: {len(all_data['safe_commits'])}")
    
    # Breakdown by category
    by_category = {}
    for commit in all_data['safe_commits']:
        cat = commit['category']
        by_category[cat] = by_category.get(cat, 0) + 1
    
    print(f"\n   By category:")
    for cat, count in sorted(by_category.items()):
        print(f"      {cat}: {count}")
    
    print(f"\n💾 Saved to: {output_path}")
    
    # Expected total
    expected_per_catastrophe = 20 + 20 + 10  # BEFORE + AFTER + DURING
    expected_total = processed * expected_per_catastrophe
    actual_total = len(all_data['safe_commits'])
    
    print(f"\n📈 Coverage:")
    print(f"   Expected: ~{expected_total} safe commits")
    print(f"   Actual: {actual_total}")
    print(f"   Success rate: {(actual_total / expected_total * 100):.1f}%")
    
    print(f"\n✅ Dataset ready for training!")
    print(f"   Next: python scripts/train.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

