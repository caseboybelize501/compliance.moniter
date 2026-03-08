"""Unit tests for Violation Detector."""
import pytest
from datetime import datetime, timedelta

from server.models.control import ControlResult
from server.models.violation import Violation
from engine.violation_detector import ViolationDetector


class TestViolationDetector:
    """Tests for ViolationDetector."""

    def test_detect_violation_on_fail(self, sample_control):
        """Test that violation is created when control fails."""
        detector = ViolationDetector()
        
        control_result = ControlResult(
            id="result_123",
            control_id="CC6.1",
            tenant_id="tenant_123",
            status="FAIL",
            evidence_count=5,
            confidence="HIGH",
            failing_items=[{"item": "test"}]
        )
        
        violation = detector.detect_violation(control_result, sample_control)
        
        assert violation is not None
        assert violation.status == "OPEN"
        assert violation.severity in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_no_violation_on_pass(self, sample_control):
        """Test that no violation is created when control passes."""
        detector = ViolationDetector()
        
        control_result = ControlResult(
            id="result_123",
            control_id="CC6.1",
            tenant_id="tenant_123",
            status="PASS",
            evidence_count=5,
            confidence="HIGH"
        )
        
        violation = detector.detect_violation(control_result, sample_control)
        
        assert violation is None

    def test_dedup_window_prevents_duplicate(self, sample_control):
        """Test that dedup window prevents duplicate violations."""
        detector = ViolationDetector()
        
        control_result = ControlResult(
            id="result_123",
            control_id="CC6.1",
            tenant_id="tenant_123",
            status="FAIL",
            evidence_count=5
        )
        
        # First violation
        violation1 = detector.detect_violation(control_result, sample_control)
        
        # Second violation within dedup window
        violation2 = detector.detect_violation(control_result, sample_control)
        
        assert violation1 is not None
        assert violation2 is None  # Should return existing violation

    def test_severity_classification(self, sample_control):
        """Test severity classification based on control result."""
        detector = ViolationDetector()
        
        # Admin without MFA should be HIGH
        control_result = ControlResult(
            id="result_123",
            control_id="CC6.1",
            tenant_id="tenant_123",
            status="FAIL",
            details={"admin_without_mfa": True}
        )
        
        violation = detector.detect_violation(control_result, sample_control)
        assert violation.severity == "HIGH"

    def test_close_violation(self, sample_control):
        """Test closing a violation."""
        detector = ViolationDetector()
        
        control_result = ControlResult(
            id="result_123",
            control_id="CC6.1",
            tenant_id="tenant_123",
            status="FAIL"
        )
        
        violation = detector.detect_violation(control_result, sample_control)
        closed = detector.close_violation(violation.id, "Remediated", "Evidence note")
        
        assert closed.status == "CLOSED"
        assert closed.closure_reason == "Remediated"
        assert closed.evidence_note == "Evidence note"

    def test_get_violation_summary(self, sample_control):
        """Test getting violation summary."""
        detector = ViolationDetector()
        
        # Create some violations
        for i in range(3):
            control_result = ControlResult(
                id=f"result_{i}",
                control_id=f"CC6.{i+1}",
                tenant_id="tenant_123",
                status="FAIL"
            )
            detector.detect_violation(control_result, sample_control)
        
        summary = detector.get_violation_summary("tenant_123")
        
        assert summary["total"] > 0
        assert "open" in summary
        assert "by_severity" in summary
