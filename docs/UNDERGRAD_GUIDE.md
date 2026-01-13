# DarkSeer: The Complete Undergrad Guide

## What Are We Building?

**One sentence:** A system that catches code changes that could kill people or cost billions, *before* they ship.

**The problem:** Every year, tiny code changes cause massive disasters:
- **Heartbleed (2014):** One missing bounds check leaked passwords from 66% of the internet. Cost: $500M+
- **Therac-25 (1986):** A race condition in medical software killed 6 patients
- **Knight Capital (2012):** A deployment bug lost $440M in 45 minutes
- **Log4Shell (2021):** One line let attackers take over any Java app. Cost: $10B+

**The insight:** These bugs share a pattern—they're *subtle architectural flaws* that:
1. Look harmless to humans
2. Pass all existing tests
3. Have massive "blast radius" (affect many systems)
4. Often exist for YEARS before discovery

**Our solution:** Train an AI to recognize these patterns by studying real catastrophes.

---

## The Two Projects

### ArchIdx (Architectural Index)
**What:** The "brain" that understands code structure
**Analogy:** Like how your brain understands language grammar, ArchIdx understands code grammar

### DarkSeer  
**What:** The "application" that uses ArchIdx to find dangerous changes
**Analogy:** ArchIdx is like knowing English; DarkSeer is like being a proofreader who spots dangerous typos

---

## How Does It Work? (The Pipeline)

### Step 1: Parse the Code (Tree-sitter)

**What happens:** Turn code text into a structured tree

```
Code:                          Tree:
                              
int add(int a, int b) {       function_definition
    return a + b;         ├── name: "add"
}                         ├── parameters: [a, b]
                          └── body: return_statement
                                   └── binary_expression: a + b
```

**Why:** Computers can't understand raw text. The tree lets us analyze structure.

**Tool:** Tree-sitter (a fast parser that works for 40+ languages)

---

### Step 2: Extract Symbols and Relationships (ArchPacket)

**What happens:** Find all the "things" in code and how they connect

```python
# Symbols (the nouns):
- Functions: add(), multiply(), calculate()
- Variables: total, count, user_input
- Classes: Calculator, User, Database

# Edges (the verbs/relationships):
- add() CALLS multiply()
- calculate() READS user_input
- Database CONTAINS users
```

**Why:** Bugs often happen at *boundaries*—where one piece of code talks to another.

**Output:** An "ArchPacket" containing:
```python
ArchPacket(
    symbols=[...],      # All functions, variables, classes
    edges=[...],        # How they connect (calls, reads, writes)
    evidence=[...],     # Safety patterns we found (more on this below)
)
```

---

### Step 3: Detect Safety Patterns (Invariants)

**What's an invariant?** A safety rule that should ALWAYS be true.

**Examples:**
```c
// INVARIANT: "bounds_checked"
// Before accessing array[i], check that i < array.length

if (i < length) {        // ✅ Invariant present
    data = array[i];
}

data = array[i];         // ❌ Invariant MISSING - potential crash!
```

```c
// INVARIANT: "null_checked"  
// Before using a pointer, check it's not NULL

if (ptr != NULL) {       // ✅ Invariant present
    use(ptr);
}

use(ptr);                // ❌ Invariant MISSING - potential crash!
```

**Why this matters:** Heartbleed was literally a missing bounds check. If we can detect "this code SHOULD have a bounds check but DOESN'T", we catch Heartbleed-class bugs.

**We detect 30+ invariant types:**
- `bounds_checked` - array access protected
- `null_checked` - pointer validated
- `mutex_protected` - concurrent access safe
- `input_sanitized` - user input cleaned
- `overflow_checked` - integer math safe
- ... and many more

---

### Step 4: Build the Architectural Map (ArchSchematic)

**What happens:** Group symbols into logical "components" and map trust boundaries

```
┌─────────────────────────────────────────────────┐
│                    SYSTEM                        │
│  ┌──────────────┐      ┌──────────────┐         │
│  │   UNTRUSTED  │      │   TRUSTED    │         │
│  │              │      │              │         │
│  │  user_input ─┼──────┼─► validate() │         │
│  │  http_request│      │   database   │         │
│  │              │      │   encrypt()  │         │
│  └──────────────┘      └──────────────┘         │
│        ▲                                         │
│        │ TRUST BOUNDARY                          │
│        │ (data must be validated here!)          │
└─────────────────────────────────────────────────┘
```

**Why:** Many catastrophes happen when untrusted data crosses into trusted zones WITHOUT validation.

**Key insight:** Log4Shell happened because user-controlled log messages (untrusted) triggered JNDI lookups (trusted operation) without validation.

---

### Step 5: Compare Before/After (ArchDelta)

**What happens:** When code changes, compute what's different architecturally

```python
ArchDelta(
    invariants_removed=[           # 🚨 DANGER: Safety removed!
        "bounds_checked on line 47"
    ],
    invariants_added=[             # ✅ GOOD: Safety added
        "null_checked on line 52"
    ],
    trust_boundaries_crossed=[     # ⚠️ WARNING: New trust flow
        "user_input now reaches database"
    ],
    components_affected=[          # 📊 Blast radius
        "auth_module", "user_service", "api_gateway"
    ]
)
```

**This is the magic:** Instead of asking "is this code buggy?", we ask "did this change make the architecture LESS safe?"

---

### Step 6: Score the Risk (The Encoder)

**What happens:** A neural network scores how "catastrophic" a change looks

```
Input: ArchDelta (the change)
       ├── Removed 1 bounds check
       ├── Affects 3 components  
       └── Crosses trust boundary

Output: Risk Score
        ├── 0.92 catastrophic probability
        └── Explanation: "Removing bounds check in network-facing 
            code with large blast radius matches Heartbleed pattern"
```

**How we train it:**
1. Feed it REAL catastrophes (Heartbleed, Log4Shell, etc.) → label: CATASTROPHIC
2. Feed it safe commits from same codebase → label: SAFE
3. It learns the difference

---

## The Training Data Strategy

### The Problem with Training Data

**Challenge:** Catastrophes are RARE. For every Heartbleed, there are millions of safe commits.

**Naive approach:** Train on 50% catastrophic, 50% safe
**Problem:** Model learns "everything looks equally dangerous" (useless)

### Our Solution: Component-Aware Sampling

**Key insight:** Not all safe commits are equally informative. The best "hard negatives" are safe commits that:
1. Touch the SAME code component as a catastrophe
2. Happen around the SAME time
3. Look similar but are actually safe

```
For Heartbleed (OpenSSL, ssl/d1_both.c):

CATASTROPHIC (1 example):
  - The actual Heartbleed commit

SAFE_BEFORE (20 examples):
  - Safe commits to ssl/d1_both.c BEFORE Heartbleed was introduced
  
SAFE_AFTER (20 examples):  
  - Safe commits to ssl/d1_both.c AFTER Heartbleed was fixed

SAFE_DURING (10 examples):
  - Safe commits to DIFFERENT OpenSSL files during vulnerable period

SAFE_RANDOM (10 examples):
  - Safe commits from completely different repos
```

**Why this works:** The model learns "these similar-looking changes are safe, but THIS specific pattern is catastrophic"

---

## K-Hop Component Analysis

### What's a "Component"?

**Definition:** All code within K hops of the changed code in the call graph

```
K=0: Just the changed function
K=1: Changed function + everything it calls + everything that calls it
K=2: K=1 + one more level
K=3: K=2 + one more level (our default)
```

**Example (K=2):**
```
                    main()
                      │
                      ▼
                   process()
                      │
        ┌─────────────┼─────────────┐
        ▼             ▼             ▼
    validate()    transform()    save()
        │             │             │
        ▼             ▼             ▼
    check_len()   parse()      write_db()
    
If transform() changes, K=2 component includes:
- transform() (K=0)
- process(), parse() (K=1)  
- main(), validate(), save(), check_len(), write_db() (K=2)
```

**Why K=3:** Catastrophes often have "action at a distance"—the bug is in function A, but the damage happens in function C.

---

## The Novel Insights (What Makes This Different)

### 1. Architecture-First, Not Pattern-First

**Traditional:** "Find code that looks like known bug patterns"
**Problem:** Can't find NEW types of bugs

**Our approach:** "Find changes that make the ARCHITECTURE less safe"
**Advantage:** Catches novel bugs that don't match any pattern

### 2. Invariant-Aware Analysis

**Traditional:** Treat all code equally
**Our approach:** Explicitly track safety invariants

This means we can say: "You removed the ONLY bounds check protecting this buffer" rather than just "this code accesses a buffer"

### 3. Trust Zone Modeling

**Traditional:** Analyze code in isolation
**Our approach:** Track where data comes from and where it flows

This catches bugs like Log4Shell where the FLOW (user input → dangerous operation) is the problem, not any single line.

### 4. Few-Shot Learning from Real Catastrophes

**Traditional:** Need millions of labeled examples
**Our approach:** Learn from ~50 real catastrophes + smart sampling

This works because we're learning ARCHITECTURAL patterns, not superficial code patterns.

---

## How to Explain It

### To Engineers (30 seconds)
"We built a tool that analyzes code changes for architectural red flags—removed safety checks, new trust boundary crossings, large blast radius. It's trained on real catastrophes like Heartbleed and Log4Shell."

### To Executives (30 seconds)
"Every year, small code changes cause billion-dollar disasters. Our AI catches these before they ship by learning from past catastrophes. Think of it as a senior security engineer that's studied every major outage in history."

### To Investors (30 seconds)
"We're building the last line of defense against catastrophic code changes. Our moat is unique training data—we've catalogued every major software disaster and built AI that recognizes those patterns. The market is every company that ships software."

### To Academics (30 seconds)
"We use hierarchical graph neural networks with invariant-aware attention to model code changes as architectural state transitions. The key insight is framing bug detection as anomaly detection in a structured latent space of architectural invariants."

---

## The Code Structure

```
DarkSeer/                      # The application
├── src/
│   ├── detector/              # Risk scoring and alerting
│   │   ├── catastrophe_detector.py
│   │   └── risk_scorer.py
│   └── training/              # Data collection and model training
│       ├── component_aware_collector.py  # Smart sampling
│       └── dataset.py                    # PyTorch dataset
├── scripts/
│   ├── collect_component_aware_data.py   # Gather training data
│   └── train.py                          # Train the model
└── data/
    └── training/
        └── catastrophes.json             # Real catastrophe examples

ArchIdx/                       # The "brain" (submodule)
├── src/
│   ├── arch_packet/           # Code parsing and analysis
│   │   ├── generator.py       # Parse code → ArchPacket
│   │   ├── ast_invariant_detector.py  # Find safety patterns
│   │   └── subgraph_extractor.py      # K-hop analysis
│   ├── arch_schematic/        # Architectural modeling
│   │   └── normalizer.py      # Build component map
│   └── arch_delta/            # Change analysis
│       └── generator.py       # Compare before/after
```

---

## Key Terms Glossary

| Term | Plain English |
|------|---------------|
| **Invariant** | A safety rule that should always be true |
| **Trust boundary** | The line between "safe" and "unsafe" data |
| **Blast radius** | How many parts of the system a bug affects |
| **K-hop** | How many function calls away from changed code |
| **ArchPacket** | Our representation of parsed code |
| **ArchSchematic** | Our map of code architecture |
| **ArchDelta** | The architectural difference between two versions |
| **Component** | A group of related functions/classes |
| **Few-shot learning** | Learning from very few examples |
| **Hard negative** | A safe example that looks similar to a catastrophe |

---

## What's Next?

1. **Tonight:** Collecting training data (running in background)
2. **Tomorrow:** Review collected data, train the model
3. **This week:** Test on held-out catastrophes
4. **Next week:** Integrate with a real repo (maybe Linux kernel?)
5. **Future:** CI/CD integration, pitch deck, funding

---

## Questions You Might Have

**Q: Why not just use existing static analysis tools?**
A: They find "known patterns" (SQL injection, buffer overflow). We find "architectural degradation"—novel bugs that don't match any pattern.

**Q: How is this different from GitHub Copilot / ChatGPT?**
A: Those generate code. We analyze CHANGES for catastrophic potential. Different problem, complementary solutions.

**Q: What if the model has false positives?**
A: Better to review 10 flagged PRs and find 1 real issue than to miss the next Heartbleed. We optimize for recall over precision.

**Q: Can attackers fool it?**
A: Potentially, but we're not doing pattern matching. To fool it, you'd need to make a catastrophic change that DOESN'T degrade the architecture—which is hard by definition.

**Q: Why not just hire more security engineers?**
A: There aren't enough. And even experts miss subtle bugs (Heartbleed existed for 2 years before discovery). AI scales.

---

*Last updated: January 2026*
*Questions? The code is the documentation—read the docstrings!*

