"""
Violation Detector for ACMP.

Detects violations from control failures and manages severity classification.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any

from server.models.control import ControlResult
from server.models.violation import Violation


class ViolationDetectorError(Exception):
    """Base exception for violation detector errors."""
    pass


class ViolationDetector:
    """
    Detects and manages violations.
    
    Responsibilities:
    - Create violations from control failures
    - Classify severity
    - Dedup violations (1hr window)
    - Escalate related violations
    """
    
    def __init__(self):
        self._violations: dict[str, Violation] = {}
        self._violation_history: dict[str, list[Violation]] = {}  # control_id -> violations
        self._dedup_window_hours = 1
    
    def detect_violation(
        self,
        control_result: ControlResult,
        control_def: dict[str, Any] | None = None
    ) -> Violation | None:
        """
        Detect violation from control result.
        
        Args:
            control_result: Control evaluation result.
            control_def: Optional control definition for context.
            
        Returns:
            Violation if control failed, None otherwise.
        """
        if control_result.status not in ("FAIL", "PARTIAL"):
            return None
        
        # Check dedup window
        existing = self._check_dedup_window(
            control_result.control_id,
            control_result.tenant_id
        )
        
        if existing:
            # Update existing violation
            return existing
        
        # Determine severity
        severity = self._classify_severity(control_result, control_def)
        
        # Create violation
        violation = Violation(
            id=str(uuid.uuid4()),
            control_id=control_result.control_id,
            control_result_id=control_result.id,
            tenant_id=control_result.tenant_id,
            severity=severity,
            description=self._generate_description(control_result, control_def),
            status="OPEN",
            opened_at=datetime.utcnow(),
            age_days=0,
        )
        
        # Store violation
        self._violations[violation.id] = violation
        
        if control_result.control_id not in self._violation_history:
            self._violation_history[control_result.control_id] = []
        self._violation_history[control_result.control_id].append(violation)
        
        # Check for escalation
        self._check_escalation(violation)
        
        return violation
    
    def _check_dedup_window(self, control_id: str, tenant_id: str) -> Violation | None:
        """Check if violation exists within dedup window."""
        if control_id not in self._violation_history:
            return None
        
        window_start = datetime.utcnow() - timedelta(hours=self._dedup_window_hours)
        
        for violation in reversed(self._violation_history[control_id]):
            if violation.tenant_id != tenant_id:
                continue
            if violation.opened_at < window_start:
                continue
            if violation.status == "OPEN":
                return violation
        
        return None
    
    def _classify_severity(
        self,
        control_result: ControlResult,
        control_def: dict[str, Any] | None
    ) -> str:
        """
        Classify violation severity.
        
        Severity levels:
        - CRITICAL: Immediate threat to compliance posture
        - HIGH: Significant compliance gap
        - MEDIUM: Moderate compliance gap
        - LOW: Minor issue
        """
        # Use control definition severity as base
        if control_def:
            base_severity = control_def.get("severity", "MEDIUM")
        else:
            base_severity = "MEDIUM"
        
        # Adjust based on control result
        if control_result.status == "FAIL":
            # Check for high-risk indicators
            details = control_result.details
            
            # Admin without MFA -> HIGH
            if "admin" in str(details).lower() and "mfa" in str(details).lower():
                return "HIGH"
            
            # Encryption missing -> HIGH
            if "encrypt" in str(details).lower():
                return "HIGH"
            
            # Escalate base severity for complete failures
            if base_severity == "MEDIUM":
                return "HIGH"
            elif base_severity == "LOW":
                return "MEDIUM"
        
        elif control_result.status == "PARTIAL":
            # Partial failures are one level lower
            severity_map = {"CRITICAL": "HIGH", "HIGH": "MEDIUM", "MEDIUM": "LOW", "LOW": "LOW"}
            return severity_map.get(base_severity, "MEDIUM")
        
        return base_severity
    
    def _generate_description(
        self,
        control_result: ControlResult,
        control_def: dict[str, Any] | None
    ) -> str:
        """Generate violation description."""
        control_name = control_def.get("name", control_result.control_id) if control_def else control_result.control_id
        
        if control_result.status == "FAIL":
            return f"Control '{control_name}' failed evaluation. {len(control_result.failing_items)} items failed."
        else:
            return f"Control '{control_name}' partially passing. Coverage: {control_result.evidence_count} evidence items."
    
    def _check_escalation(self, new_violation: Violation) -> None:
        """Check if violation should be escalated due to related violations."""
        # Find related violations (same category or related controls)
        related = self._find_related_violations(new_violation)
        
        if len(related) >= 3:
            # Escalate to CRITICAL
            new_violation.severity = "CRITICAL"
            new_violation.related_violation_ids = [v.id for v in related[:5]]
    
    def _find_related_violations(self, violation: Violation) -> list[Violation]:
        """Find violations related to this one."""
        related = []
        
        # Get control category
        control_category = violation.control_id.split(".")[0] if "." in violation.control_id else ""
        
        for existing in self._violations.values():
            if existing.id == violation.id:
                continue
            if existing.status != "OPEN":
                continue
            if existing.tenant_id != violation.tenant_id:
                continue
            
            # Same category
            existing_category = existing.control_id.split(".")[0] if "." in existing.control_id else ""
            if control_category and existing_category == control_category:
                related.append(existing)
        
        return related
    
    def get_open_violations(self, tenant_id: str) -> list[Violation]:
        """Get all open violations for a tenant."""
        return [
            v for v in self._violations.values()
            if v.tenant_id == tenant_id and v.status == "OPEN"
        ]
    
    def get_violation(self, violation_id: str) -> Violation | None:
        """Get a specific violation by ID."""
        return self._violations.get(violation_id)
    
    def close_violation(
        self,
        violation_id: str,
        reason: str,
        evidence_note: str | None = None
    ) -> Violation | None:
        """
        Close a violation.
        
        Args:
            violation_id: ID of the violation.
            reason: Reason for closure.
            evidence_note: Optional remediation evidence.
            
        Returns:
            Updated violation or None if not found.
        """
        violation = self._violations.get(violation_id)
        if not violation:
            return None
        
        violation.status = "CLOSED"
        violation.closed_at = datetime.utcnow()
        violation.closure_reason = reason
        violation.evidence_note = evidence_note
        
        return violation
    
    def get_violations_by_severity(
        self,
        tenant_id: str,
        severity: str
    ) -> list[Violation]:
        """Get violations filtered by severity."""
        return [
            v for v in self._violations.values()
            if v.tenant_id == tenant_id and v.severity == severity and v.status == "OPEN"
        ]
    
    def get_violation_summary(self, tenant_id: str) -> dict[str, Any]:
        """Get violation summary for a tenant."""
        violations = [v for v in self._violations.values() if v.tenant_id == tenant_id]
        
        open_violations = [v for v in violations if v.status == "OPEN"]
        
        by_severity = {}
        for v in open_violations:
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
        
        # Calculate age of oldest critical
        critical_violations = [v for v in open_violations if v.severity == "CRITICAL"]
        critical_age_days = 0
        if critical_violations:
            oldest = min(critical_violations, key=lambda v: v.opened_at)
            critical_age_days = (datetime.utcnow() - oldest.opened_at).days
        
        return {
            "total": len(violations),
            "open": len(open_violations),
            "in_progress": sum(1 for v in violations if v.status == "IN_PROGRESS"),
            "closed": sum(1 for v in violations if v.status == "CLOSED"),
            "by_severity": by_severity,
            "critical_age_days": critical_age_days,
        }
