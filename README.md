# DarkSeer

**Catastrophic Code Change Detection** — Powered by ArchIdx

DarkSeer detects subtle, catastrophic code changes before they ship to production. It understands code architecture, not just syntax patterns, enabling it to catch vulnerabilities that humans miss for years.

## The Problem

Some of the worst software disasters came from seemingly innocent changes:

| Disaster | Root Cause | Latency | Impact |
|----------|------------|---------|--------|
| **Heartbleed** | Missing bounds check | 2 years | $500M+, 66% of HTTPS servers |
| **Log4Shell** | JNDI lookup in logging | 8 years | $10B+, virtually every Java app |
| **Therac-25** | Race condition | 2 years | 6 deaths |
| **Boeing 737 MAX** | Single sensor, no redundancy | 2 years | 346 deaths |

These weren't obvious bugs. They were **architectural violations** — missing invariants that should have existed but didn't.

## How DarkSeer Works

DarkSeer uses **ArchIdx** (Architectural Index) to understand code at multiple scales:

```
Code Change → ArchIdx Analysis → Risk Assessment → Explanation
                    │
                    ├── Invariants present/missing
                    ├── Trust boundaries crossed
                    ├── Data flow analysis
                    └── Blast radius estimation
```

### Key Capabilities

1. **Invariant Detection** — Identifies safety invariants (bounds checks, null checks, auth, etc.)
2. **Change Analysis** — Compares before/after to find invariants added/removed
3. **Risk Scoring** — Quantifies catastrophic potential (0-100)
4. **Plain English Explanation** — Describes the risk in terms anyone can understand

## Quick Start

```bash
# Clone with ArchIdx submodule
git clone --recursive https://github.com/YOUR_ORG/DarkSeer.git
cd DarkSeer

# Install dependencies
pip install -r requirements.txt

# Run the Heartbleed demo
python scripts/demo_heartbleed.py
```

## Project Structure

```
DarkSeer/
├── archidx/              # ArchIdx submodule (foundation)
├── src/
│   ├── detector/         # Catastrophe detection logic
│   ├── training/         # Training data and scripts
│   └── integrations/     # CI/CD, GitHub, etc.
├── data/
│   └── catastrophes/     # Real-world catastrophe examples
├── scripts/
│   ├── demo_heartbleed.py
│   ├── train.py
│   └── scan_pr.py
└── docs/
    ├── ARCHITECTURE.md
    └── PITCH_DECK.md
```

## Proven Results

DarkSeer correctly detects real-world catastrophic vulnerabilities:

| CVE | Vulnerability | Detection |
|-----|---------------|-----------|
| CVE-2014-0160 | Heartbleed | ✅ Found 8 missing bounds checks |
| CVE-2014-0195 | OpenSSL DTLS Overflow | ✅ Found missing bounds check |
| CVE-2015-1789 | OpenSSL X509 Parsing | ✅ Found 2 missing bounds checks |

## Philosophy

> "The goal isn't to find all bugs. It's to find the bugs that cause catastrophes — the subtle architectural violations that slip past human review and automated testing."

DarkSeer is designed to be a **Calamity Counter** — a superhero tool for public safety.

## License

[To be determined]

## Acknowledgments

Built on [ArchIdx](https://github.com/YOUR_ORG/ArchIdx), a novel architectural understanding engine.

