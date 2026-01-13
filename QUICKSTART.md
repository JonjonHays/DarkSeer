# DarkSeer Quick Start

Get up and running in 5 minutes.

## Prerequisites

- Python 3.9+
- Git
- Access to DarkSeer-v3 catastrophe data at `/Users/jonhays/DarkSeer-v3/data/catastrophes/`

## Installation

```bash
cd /Users/jonhays/DarkSeer

# Install dependencies (ArchIdx + DarkSeer)
pip install -r requirements.txt
```

## Run the Demo

```bash
# See DarkSeer detect Heartbleed
python scripts/demo_heartbleed.py
```

Expected output:
```
======================================================================
  DarkSeer Heartbleed Detection Demo
======================================================================

Risk Score: 100/100
Catastrophic: YES

Summary:
  CRITICAL: High probability of catastrophic vulnerability

Details:
  Dangerous operations found: memcpy, malloc, OPENSSL_malloc
  ⚠️  No protective invariants detected in code with dangerous operations.
  Invariants ADDED by this change: bounds_checked
  
✅ DarkSeer correctly identified Heartbleed as CATASTROPHIC
```

## Collect Training Data

```bash
# Process the 33 catastrophes from DarkSeer-v3
python scripts/collect_training_data.py
```

This will:
1. Load JSON files from `/Users/jonhays/DarkSeer-v3/data/catastrophes/`
2. Extract before/after code
3. Process and label examples
4. Save to `data/training/catastrophes.json`

**Note**: Any git operations use temp directories - nothing is stored in your repo!

## Analyze Your Own Code

```python
from src.detector.catastrophe_detector import CatastropheDetector

detector = CatastropheDetector(threshold=70)

result = detector.analyze_change(
    before_code="... your code before ...",
    after_code="... your code after ...",
    language="c",  # or python, java, etc.
)

if result.is_catastrophic:
    print(f"🚨 Risk: {result.risk_score}/100")
    print(f"Issue: {result.summary}")
    print(f"Missing: {result.invariants_removed}")
```

## Next Steps

1. **Review the architecture**: `docs/ARCHITECTURE.md`
2. **Setup for development**: `SETUP.md`
3. **Explore training data**: `data/training/catastrophes.json`
4. **Add new catastrophes**: `/Users/jonhays/DarkSeer-v3/data/catastrophes/`

## Troubleshooting

### "ArchIdx not available"

ArchIdx needs to be linked. Either:

**Option A**: Use sibling directory (development)
```
/Users/jonhays/
├── ArchIdx/
└── DarkSeer/
```

**Option B**: Use submodule (production)
```bash
git submodule add <ARCHIDX_URL> archidx
git submodule update --init
```

### "Catastrophe data not found"

Ensure DarkSeer-v3 exists at `/Users/jonhays/DarkSeer-v3/` with catastrophe JSON files.

## Questions?

See full documentation in `docs/` or check the README.

