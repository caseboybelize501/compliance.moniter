"""
Control Engine for ACMP.

Maps evidence to controls and evaluates pass/fail status.
"""
import uuid
from datetime import datetime
from typing import Any

from server.models.control import Control, EvidenceArtifact, ControlResult
from server.models.framework import Framework
from engine.framework_registry import FrameworkRegistry
from engine.rules_engine import RulesEngine, RuleResult
from engine.evidence_store import EvidenceStore


class ControlEngineError(Exception):
    """Base exception for control engine errors."""
    pass


class ControlEngine:
    """
    Evaluates controls against collected evidence.
    
    Responsibilities:
    - Map evidence to controls
    - Evaluate control pass/fail
    - Track control state over time
    - Calculate confidence scores
    """
    
    def __init__(
        self,
        framework_registry: FrameworkRegistry,
        rules_engine: RulesEngine,
        evidence_store: EvidenceStore,
    ):
        self.framework_registry = framework_registry
        self.rules_engine = rules_engine
        self.evidence_store = evidence_store
    
    async def evaluate_control(
        self,
        control_id: str,
        tenant_id: str,
        framework_id: str | None = None
    ) -> ControlResult:
        """
        Evaluate a single control.
        
        Args:
            control_id: ID of the control.
            tenant_id: Tenant ID.
            framework_id: Optional framework ID (auto-detected if not provided).
            
        Returns:
            ControlResult with evaluation outcome.
        """
        # Find control in framework
        if framework_id is None:
            # Search across all frameworks
            framework_id = self._find_framework_for_control(control_id)
        
        if not framework_id:
            raise ControlEngineError(f"Control not found: {control_id}")
        
        try:
            control_def = self.framework_registry.get_control(framework_id, control_id)
        except Exception as e:
            raise ControlEngineError(f"Failed to get control definition: {e}")
        
        # Collect evidence for this control
        artifacts = await self.evidence_store.list_artifacts(
            tenant_id=tenant_id,
            control_id=control_id
        )
        
        # Evaluate control
        result = self._evaluate_with_evidence(control_def, artifacts)
        
        # Create ControlResult
        return ControlResult(
            id=str(uuid.uuid4()),
            control_id=control_id,
            tenant_id=tenant_id,
            status=result["status"],
            evidence_count=len(artifacts),
            confidence=result["confidence"],
            details=result["details"],
            evaluated_at=datetime.utcnow(),
            failing_items=result.get("failing_items", []),
            passing_items=result.get("passing_items", [])
        )
    
    async def evaluate_all_controls(
        self,
        tenant_id: str,
        framework_id: str
    ) -> list[ControlResult]:
        """
        Evaluate all controls in a framework.
        
        Args:
            tenant_id: Tenant ID.
            framework_id: Framework ID.
            
        Returns:
            List of ControlResult objects.
        """
        framework = self.framework_registry.get_framework(framework_id)
        results = []
        
        for control in framework.controls:
            if isinstance(control, dict):
                control_id = control.get("id")
                
                try:
                    result = await self.evaluate_control(
                        control_id=control_id,
                        tenant_id=tenant_id,
                        framework_id=framework_id
                    )
                    results.append(result)
                except ControlEngineError as e:
                    # Create failed result
                    results.append(
                        ControlResult(
                            id=str(uuid.uuid4()),
                            control_id=control_id,
                            tenant_id=tenant_id,
                            status="NOT_EVALUATED",
                            evidence_count=0,
                            confidence="LOW",
                            details={"error": str(e)},
                            evaluated_at=datetime.utcnow()
                        )
                    )
        
        return results
    
    def _evaluate_with_evidence(
        self,
        control_def: dict[str, Any],
        artifacts: list[EvidenceArtifact]
    ) -> dict[str, Any]:
        """
        Evaluate control with collected evidence.
        
        Args:
            control_def: Control definition from framework.
            artifacts: List of evidence artifacts.
            
        Returns:
            Evaluation result dictionary.
        """
        rule_type = control_def.get("rule_type", "existence")
        rule_config = control_def.get("rule_config", {})
        
        if not artifacts:
            return {
                "status": "NOT_EVALUATED",
                "confidence": "LOW",
                "details": {"reason": "No evidence collected"},
                "failing_items": [],
                "passing_items": []
            }
        
        # Build evidence data from artifacts
        evidence_data = self._build_evidence_data(artifacts)
        
        # Evaluate rule
        try:
            rule_result = self.rules_engine.evaluate(rule_type, rule_config, evidence_data)
        except Exception as e:
            return {
                "status": "NOT_EVALUATED",
                "confidence": "LOW",
                "details": {"error": str(e)},
                "failing_items": [],
                "passing_items": []
            }
        
        # Determine status
        if rule_result.passed:
            status = "PASS"
            confidence = self._calculate_confidence(artifacts, rule_result)
        elif rule_result.coverage_percent is not None and rule_result.coverage_percent > 50:
            status = "PARTIAL"
            confidence = "MEDIUM"
        else:
            status = "FAIL"
            confidence = self._calculate_confidence(artifacts, rule_result)
        
        return {
            "status": status,
            "confidence": confidence,
            "details": rule_result.details,
            "failing_items": rule_result.failing_items,
            "passing_items": rule_result.passing_items,
        }
    
    def _build_evidence_data(self, artifacts: list[EvidenceArtifact]) -> dict[str, Any]:
        """Build evidence data structure from artifacts."""
        evidence_data = {
            "artifact_count": len(artifacts),
            "sources": list(set(a.source for a in artifacts)),
            "documents": [],
            "processes": [],
            "controls": [],
        }
        
        for artifact in artifacts:
            content = artifact.content
            
            # Extract relevant fields based on evidence type
            if artifact.metadata.get("evidence_type") == "mfa_status":
                evidence_data["users_with_mfa"] = content.get("users_with_mfa", 0)
                evidence_data["total_users"] = content.get("total_users", 0)
                evidence_data["coverage_percent"] = content.get("mfa_coverage_percent", 0)
            
            elif artifact.metadata.get("evidence_type") == "branch_protection":
                evidence_data["protected_repos"] = content.get("protected_repos", 0)
                evidence_data["total_repos"] = content.get("total_repos", 0)
            
            # Add document names if present
            if "documents" in content:
                evidence_data["documents"].extend(content["documents"])
        
        return evidence_data
    
    def _calculate_confidence(
        self,
        artifacts: list[EvidenceArtifact],
        rule_result: RuleResult
    ) -> str:
        """Calculate confidence score for evaluation."""
        # More artifacts = higher confidence
        artifact_score = min(1.0, len(artifacts) / 5)  # Cap at 5 artifacts
        
        # More sources = higher confidence
        sources = set(a.source for a in artifacts)
        source_score = min(1.0, len(sources) / 3)  # Cap at 3 sources
        
        # Rule result details
        if rule_result.coverage_percent is not None:
            coverage_score = rule_result.coverage_percent / 100
        else:
            coverage_score = 1.0 if rule_result.passed else 0.0
        
        # Combined score
        combined = (artifact_score * 0.3 + source_score * 0.3 + coverage_score * 0.4)
        
        if combined >= 0.8:
            return "HIGH"
        elif combined >= 0.5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _find_framework_for_control(self, control_id: str) -> str | None:
        """Find which framework contains a control."""
        for framework_id in self.framework_registry.list_frameworks():
            try:
                self.framework_registry.get_control(framework_id, control_id)
                return framework_id
            except Exception:
                continue
        return None
    
    async def get_control_status(
        self,
        tenant_id: str,
        framework_id: str
    ) -> dict[str, ControlResult]:
        """
        Get current status of all controls in a framework.
        
        Args:
            tenant_id: Tenant ID.
            framework_id: Framework ID.
            
        Returns:
            Dictionary mapping control_id to latest ControlResult.
        """
        results = await self.evaluate_all_controls(tenant_id, framework_id)
        return {r.control_id: r for r in results}
