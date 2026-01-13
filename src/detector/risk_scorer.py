"""
Risk Scorer for DarkSeer

Calculates risk scores based on multiple factors:
- Invariant violations
- Blast radius
- Domain (security vs safety-critical)
- Historical patterns
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class RiskCategory(str, Enum):
    """Categories of risk."""
    SECURITY = "security"           # Data breach, RCE, etc.
    SAFETY = "safety"               # Life-threatening
    FINANCIAL = "financial"         # Money loss
    AVAILABILITY = "availability"   # Service disruption
    DATA_INTEGRITY = "data"         # Data corruption


@dataclass
class RiskAssessment:
    """Detailed risk assessment."""
    score: int  # 0-100
    category: RiskCategory
    confidence: float  # 0.0-1.0
    
    factors: Dict[str, int]  # Factor name -> contribution to score
    mitigations: List[str]  # Suggested mitigations
    
    blast_radius: str  # "single_user", "organization", "internet_scale"
    reversibility: str  # "easy", "difficult", "impossible"


class RiskScorer:
    """
    Calculates risk scores with multiple dimensions.
    
    Scoring is based on:
    1. What invariants are violated
    2. What operations are affected
    3. Domain context
    4. Historical pattern matching
    """
    
    def __init__(self):
        # Invariant severity weights
        self.invariant_weights = {
            "bounds_checked": 40,      # Buffer overflows are critical
            "null_checked": 20,        # Null derefs can crash
            "input_validated": 35,     # Injection attacks
            "authenticated": 30,       # Auth bypass
            "authorized": 30,          # Authz bypass
            "encrypted": 25,           # Data exposure
            "rate_limited": 15,        # DoS potential
            "audit_logged": 10,        # Forensics
        }
        
        # Domain multipliers
        self.domain_multipliers = {
            "cryptography": 1.5,       # Crypto bugs are severe
            "authentication": 1.4,
            "medical": 2.0,            # Lives at stake
            "automotive": 2.0,
            "aviation": 2.0,
            "financial": 1.3,
            "infrastructure": 1.4,
            "general": 1.0,
        }
    
    def calculate(
        self,
        missing_invariants: List[str],
        dangerous_operations: List[str],
        domain: str = "general",
        code_context: Optional[str] = None,
    ) -> RiskAssessment:
        """
        Calculate comprehensive risk assessment.
        
        Args:
            missing_invariants: List of invariant types that are missing
            dangerous_operations: List of dangerous operations in code
            domain: Domain context (cryptography, medical, etc.)
            code_context: Additional code context for analysis
            
        Returns:
            RiskAssessment with detailed breakdown
        """
        factors = {}
        base_score = 0
        
        # Score for missing invariants
        for inv in missing_invariants:
            weight = self.invariant_weights.get(inv, 10)
            factors[f"missing_{inv}"] = weight
            base_score += weight
        
        # Score for dangerous operations
        if dangerous_operations:
            danger_score = min(30, len(dangerous_operations) * 10)
            factors["dangerous_operations"] = danger_score
            base_score += danger_score
        
        # Apply domain multiplier
        multiplier = self.domain_multipliers.get(domain, 1.0)
        final_score = min(100, int(base_score * multiplier))
        
        # Determine category
        if domain in ["medical", "automotive", "aviation"]:
            category = RiskCategory.SAFETY
        elif domain in ["financial"]:
            category = RiskCategory.FINANCIAL
        else:
            category = RiskCategory.SECURITY
        
        # Estimate blast radius
        if final_score >= 80:
            blast_radius = "internet_scale"
        elif final_score >= 50:
            blast_radius = "organization"
        else:
            blast_radius = "single_user"
        
        # Suggest mitigations
        mitigations = self._suggest_mitigations(missing_invariants, dangerous_operations)
        
        return RiskAssessment(
            score=final_score,
            category=category,
            confidence=0.8 if len(missing_invariants) > 0 else 0.5,
            factors=factors,
            mitigations=mitigations,
            blast_radius=blast_radius,
            reversibility="difficult" if final_score >= 70 else "easy",
        )
    
    def _suggest_mitigations(
        self,
        missing_invariants: List[str],
        dangerous_operations: List[str],
    ) -> List[str]:
        """Suggest mitigations based on findings."""
        mitigations = []
        
        if "bounds_checked" in missing_invariants:
            mitigations.append("Add bounds checking before memory operations")
            mitigations.append("Validate input lengths before use")
        
        if "null_checked" in missing_invariants:
            mitigations.append("Add null checks before pointer dereference")
        
        if "input_validated" in missing_invariants:
            mitigations.append("Sanitize and validate all user input")
            mitigations.append("Use parameterized queries for database operations")
        
        if "authenticated" in missing_invariants:
            mitigations.append("Require authentication before this operation")
        
        if "authorized" in missing_invariants:
            mitigations.append("Check user permissions before accessing resource")
        
        if "memcpy" in dangerous_operations or "strcpy" in dangerous_operations:
            mitigations.append("Use safe string functions (strncpy, memcpy_s)")
        
        if "eval" in dangerous_operations or "exec" in dangerous_operations:
            mitigations.append("Avoid eval/exec; use safer alternatives")
        
        return mitigations

