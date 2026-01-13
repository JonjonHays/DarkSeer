#!/usr/bin/env python3
"""
Collect Training Data for DarkSeer

Processes the catastrophe examples from DarkSeer-v3 and prepares them for training.
All git operations use temporary directories - nothing is stored in the repo.

Usage:
    python scripts/collect_training_data.py
    
Output:
    data/training/catastrophes.json - Processed training examples
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from training.data_collector import CatastropheDataCollector


# Path to DarkSeer-v3 catastrophe data
DARKSEER_V3_CATASTROPHES = Path("/Users/jonhays/DarkSeer-v3/data/catastrophes")

# Output directory (in DarkSeer repo)
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "training"


def main():
    """Collect and process catastrophe training data."""
    
    print("=" * 70)
    print("  DarkSeer Training Data Collection")
    print("=" * 70)
    print()
    
    # Check if DarkSeer-v3 data exists
    if not DARKSEER_V3_CATASTROPHES.exists():
        print(f"❌ DarkSeer-v3 catastrophe data not found at:")
        print(f"   {DARKSEER_V3_CATASTROPHES}")
        print()
        print("   Please ensure DarkSeer-v3 project exists with catastrophe data.")
        return 1
    
    # Initialize collector
    collector = CatastropheDataCollector(output_dir=OUTPUT_DIR)
    
    # Load catastrophe examples from JSON files
    print(f"📂 Loading catastrophes from: {DARKSEER_V3_CATASTROPHES}")
    print()
    
    examples = collector.collect_from_catastrophe_files(DARKSEER_V3_CATASTROPHES)
    
    if not examples:
        print("❌ No catastrophe examples found with code")
        return 1
    
    # Save processed dataset
    print()
    collector.save_dataset(examples, output_file="catastrophes.json")
    
    # Print some example details
    print("\n" + "=" * 70)
    print("  Sample Examples")
    print("=" * 70)
    
    for i, ex in enumerate(examples[:5]):
        print(f"\n{i+1}. {ex.name} ({ex.cve or 'N/A'})")
        print(f"   Project: {ex.project}")
        print(f"   Language: {ex.language}")
        print(f"   Category: {ex.category}")
        print(f"   Root cause: {ex.root_cause}")
        print(f"   Impact: {ex.deaths} deaths, ${ex.financial_loss_usd:,}")
        print(f"   Code: {len(ex.before_code)} chars before → {len(ex.after_code)} chars after")
    
    if len(examples) > 5:
        print(f"\n   ... and {len(examples) - 5} more")
    
    print("\n" + "=" * 70)
    print("  ✅ Data collection complete!")
    print("=" * 70)
    print()
    print(f"📊 Next steps:")
    print(f"   1. Review data: {OUTPUT_DIR}/catastrophes.json")
    print(f"   2. Run analysis: python scripts/analyze_dataset.py")
    print(f"   3. Train model: python scripts/train.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

