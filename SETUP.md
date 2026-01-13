# DarkSeer Setup Guide

## Project Structure

```
DarkSeer/                    # Main project (catastrophe detector)
├── archidx/                 # ArchIdx submodule (foundation)
├── src/
│   ├── detector/            # Detection engine
│   └── training/            # Training data collection
├── scripts/
│   ├── demo_heartbleed.py   # Quick demo
│   └── collect_training_data.py
└── data/
    └── training/            # Processed training data (NOT repos)
```

## Setup Instructions

### 1. Clone with ArchIdx Submodule

```bash
cd /Users/jonhays/DarkSeer
git init
git remote add origin <YOUR_GITHUB_URL>

# Add ArchIdx as submodule
# (First, push ArchIdx to GitHub)
cd /Users/jonhays/ArchIdx
git init
git add .
git commit -m "Initial ArchIdx commit"
git remote add origin <ARCHIDX_GITHUB_URL>
git push -u origin main

# Then add as submodule to DarkSeer
cd /Users/jonhays/DarkSeer
git submodule add <ARCHIDX_GITHUB_URL> archidx
git submodule update --init --recursive
```

### 2. Install Dependencies

```bash
# ArchIdx dependencies
pip install -r archidx/requirements.txt

# DarkSeer dependencies
pip install -r requirements.txt
```

### 3. Collect Training Data

```bash
# This uses the catastrophe data from DarkSeer-v3
# All git operations use temp directories - nothing stored in repo
python scripts/collect_training_data.py
```

### 4. Run Demo

```bash
python scripts/demo_heartbleed.py
```

## Development Workflow

### Working with ArchIdx

ArchIdx is a submodule, so changes there should be committed separately:

```bash
cd archidx/
git add .
git commit -m "Update ArchIdx"
git push

cd ..
git add archidx
git commit -m "Update ArchIdx submodule reference"
```

### Adding New Catastrophe Data

New catastrophe examples go in `/Users/jonhays/DarkSeer-v3/data/catastrophes/`.
They should follow the JSON format:

```json
{
  "id": "unique_id",
  "name": "Vulnerability Name",
  "cve": "CVE-2024-XXXXX",
  "vulnerable_code": {
    "code": "...",
    "file": "path/to/file.c",
    "commit_fixing": "abc123..."
  },
  "fix_code": {
    "code": "..."
  },
  "labels": {
    "category": "security",
    "root_cause": "buffer_overflow",
    "deaths": 0,
    "financial_loss_usd": 1000000
  }
}
```

### Testing Changes

```bash
# Quick test with demo
python scripts/demo_heartbleed.py

# Test data collection
python scripts/collect_training_data.py

# Run full test suite (TODO)
pytest tests/
```

## Important Notes

**⚠️ DO NOT commit:**
- Cloned repos (`data/repos/` is gitignored)
- Large model files (use Git LFS if needed)
- Temporary files

**✅ DO commit:**
- Processed training data (`data/training/catastrophes.json`)
- Source code
- Documentation
- Small example files

## Architecture

DarkSeer is a **use case** of ArchIdx:

```
┌─────────────────────────────────────┐
│          ArchIdx                     │
│  (Foundation for understanding       │
│   code architecture)                 │
└─────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────┐
│         DarkSeer                     │
│  (Catastrophe detection powered      │
│   by ArchIdx)                        │
└─────────────────────────────────────┘
```

This separation allows:
- ArchIdx to be used for other applications (code review, documentation, etc.)
- DarkSeer to focus on catastrophe detection
- Clean boundaries and reusability

