#!/usr/bin/env python3
"""
Test surgical fetch on verified catastrophes.

Tests the efficient git fetching strategy on:
1. Heartbleed (OpenSSL, GitHub)
2. PwnKit (polkit, GitLab)
3. Log4Shell (Log4j, GitHub)
"""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from training.types import CatastropheRecord, CatastropheType
from training.surgical_fetch import SurgicalFetcher, FetchConfig


def load_verified_catastrophes() -> list:
    """Load verified catastrophes from JSON."""
    json_path = Path(__file__).parent.parent / "data" / "verified_catastrophes.json"
    
    with open(json_path) as f:
        data = json.load(f)
    
    records = []
    for cat in data.get("catastrophes", []):
        if not cat.get("verified"):
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


def test_single_catastrophe(record: CatastropheRecord, fetcher: SurgicalFetcher):
    """Test fetching a single catastrophe."""
    print(f"\n{'='*60}")
    print(f"Testing: {record.name} ({record.cve})")
    print(f"{'='*60}")
    print(f"  Repo: {record.repo_url}")
    print(f"  Fix commits: {record.fixing_commits}")
    print(f"  Language: {record.language}")
    print()
    
    with tempfile.TemporaryDirectory(prefix="darkseer_test_") as temp_dir:
        work_dir = Path(temp_dir)
        
        try:
            # Fetch the commit window
            repo_dir, windows = fetcher.fetch_catastrophe_window(record, work_dir)
            
            print(f"  ✅ Fetch succeeded!")
            print(f"  Repo dir: {repo_dir}")
            print(f"  Windows: {len(windows)}")
            
            for i, window in enumerate(windows):
                print(f"\n  Window {i+1}:")
                print(f"    Target: {window.target_sha[:8]}")
                print(f"    Ancestors: {len(window.ancestors)}")
                print(f"    Descendants: {len(window.descendants)}")
                print(f"    Total commits: {len(window.all_commits)}")
            
            # Test getting diff (without full checkout)
            if windows:
                window = windows[0]
                print(f"\n  Testing get_commit_diff on {window.target_sha[:8]}...")
                before, after, files = fetcher.get_commit_diff(repo_dir, window.target_sha)
                print(f"    Before: {len(before)} chars")
                print(f"    After: {len(after)} chars")
                print(f"    Files: {files[:3]}{'...' if len(files) > 3 else ''}")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    print("=" * 60)
    print("  DarkSeer Surgical Fetch Test")
    print("=" * 60)
    
    # Load verified catastrophes
    records = load_verified_catastrophes()
    print(f"\nLoaded {len(records)} verified catastrophes")
    
    # Configure fetcher
    config = FetchConfig(
        ancestors_count=5,   # Smaller for testing
        descendants_count=5,
    )
    fetcher = SurgicalFetcher(config)
    
    # Test each
    results = {}
    for record in records:
        success = test_single_catastrophe(record, fetcher)
        results[record.id] = success
    
    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    
    for cat_id, success in results.items():
        status = "✅" if success else "❌"
        print(f"  {status} {cat_id}")
    
    passed = sum(results.values())
    total = len(results)
    print(f"\n  {passed}/{total} passed")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

