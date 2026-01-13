#!/usr/bin/env python3
"""
Analyze Training Dataset

Examines the collected catastrophes to identify:
1. What invariant types are needed
2. Coverage gaps in current detection
3. Patterns we're missing

This informs what invariant detectors to build in Phase 2.
"""

import sys
import json
from pathlib import Path
from collections import Counter, defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def load_dataset(path: Path):
    """Load the catastrophe dataset."""
    with open(path) as f:
        return json.load(f)


def analyze_root_causes(examples):
    """Analyze root causes to identify needed invariants."""
    
    print("\n" + "=" * 70)
    print("  ROOT CAUSE → INVARIANT MAPPING")
    print("=" * 70)
    
    # Map root causes to required invariants
    invariant_map = {
        'buffer_over_read': ['bounds_checked', 'input_length_validated'],
        'buffer_overflow': ['bounds_checked', 'input_length_validated'],
        'heap_buffer_overflow': ['bounds_checked', 'malloc_checked'],
        'out_of_bounds_read': ['bounds_checked'],
        'out_of_bounds_write': ['bounds_checked'],
        
        'race_condition': ['mutex_protected', 'atomic_operation', 'critical_section'],
        
        'unsafe_deserialization': ['deserialization_safe', 'type_validated'],
        'injection': ['input_sanitized', 'parameterized_query'],
        'sql_injection': ['parameterized_query', 'input_sanitized'],
        
        'integer_overflow': ['overflow_checked', 'safe_arithmetic'],
        'floating_point_accumulation': ['precision_aware'],
        
        'uninitialized_memory': ['initialized_before_use'],
        'certificate_validation_bypass': ['certificate_validated'],
        'authorization_bypass': ['authorized'],
        
        'prototype_pollution': ['prototype_frozen', 'property_validated'],
        'class_loader_manipulation': ['classloader_restricted'],
        
        'supply_chain_attack': ['dependency_verified', 'checksum_validated'],
        'dependency_removal': ['dependency_exists'],
        
        'logic_error': ['state_machine_valid', 'invariant_maintained'],
        'unit_conversion_error': ['units_consistent'],
        'parsing_vulnerability': ['parser_bounded', 'input_validated'],
        
        'regex_denial_of_service': ['regex_bounded', 'timeout_set'],
        'speculative_execution': ['speculation_barrier'],
        'deployment_error': ['configuration_validated'],
    }
    
    # Count what invariants we need
    needed_invariants = Counter()
    root_causes = Counter()
    
    for ex in examples:
        root_cause = ex.get('root_cause', 'unknown')
        root_causes[root_cause] += 1
        
        invariants = invariant_map.get(root_cause, ['unknown'])
        for inv in invariants:
            needed_invariants[inv] += 1
    
    print("\nRoot Causes (frequency):")
    for cause, count in root_causes.most_common():
        print(f"  {count:2d}x {cause}")
    
    print("\n" + "-" * 70)
    print("Invariants Needed (by frequency):")
    print("-" * 70)
    
    # Current vs. needed
    current_invariants = {
        'bounds_checked',
        'null_checked',
        'authenticated',
        'authorized',
        'encrypted',
        'rate_limited',
        'audit_logged',
    }
    
    for inv, count in needed_invariants.most_common():
        status = "✅ EXISTS" if inv in current_invariants else "❌ MISSING"
        print(f"  {count:2d}x {inv:30s} {status}")
    
    # Group missing by category
    missing = [inv for inv in needed_invariants if inv not in current_invariants]
    
    print("\n" + "=" * 70)
    print("  MISSING INVARIANTS BY CATEGORY")
    print("=" * 70)
    
    categories = {
        'Memory Safety': [
            'input_length_validated', 'malloc_checked', 'initialized_before_use',
            'overflow_checked', 'safe_arithmetic'
        ],
        'Concurrency': [
            'mutex_protected', 'atomic_operation', 'critical_section',
        ],
        'Input Validation': [
            'input_sanitized', 'parameterized_query', 'deserialization_safe',
            'type_validated', 'parser_bounded', 'input_validated'
        ],
        'State Management': [
            'state_machine_valid', 'invariant_maintained', 'prototype_frozen',
            'property_validated'
        ],
        'Security': [
            'certificate_validated', 'dependency_verified', 'checksum_validated',
            'classloader_restricted'
        ],
        'Resource Management': [
            'regex_bounded', 'timeout_set', 'speculation_barrier',
        ],
        'Configuration': [
            'units_consistent', 'configuration_validated', 'dependency_exists',
            'precision_aware'
        ],
    }
    
    for category, invs in categories.items():
        missing_in_cat = [i for i in invs if i in missing]
        if missing_in_cat:
            print(f"\n{category}:")
            for inv in missing_in_cat:
                count = needed_invariants[inv]
                print(f"  {count:2d}x {inv}")
    
    return needed_invariants, root_causes


def analyze_by_category(examples):
    """Analyze by catastrophe category."""
    
    print("\n" + "=" * 70)
    print("  CATASTROPHE CATEGORIES")
    print("=" * 70)
    
    by_category = defaultdict(list)
    
    for ex in examples:
        cat = ex.get('category', 'unknown')
        by_category[cat].append(ex)
    
    for cat, exs in sorted(by_category.items()):
        print(f"\n{cat.upper()} ({len(exs)} examples):")
        
        # Show sample
        for ex in exs[:3]:
            name = ex.get('name', 'Unknown')
            deaths = ex.get('deaths', 0)
            loss = ex.get('financial_loss_usd', 0)
            print(f"  • {name:40s} {deaths} deaths, ${loss:,}")
        
        if len(exs) > 3:
            print(f"  ... and {len(exs) - 3} more")


def analyze_languages(examples):
    """Analyze language distribution."""
    
    print("\n" + "=" * 70)
    print("  LANGUAGE DISTRIBUTION")
    print("=" * 70)
    
    langs = Counter(ex.get('language', 'unknown') for ex in examples)
    
    for lang, count in langs.most_common():
        pct = (count / len(examples)) * 100
        bar = "█" * int(pct / 2)
        print(f"  {lang:30s} {count:2d} ({pct:5.1f}%) {bar}")


def priority_recommendations(needed_invariants, root_causes):
    """Recommend priority order for building invariant detectors."""
    
    print("\n" + "=" * 70)
    print("  PHASE 2 PRIORITY RECOMMENDATIONS")
    print("=" * 70)
    
    # Priority based on:
    # 1. Frequency in dataset
    # 2. Severity (death-causing vs. financial)
    # 3. Detectability (can we realistically detect it via AST?)
    
    priorities = [
        {
            'name': 'Concurrency Safety',
            'invariants': ['mutex_protected', 'atomic_operation', 'critical_section'],
            'reason': 'Death-causing (Therac-25), hard to test, high impact',
            'examples': ['Therac-25 race condition', 'Dirty COW race condition'],
            'difficulty': 'Medium',
        },
        {
            'name': 'Input Validation',
            'invariants': ['input_sanitized', 'deserialization_safe', 'parameterized_query'],
            'reason': 'Most common root cause (injection, deserialization)',
            'examples': ['Log4Shell', 'Equifax Struts', 'Rails YAML'],
            'difficulty': 'Medium',
        },
        {
            'name': 'Integer Safety',
            'invariants': ['overflow_checked', 'safe_arithmetic'],
            'reason': 'Subtle, safety-critical (Ariane 5, Patriot missile)',
            'examples': ['Ariane 5 overflow', 'Patriot missile timing'],
            'difficulty': 'Easy',
        },
        {
            'name': 'Memory Initialization',
            'invariants': ['initialized_before_use'],
            'reason': 'Common in C/C++ codebases',
            'examples': ['Dirty Pipe', 'goto fail'],
            'difficulty': 'Hard (requires data flow analysis)',
        },
        {
            'name': 'State Machine Validation',
            'invariants': ['state_machine_valid', 'invariant_maintained'],
            'reason': 'Death-causing (737 MAX), complex systems',
            'examples': ['Boeing 737 MAX MCAS', 'Kubernetes privilege escalation'],
            'difficulty': 'Hard',
        },
        {
            'name': 'Resource Bounds',
            'invariants': ['regex_bounded', 'timeout_set', 'parser_bounded'],
            'reason': 'DoS attacks, common in web services',
            'examples': ['ua-parser ReDoS', 'XML bomb attacks'],
            'difficulty': 'Easy',
        },
    ]
    
    print("\nPriority Order (High → Low):\n")
    
    for i, p in enumerate(priorities, 1):
        print(f"{i}. {p['name']}")
        print(f"   Invariants: {', '.join(p['invariants'])}")
        print(f"   Why: {p['reason']}")
        print(f"   Difficulty: {p['difficulty']}")
        print(f"   Examples: {', '.join(p['examples'])}")
        print()


def main():
    """Run dataset analysis."""
    
    dataset_path = Path(__file__).parent.parent / "data" / "training" / "catastrophes.json"
    
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        print("   Run: python scripts/collect_training_data.py")
        return 1
    
    print("=" * 70)
    print("  DarkSeer Training Dataset Analysis")
    print("=" * 70)
    
    data = load_dataset(dataset_path)
    examples = data.get('examples', [])
    
    print(f"\n📊 Dataset: {len(examples)} catastrophes")
    print(f"   Deaths: {sum(ex.get('deaths', 0) for ex in examples)}")
    print(f"   Financial: ${sum(ex.get('financial_loss_usd', 0) for ex in examples):,}")
    
    # Run analyses
    needed_invariants, root_causes = analyze_root_causes(examples)
    analyze_by_category(examples)
    analyze_languages(examples)
    priority_recommendations(needed_invariants, root_causes)
    
    print("\n" + "=" * 70)
    print("  Next: Build Priority Invariant Detectors")
    print("=" * 70)
    print("\n1. Start with: Concurrency Safety + Input Validation")
    print("2. Add to: ArchIdx/src/arch_packet/ast_invariant_detector.py")
    print("3. Test on: Real catastrophes")
    print("4. Iterate!\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

