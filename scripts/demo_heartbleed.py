#!/usr/bin/env python3
"""
DarkSeer Heartbleed Demo

Demonstrates DarkSeer detecting the Heartbleed vulnerability using the catastrophe detector.
This is a simplified version that uses the DarkSeer API (which wraps ArchIdx).
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from detector.catastrophe_detector import CatastropheDetector


# The VULNERABLE Heartbleed code
VULNERABLE_CODE = '''
int dtls1_process_heartbeat(SSL *s) {
    unsigned char *p = &s->s3->rrec.data[0], *pl;
    unsigned short hbtype;
    unsigned int payload;
    
    hbtype = *p++;
    n2s(p, payload);  // payload = attacker-controlled value
    pl = p;
    
    unsigned char *buffer, *bp;
    buffer = OPENSSL_malloc(1 + 2 + payload + 16);
    bp = buffer;
    
    memcpy(bp, pl, payload);  // BUFFER OVER-READ - no bounds check!
    
    dtls1_write_bytes(s, TLS1_RT_HEARTBEAT, buffer, 3 + payload);
    OPENSSL_free(buffer);
    return 0;
}
'''

# The FIXED code
FIXED_CODE = '''
int dtls1_process_heartbeat(SSL *s) {
    unsigned char *p = &s->s3->rrec.data[0], *pl;
    unsigned short hbtype;
    unsigned int payload;
    
    if (s->s3->rrec.length < 3)  // FIX: Minimum length check
        return 0;
    
    hbtype = *p++;
    n2s(p, payload);
    
    if (1 + 2 + payload + 16 > s->s3->rrec.length)  // FIX: Bounds check!
        return 0;
    
    pl = p;
    
    unsigned char *buffer, *bp;
    buffer = OPENSSL_malloc(1 + 2 + payload + 16);
    bp = buffer;
    
    memcpy(bp, pl, payload);  // Now safe - payload validated
    
    dtls1_write_bytes(s, TLS1_RT_HEARTBEAT, buffer, 3 + payload);
    OPENSSL_free(buffer);
    return 0;
}
'''


def main():
    """Run Heartbleed detection demo."""
    
    print("=" * 70)
    print("  DarkSeer Heartbleed Detection Demo")
    print("  CVE-2014-0160")
    print("=" * 70)
    print()
    
    # Initialize detector
    detector = CatastropheDetector(threshold=70)
    
    print("🔍 Analyzing vulnerable code vs. fixed code...")
    print()
    
    # Analyze the change
    result = detector.analyze_change(
        before_code=VULNERABLE_CODE,
        after_code=FIXED_CODE,
        language="c",
        file_path="ssl/d1_both.c",
    )
    
    # Display results
    print("=" * 70)
    print("  RESULTS")
    print("=" * 70)
    print()
    
    print(f"Risk Score: {result.risk_score}/100")
    print(f"Catastrophic: {'YES' if result.is_catastrophic else 'NO'}")
    print()
    
    print("Summary:")
    print(f"  {result.summary}")
    print()
    
    print("Details:")
    for line in result.detailed_explanation.split('\n'):
        print(f"  {line}")
    print()
    
    print(f"Invariants in vulnerable code: {len(result.invariants_before)}")
    for inv in result.invariants_before[:3]:
        print(f"  • {inv['type']}")
    
    print()
    print(f"Invariants in fixed code: {len(result.invariants_after)}")
    for inv in result.invariants_after[:5]:
        print(f"  • {inv['type']} (protects: {inv.get('protected_operation', 'N/A')})")
    
    print()
    print(f"Invariants ADDED by fix: {len(result.invariants_added)}")
    for inv in result.invariants_added:
        print(f"  ✅ {inv['type']}")
    
    print()
    print(f"Dangerous operations detected: {', '.join(result.dangerous_ops)}")
    
    print()
    print("=" * 70)
    
    if result.is_catastrophic:
        print("  ✅ DarkSeer correctly identified Heartbleed as CATASTROPHIC")
    else:
        print("  ❌ Failed to detect catastrophic nature")
    
    print("=" * 70)


if __name__ == "__main__":
    main()

