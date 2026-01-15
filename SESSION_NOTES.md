# DarkSeer Session Notes
**Date:** 2026-01-14

## Current Status

### ✅ Working Components

1. **Surgical Fetch** (`src/training/surgical_fetch.py`)
   - Fetches commit windows around catastrophe fix commits
   - Uses blobless clones + on-demand blob fetching
   - Gets N ancestors via `git rev-list`
   - Gets M descendants via GitHub API
   - Tested on 3 CVEs: Heartbleed, PwnKit, Log4Shell

2. **Verified Catastrophes** (`data/verified_catastrophes.json`)
   - 3 entries with confirmed commit hashes
   - Ready for data collection

3. **Test Script** (`scripts/test_surgical_fetch.py`)
   - Validates surgical fetch on all verified catastrophes

### 📋 Next Steps

1. **Integrate surgical fetch into data collection pipeline**
2. **Expand verified catastrophes list** (more CVEs)
3. **Build training data** using component-aware sampling
4. **Train encoder** on real catastrophe data

### 🔧 Architecture Notes

- **Option A approach**: Simple ancestor/descendant fetching regardless of branch topology
- We care about the CODE change, not merge history
- K=3 hops for subgraph extraction
- Component-aware safe commit sampling (1000:1 ratio)

### 📁 Key Files

```
/Users/jonhays/DarkSeer/
├── src/
│   └── training/
│       ├── surgical_fetch.py    # ✅ Working
│       └── types.py             # Data types
├── scripts/
│   └── test_surgical_fetch.py   # ✅ Passing
└── data/
    └── verified_catastrophes.json  # 3 CVEs
```

### 🔗 Related Projects

- **ArchIdx** (`/Users/jonhays/ArchIdx`) - Architectural understanding layer (submodule)
- **DarkSeer-v3** (`/Users/jonhays/DarkSeer-v3`) - Previous iteration (reference only)
