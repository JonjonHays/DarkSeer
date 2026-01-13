# DarkSeer Quick Reference Card

## What Is It?
AI that catches catastrophic code changes by analyzing architecture, not patterns.

## The Stack
```
┌─────────────────────────────────────────────┐
│              DarkSeer (App)                 │
│  • Catastrophe detection                    │
│  • Risk scoring                             │
│  • Training pipeline                        │
├─────────────────────────────────────────────┤
│              ArchIdx (Brain)                │
│  • Code parsing (Tree-sitter)               │
│  • Invariant detection (30+ types)          │
│  • Architecture modeling                    │
│  • K-hop component analysis                 │
└─────────────────────────────────────────────┘
```

## Key Concepts

| Concept | What It Means | Why It Matters |
|---------|---------------|----------------|
| **Invariant** | Safety rule (bounds check, null check) | Removing one = danger |
| **Trust boundary** | Safe ↔ unsafe data line | Crossing without validation = danger |
| **Blast radius** | How many components affected | Bigger = more catastrophic |
| **K-hop** | Functions within K calls | K=3 captures "action at a distance" |

## The Pipeline
```
Code Change → Parse → Extract Symbols → Detect Invariants → 
Build Architecture → Compare Before/After → Score Risk
```

## Training Data Strategy
```
Per catastrophe (e.g., Heartbleed):
  1 CATASTROPHIC   - The actual bad commit
 20 SAFE_BEFORE    - Same component, pre-bug
 20 SAFE_AFTER     - Same component, post-fix
 10 SAFE_DURING    - Different component, same time
 10 SAFE_RANDOM    - Different repo entirely
```

## 30-Second Explanations

**To Engineers:** "Analyzes code changes for removed safety checks, trust violations, and patterns matching real disasters."

**To Execs:** "AI that catches billion-dollar bugs before they ship, trained on every major software disaster."

**To Investors:** "We're the last line of defense. Every company that ships code is a customer."

## Commands

```bash
# Collect training data
python scripts/collect_component_aware_data.py

# Train the model
python scripts/train.py

# Analyze a change
python -c "from src.detector import analyze; analyze('before.c', 'after.c')"
```

## Files That Matter

| File | Purpose |
|------|---------|
| `data/training/catastrophes.json` | 33 real catastrophes with code |
| `src/training/component_aware_collector.py` | Smart training data sampling |
| `ArchIdx/src/arch_packet/generator.py` | Code → structured representation |
| `ArchIdx/src/arch_packet/ast_invariant_detector.py` | Find safety patterns |

## Validated Detections
- ✅ Heartbleed (CVE-2014-0160)
- ✅ PwnKit (CVE-2021-4034)
- ✅ Log4Shell (CVE-2021-44228)
- ✅ Baron Samedit (CVE-2021-3156)

## The Insight
Traditional tools: "Does this code match a bug pattern?"
DarkSeer: "Did this change make the architecture LESS safe?"

---
*Print this. Tape it to your wall.*

