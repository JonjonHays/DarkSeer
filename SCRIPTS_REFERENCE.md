# DarkSeer Scripts Reference

Quick guide to all available scripts and what they do.

---

## 📊 Data Collection

### `scripts/collect_training_data.py`
**What**: Loads 32 catastrophes from DarkSeer-v3 JSON files  
**Output**: `data/training/catastrophes.json`  
**Runtime**: ~1 second  
**Usage**:
```bash
python scripts/collect_training_data.py
```

### `scripts/collect_component_aware_data.py` ⭐ NEW
**What**: Intelligently samples safe commits using K=3 hop component analysis  
**Output**: `data/training/component_aware_dataset.json`  
**Runtime**: ~5-10 minutes (git operations in temp dirs)  
**Details**:
- 20 SAFE_BEFORE per catastrophe (same component, pre-vuln)
- 20 SAFE_AFTER per catastrophe (same component, post-fix)
- 10 SAFE_DURING per catastrophe (different component)
- 10 SAFE_RANDOM per catastrophe (different repos)
- Total: ~2,000 examples from 32 catastrophes

**Usage**:
```bash
python scripts/collect_component_aware_data.py
```

---

## 📈 Analysis

### `scripts/analyze_dataset.py`
**What**: Analyzes the 32 catastrophes to identify needed invariants  
**Output**: Console report with priorities  
**Key Info**:
- Root cause → invariant mapping
- Missing invariant detectors
- Priority recommendations
- Language/category distribution

**Usage**:
```bash
python scripts/analyze_dataset.py
```

**Output**:
```
Root Causes → Invariants:
  6x bounds_checked ✅ EXISTS
  3x deserialization_safe ❌ MISSING
  ...

Priority Recommendations:
  1. Concurrency Safety (death-causing)
  2. Input Validation (most common)
  ...
```

---

## 🎓 Training

### `scripts/train.py`
**What**: Trains ArchIdx encoder on catastrophe data  
**Input**: `data/training/catastrophes.json` (or component_aware_dataset.json)  
**Output**: `models/catastrophe_detector.pth`, `models/training_history.json`  
**Runtime**: ~1-2 hours (depends on dataset size)  
**Details**:
- Binary classification (catastrophic vs. safe)
- Severity regression (0.0-1.0)
- 80/20 train/val split
- 50 epochs with early stopping

**Usage**:
```bash
python scripts/train.py
```

**Output**:
```
Epoch 1/50
  Train Loss: 0.6432, Acc: 0.7200
  Val Loss: 0.5821, Acc: 0.7500
  ✅ Saved best model

...

Best validation accuracy: 0.8750
Model saved to: models/catastrophe_detector.pth
```

---

## 🎬 Demos

### `scripts/demo_heartbleed.py`
**What**: Demonstrates DarkSeer detecting Heartbleed  
**Runtime**: <1 second  
**Purpose**: Quick validation that the system works

**Usage**:
```bash
python scripts/demo_heartbleed.py
```

**Output**:
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
  ⚠️  No protective invariants detected
  Invariants ADDED by fix: bounds_checked

✅ DarkSeer correctly identified Heartbleed as CATASTROPHIC
```

---

## 🧪 Testing (ArchIdx)

These scripts live in `/Users/jonhays/ArchIdx/scripts/`:

### `demo_heartbleed.py`
Low-level ArchIdx demo (shows invariant detection details)

### `test_real_catastrophes.py`
Tests ArchIdx on 5 real CVEs from git history

**Usage**:
```bash
cd /Users/jonhays/ArchIdx
python scripts/test_real_catastrophes.py
```

**Output**:
```
Heartbleed: ✅ DETECTED (3 bounds checks missing)
OpenSSL DTLS Overflow: ✅ DETECTED
OpenSSL X509 Parsing: ✅ DETECTED
...
```

---

## 📋 Workflow

### Initial Setup
```bash
# 1. Collect basic catastrophe data
cd /Users/jonhays/DarkSeer
python scripts/collect_training_data.py

# 2. Analyze to understand gaps
python scripts/analyze_dataset.py

# 3. Quick validation demo
python scripts/demo_heartbleed.py
```

### Full Training Pipeline
```bash
# 1. Collect component-aware data (~5-10 min)
python scripts/collect_component_aware_data.py

# 2. Train model (~1-2 hours)
python scripts/train.py

# 3. Validate (TODO: create validation script)
python scripts/validate.py
```

### Testing New Detectors
```bash
# Test on real CVEs
cd /Users/jonhays/ArchIdx
python scripts/test_real_catastrophes.py
```

---

## 🔍 Script Details

| Script | Category | Runtime | Git Ops | Temp Dirs |
|--------|----------|---------|---------|-----------|
| `collect_training_data.py` | Data | ~1s | No | No |
| `collect_component_aware_data.py` | Data | ~5-10min | Yes | Yes ✅ |
| `analyze_dataset.py` | Analysis | ~1s | No | No |
| `train.py` | Training | ~1-2hr | No | No |
| `demo_heartbleed.py` | Demo | <1s | No | No |

**Note**: Only `collect_component_aware_data.py` does git operations, and ALL are in temp directories (nothing stored in repo).

---

## 📦 Output Files

```
DarkSeer/
└── data/training/
    ├── catastrophes.json                  # 32 catastrophes (basic)
    ├── component_aware_dataset.json       # ~2,000 examples (K=3)
    └── safe_commits_metadata.json         # Commit metadata

└── models/
    ├── catastrophe_detector.pth           # Trained model
    └── training_history.json              # Training metrics
```

---

## 🚀 Quick Start

```bash
# Complete workflow from scratch:
cd /Users/jonhays/DarkSeer

# Step 1: Get catastrophes (1 second)
python scripts/collect_training_data.py

# Step 2: See what we need (1 second)
python scripts/analyze_dataset.py

# Step 3: Validate core detection (1 second)
python scripts/demo_heartbleed.py

# Step 4: Collect component-aware data (5-10 minutes)
python scripts/collect_component_aware_data.py

# Step 5: Train the model (1-2 hours)
python scripts/train.py
```

**Total time**: ~1-2 hours for complete pipeline!

---

Ready to run! 🚀

