"""
DarkSeer Catastrophe Detector

The core detection engine that uses ArchIdx to identify catastrophic code changes.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add ArchIdx to path (submodule)
ARCHIDX_PATH = Path(__file__).parent.parent.parent / "archidx" / "src"
if ARCHIDX_PATH.exists():
    sys.path.insert(0, str(ARCHIDX_PATH))
else:
    # Fallback to sibling directory during development
    ARCHIDX_PATH = Path(__file__).parent.parent.parent.parent / "ArchIdx" / "src"
    if ARCHIDX_PATH.exists():
        sys.path.insert(0, str(ARCHIDX_PATH))

try:
    from arch_packet.generator import ArchPacketGenerator
    from arch_packet.ast_invariant_detector import ASTInvariantDetector, DetectedInvariant
    ARCHIDX_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  ArchIdx not available: {e}")
    print(f"   Looked in: {ARCHIDX_PATH}")
    ARCHIDX_AVAILABLE = False


@dataclass
class DetectionResult:
    """Result of catastrophe detection."""
    risk_score: int  # 0-100
    is_catastrophic: bool  # risk_score >= threshold
    
    # What was found
    invariants_before: List[Dict]
    invariants_after: List[Dict]
    invariants_added: List[Dict]
    invariants_removed: List[Dict]
    
    # Dangerous operations
    dangerous_ops: List[str]
    
    # Explanation
    summary: str
    detailed_explanation: str
    
    # Metadata
    files_analyzed: List[str]
    language: str


class CatastropheDetector:
    """
    Detects catastrophic code changes using ArchIdx architectural analysis.
    
    Usage:
        detector = CatastropheDetector()
        result = detector.analyze_change(before_code, after_code, language="c")
        
        if result.is_catastrophic:
            print(f"🚨 CRITICAL: {result.summary}")
            print(f"Risk Score: {result.risk_score}/100")
    """
    
    def __init__(self, threshold: int = 70):
        """
        Initialize the detector.
        
        Args:
            threshold: Risk score threshold for catastrophic classification (0-100)
        """
        if not ARCHIDX_AVAILABLE:
            raise RuntimeError("ArchIdx not available. Ensure it's installed or linked.")
        
        self.threshold = threshold
        self.invariant_detector = ASTInvariantDetector()
        self.packet_generator = ArchPacketGenerator()
        
        # Dangerous operations that need protection
        self.dangerous_ops = {
            'c': ['memcpy', 'memmove', 'memset', 'strcpy', 'strncpy', 'sprintf', 
                  'snprintf', 'read', 'write', 'recv', 'send', 'malloc', 'free'],
            'python': ['eval', 'exec', 'pickle.loads', 'yaml.load', 'subprocess.call',
                       'os.system', '__import__'],
            'java': ['Runtime.exec', 'ProcessBuilder', 'ObjectInputStream', 
                     'XMLDecoder', 'ScriptEngine.eval'],
            'javascript': ['eval', 'Function', 'innerHTML', 'document.write',
                          'child_process.exec'],
        }
    
    def analyze_change(
        self,
        before_code: str,
        after_code: str,
        language: str,
        file_path: str = "unknown",
    ) -> DetectionResult:
        """
        Analyze a code change for catastrophic potential.
        
        Args:
            before_code: Code before the change
            after_code: Code after the change
            language: Programming language (c, python, java, etc.)
            file_path: Path to the file (for reporting)
            
        Returns:
            DetectionResult with risk assessment and explanation
        """
        # Detect invariants in both versions
        before_invs = self.invariant_detector.detect_invariants(before_code, language, file_path)
        after_invs = self.invariant_detector.detect_invariants(after_code, language, file_path)
        
        # Compare
        comparison = self.invariant_detector.compare_invariants(
            before_code, after_code, language, file_path
        )
        
        # Find dangerous operations in the code
        dangerous = self._find_dangerous_ops(before_code, after_code, language)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(
            before_invs=before_invs,
            after_invs=after_invs,
            added=comparison['added'],
            removed=comparison['removed'],
            dangerous_ops=dangerous,
        )
        
        # Generate explanation
        summary, detailed = self._generate_explanation(
            before_invs=before_invs,
            after_invs=after_invs,
            added=comparison['added'],
            removed=comparison['removed'],
            dangerous_ops=dangerous,
            risk_score=risk_score,
        )
        
        return DetectionResult(
            risk_score=risk_score,
            is_catastrophic=risk_score >= self.threshold,
            invariants_before=[self._inv_to_dict(i) for i in before_invs],
            invariants_after=[self._inv_to_dict(i) for i in after_invs],
            invariants_added=[self._inv_to_dict(i) for i in comparison['added']],
            invariants_removed=[self._inv_to_dict(i) for i in comparison['removed']],
            dangerous_ops=dangerous,
            summary=summary,
            detailed_explanation=detailed,
            files_analyzed=[file_path],
            language=language,
        )
    
    def analyze_diff(
        self,
        diff_text: str,
        language: str,
    ) -> DetectionResult:
        """
        Analyze a unified diff for catastrophic potential.
        
        Args:
            diff_text: Unified diff text
            language: Programming language
            
        Returns:
            DetectionResult
        """
        # Parse diff into before/after
        added_lines = []
        removed_lines = []
        
        for line in diff_text.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                added_lines.append(line[1:])
            elif line.startswith('-') and not line.startswith('---'):
                removed_lines.append(line[1:])
        
        before_code = '\n'.join(removed_lines)
        after_code = '\n'.join(added_lines)
        
        return self.analyze_change(before_code, after_code, language, "diff")
    
    def _find_dangerous_ops(
        self,
        before_code: str,
        after_code: str,
        language: str,
    ) -> List[str]:
        """Find dangerous operations in the code."""
        ops = self.dangerous_ops.get(language, [])
        found = []
        
        combined_code = before_code + after_code
        
        for op in ops:
            if op in combined_code:
                found.append(op)
        
        return found
    
    def _calculate_risk_score(
        self,
        before_invs: List[DetectedInvariant],
        after_invs: List[DetectedInvariant],
        added: List[DetectedInvariant],
        removed: List[DetectedInvariant],
        dangerous_ops: List[str],
    ) -> int:
        """
        Calculate risk score (0-100).
        
        Factors:
        - Dangerous operations present
        - Protective invariants missing
        - Invariants removed by change
        - Severity of affected invariants
        """
        score = 0
        
        # Dangerous operations present (+30)
        if dangerous_ops:
            score += min(30, len(dangerous_ops) * 10)
        
        # No protective invariants in before code (+40)
        protective_types = {'bounds_checked', 'null_checked', 'input_validated'}
        before_has_protection = any(
            i.invariant_type.value in protective_types for i in before_invs
        )
        
        if dangerous_ops and not before_has_protection:
            score += 40
        
        # Invariants removed (very bad) (+20)
        if removed:
            score += min(20, len(removed) * 10)
        
        # Change adds protection (indicates it was missing) (+10)
        protection_added = any(
            i.invariant_type.value in protective_types for i in added
        )
        if protection_added:
            score += 10
        
        return min(100, score)
    
    def _generate_explanation(
        self,
        before_invs: List[DetectedInvariant],
        after_invs: List[DetectedInvariant],
        added: List[DetectedInvariant],
        removed: List[DetectedInvariant],
        dangerous_ops: List[str],
        risk_score: int,
    ) -> Tuple[str, str]:
        """Generate human-readable explanation."""
        
        # Summary
        if risk_score >= 90:
            summary = "CRITICAL: High probability of catastrophic vulnerability"
        elif risk_score >= 70:
            summary = "HIGH RISK: Significant security/safety concern"
        elif risk_score >= 50:
            summary = "MEDIUM RISK: Potential issue, review recommended"
        else:
            summary = "LOW RISK: No obvious catastrophic patterns detected"
        
        # Detailed explanation
        parts = []
        
        if dangerous_ops:
            parts.append(f"Dangerous operations found: {', '.join(dangerous_ops)}")
        
        if not before_invs and dangerous_ops:
            parts.append(
                "⚠️  No protective invariants (bounds checks, validation) detected "
                "in code with dangerous operations."
            )
        
        if removed:
            types_removed = set(i.invariant_type.value for i in removed)
            parts.append(f"Invariants REMOVED: {', '.join(types_removed)}")
        
        if added:
            types_added = set(i.invariant_type.value for i in added)
            parts.append(
                f"Invariants ADDED by this change: {', '.join(types_added)}. "
                "This suggests they were missing before."
            )
        
        detailed = "\n".join(parts) if parts else "No specific issues identified."
        
        return summary, detailed
    
    def _inv_to_dict(self, inv: DetectedInvariant) -> Dict:
        """Convert invariant to dictionary."""
        return {
            "type": inv.invariant_type.value,
            "severity": inv.severity.value,
            "description": inv.description,
            "line_start": inv.line_start,
            "line_end": inv.line_end,
            "protected_operation": inv.protected_operation,
        }

