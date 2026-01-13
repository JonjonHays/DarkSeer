# DarkSeer Architecture

## Overview

DarkSeer is a **catastrophe detection system** built on top of **ArchIdx**, a novel architectural understanding engine.

```
┌───────────────────────────────────────────────────────────────┐
│                         DarkSeer                               │
│              (Application Layer)                               │
│                                                                │
│  ┌─────────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │  Catastrophe    │───▶│ Risk         │───▶│ Explainer    │ │
│  │  Detector       │    │ Scorer       │    │              │ │
│  └─────────────────┘    └──────────────┘    └──────────────┘ │
│           │                                                    │
└───────────┼────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────┐
│                        ArchIdx                                 │
│              (Foundation Layer)                                │
│                                                                │
│  ┌──────────────┐  ┌────────────┐  ┌─────────────┐  ┌──────┐ │
│  │ ArchPacket   │─▶│ ArchSchema │─▶│ ArchDelta   │─▶│Encode│ │
│  │ Generator    │  │ Normalizer │  │ Generator   │  │  r   │ │
│  └──────────────┘  └────────────┘  └─────────────┘  └──────┘ │
│         │                                                      │
│         ├── AST Invariant Detector                            │
│         ├── Tree-sitter Parser                                │
│         └── Multi-language Support                            │
└───────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Separation of Concerns

**ArchIdx** (Foundation):
- Understands code architecture at multiple scales
- Language-agnostic parsing and analysis
- Invariant detection (bounds checks, null checks, auth, etc.)
- Reusable for multiple applications

**DarkSeer** (Application):
- Focuses on catastrophe detection specifically
- Adds risk scoring and explanation
- Training data collection
- CI/CD integrations

**Why this split?**
- ArchIdx can power other products (code review, documentation, etc.)
- DarkSeer gets a clean, focused purpose
- Broader patent/IP scope for ArchIdx
- Better enterprise positioning

### 2. Invariant-Based Detection

Instead of pattern matching for specific vulnerabilities, DarkSeer detects **missing architectural invariants**:

| Invariant | What It Protects |
|-----------|------------------|
| `bounds_checked` | Buffer overflows, over-reads |
| `null_checked` | Null pointer dereferences |
| `input_validated` | Injection attacks |
| `authenticated` | Unauthorized access |
| `authorized` | Privilege escalation |
| `rate_limited` | DoS attacks |

**Key insight**: Heartbleed wasn't about detecting "Heartbleed" - it was about detecting that a bounds check was missing before a memory operation.

### 3. No Repos in Repo

All git operations use **temporary directories** that are automatically cleaned up:

```python
with tempfile.TemporaryDirectory(prefix="darkseer_") as temp_dir:
    # Clone, analyze, done
    # Temp dir automatically deleted
```

This keeps the repo clean and fast.

### 4. Real-World Training Data

33 documented catastrophes from history:
- Heartbleed, Log4Shell, Shellshock
- Therac-25, Boeing 737 MAX (death-causing)
- Knight Capital, Equifax (financial)
- Ariane 5, Mars Climate Orbiter (embedded)

Each has:
- Before/after code
- CVE/incident details
- Impact metrics (deaths, $ loss)
- Root cause analysis

## Data Flow

### Detection Flow

```
1. Code Change
   └─▶ ArchPacket Generator
       └─▶ Tree-sitter parsing
       └─▶ AST Invariant Detection
           └─▶ Compare before/after
               └─▶ Calculate risk score
                   └─▶ Generate explanation
```

### Training Flow

```
1. Catastrophe JSON files (DarkSeer-v3/data/catastrophes/)
   └─▶ Data Collector
       └─▶ Load code examples
       └─▶ Optional: fetch from git (temp dir)
           └─▶ Process and label
               └─▶ Save training dataset
                   └─▶ Train ArchIdx encoder
```

## Why This Works

### The Pattern

All catastrophic bugs share a pattern:

1. **Critical operation exists** (memory copy, authentication, control surface)
2. **Protective invariant should exist** (bounds check, null check, redundancy)
3. **Invariant is missing or removed** → Catastrophe

### Examples

| Disaster | Critical Operation | Missing Invariant |
|----------|-------------------|-------------------|
| **Heartbleed** | memcpy(user_length) | bounds_checked |
| **Therac-25** | Set beam power | race_condition_protected |
| **737 MAX** | Read AoA sensor | redundant_sensor_check |
| **Equifax** | Parse user input | input_validated |

DarkSeer detects these patterns **architecturally**, not through signatures.

## Extensibility

### Adding New Invariant Types

1. Add to `ast_invariant_detector.py`:
```python
def _detect_race_condition_protection(self, ...):
    # Look for mutexes, locks, atomic operations
    ...
```

2. Add scoring in `risk_scorer.py`:
```python
self.invariant_weights["race_condition_protected"] = 45
```

3. Works automatically in detection pipeline

### Adding New Languages

Tree-sitter supports 40+ languages out of the box:

```python
LANGUAGE_EXTENSIONS = {
    "rust": [".rs"],
    "kotlin": [".kt"],
    "swift": [".swift"],
    ...
}
```

## Future Directions

### Phase 1: Few-Shot Learning (Current)
- Train on 33 real catastrophes
- Learn what "missing invariant" looks like
- Validate on held-out examples

### Phase 2: GAN-Based Augmentation
- Generator: Create realistic code changes
- Discriminator: Is this a realistic dev commit?
- Critic: Does it violate invariants?
- Generate 1000s of synthetic examples

### Phase 3: Production Integration
- GitHub PR scanning
- CI/CD webhooks
- Real-time risk scoring
- Explanation UI

## Performance Goals

| Metric | Target | Current |
|--------|--------|---------|
| Detection on Heartbleed | >90/100 | 100/100 ✅ |
| False positive rate | <5% | TBD |
| Analysis time | <1s per commit | ~0.3s ✅ |
| Languages supported | 10+ | 8 ✅ |

## References

- ArchCodeBERT chat (inspiration for multi-scale encoding)
- DarkSeer-v3 (training data source)
- Real CVE fixes (validation data)

