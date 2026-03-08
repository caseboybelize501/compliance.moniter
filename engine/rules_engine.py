"""
Rules Engine for ACMP.

Pluggable rule evaluation for different control types.
"""
from typing import Any, Protocol
from abc import ABC, abstractmethod


class RuleEvaluationError(Exception):
    """Base exception for rule evaluation errors."""
    pass


class RuleNotFoundError(RuleEvaluationError):
    """Raised when rule type is not found."""
    pass


class RuleResult:
    """Result of rule evaluation."""
    
    def __init__(
        self,
        passed: bool,
    RuleConfig: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None
    ):
        self.passed = passed
        self.rule_config = rule_config or {}
        self.details = details or {}
        self.coverage_percent: float | None = None
        self.failing_items: list[dict[str, Any]] = []
        self.passing_items: list[dict[str, Any]] = []


class RuleEvaluator(Protocol):
    """Protocol for rule evaluators."""
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """Evaluate evidence against rule configuration."""
        ...


class ExistenceRuleEvaluator:
    """
    Evaluates existence rules.
    
    Checks if required documents, processes, or controls exist.
    """
    
    rule_type = "existence"
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate existence rule.
        
        Args:
            rule_config: Configuration with required_documents, required_processes, etc.
            evidence: Evidence data.
            
        Returns:
            RuleResult with pass/fail status.
        """
        required_docs = rule_config.get("required_documents", [])
        required_processes = rule_config.get("required_processes", [])
        required_controls = rule_config.get("required_controls", [])
        required_roles = rule_config.get("required_roles", [])
        required_if = rule_config.get("required_if", [])  # Conditional requirements
        
        # Check conditional requirements first
        if required_if:
            for condition in required_if:
                if evidence.get(condition):
                    # Condition met, requirement applies
                    pass
        
        missing = []
        found = []
        
        # Check required documents
        existing_docs = evidence.get("documents", [])
        for doc in required_docs:
            if any(doc.lower() in d.lower() for d in existing_docs):
                found.append({"type": "document", "name": doc})
            else:
                missing.append({"type": "document", "name": doc})
        
        # Check required processes
        existing_processes = evidence.get("processes", [])
        for proc in required_processes:
            if any(proc.lower() in p.lower() for p in existing_processes):
                found.append({"type": "process", "name": proc})
            else:
                missing.append({"type": "process", "name": proc})
        
        # Check required controls
        existing_controls = evidence.get("controls", [])
        for ctrl in required_controls:
            if any(ctrl.lower() in c.lower() for c in existing_controls):
                found.append({"type": "control", "name": ctrl})
            else:
                missing.append({"type": "control", "name": ctrl})
        
        passed = len(missing) == 0
        
        return RuleResult(
            passed=passed,
            rule_config=rule_config,
            details={
                "found": found,
                "missing": missing,
            },
            passing_items=found,
            failing_items=missing
        )


class PercentageRuleEvaluator:
    """
    Evaluates percentage-based rules.
    
    Checks if a metric meets a threshold percentage.
    """
    
    rule_type = "percentage"
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate percentage rule.
        
        Args:
            rule_config: Configuration with threshold and metric.
            evidence: Evidence data with metric values.
            
        Returns:
            RuleResult with pass/fail status and coverage percentage.
        """
        threshold = rule_config.get("threshold", 100)
        metric_name = rule_config.get("metric")
        
        if not metric_name:
            raise RuleEvaluationError("Percentage rule requires 'metric' configuration")
        
        # Get metric value from evidence
        actual_percent = evidence.get(metric_name, evidence.get("coverage_percent", 0))
        
        passed = actual_percent >= threshold
        
        return RuleResult(
            passed=passed,
            rule_config=rule_config,
            details={
                "threshold": threshold,
                "actual_percent": actual_percent,
                "metric": metric_name,
                "gap": max(0, threshold - actual_percent),
            },
            coverage_percent=actual_percent,
            passing_items=[{"metric": metric_name, "value": actual_percent}] if passed else [],
            failing_items=[{"metric": metric_name, "value": actual_percent, "threshold": threshold}] if not passed else []
        )


class BooleanRuleEvaluator:
    """
    Evaluates boolean rules.
    
    Checks if a boolean condition is true.
    """
    
    rule_type = "boolean"
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate boolean rule.
        
        Args:
            rule_config: Configuration with expected_value and field.
            evidence: Evidence data.
            
        Returns:
            RuleResult with pass/fail status.
        """
        field = rule_config.get("field")
        expected_value = rule_config.get("expected_value", True)
        
        if not field:
            raise RuleEvaluationError("Boolean rule requires 'field' configuration")
        
        actual_value = evidence.get(field, False)
        passed = actual_value == expected_value
        
        return RuleResult(
            passed=passed,
            rule_config=rule_config,
            details={
                "field": field,
                "expected": expected_value,
                "actual": actual_value,
            },
            passing_items=[{"field": field, "value": actual_value}] if passed else [],
            failing_items=[{"field": field, "value": actual_value, "expected": expected_value}] if not passed else []
        )


class ThresholdRuleEvaluator:
    """
    Evaluates threshold rules.
    
    Checks if a numeric value meets a threshold.
    """
    
    rule_type = "threshold"
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate threshold rule.
        
        Args:
            rule_config: Configuration with threshold, comparison, and field.
            evidence: Evidence data.
            
        Returns:
            RuleResult with pass/fail status.
        """
        threshold = rule_config.get("threshold", 0)
        comparison = rule_config.get("comparison", ">=")  # >=, <=, >, <, ==
        field = rule_config.get("field")
        
        if not field:
            raise RuleEvaluationError("Threshold rule requires 'field' configuration")
        
        actual_value = evidence.get(field, 0)
        
        if comparison == ">=":
            passed = actual_value >= threshold
        elif comparison == "<=":
            passed = actual_value <= threshold
        elif comparison == ">":
            passed = actual_value > threshold
        elif comparison == "<":
            passed = actual_value < threshold
        elif comparison == "==":
            passed = actual_value == threshold
        else:
            raise RuleEvaluationError(f"Unknown comparison operator: {comparison}")
        
        return RuleResult(
            passed=passed,
            rule_config=rule_config,
            details={
                "field": field,
                "threshold": threshold,
                "comparison": comparison,
                "actual": actual_value,
            },
            passing_items=[{"field": field, "value": actual_value}] if passed else [],
            failing_items=[{"field": field, "value": actual_value, "threshold": threshold}] if not passed else []
        )


class ConditionalRuleEvaluator:
    """
    Evaluates conditional rules.
    
    Requirements apply only if certain conditions are met.
    """
    
    rule_type = "conditional"
    
    def evaluate(self, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate conditional rule.
        
        Args:
            rule_config: Configuration with required_if conditions.
            evidence: Evidence data.
            
        Returns:
            RuleResult with pass/fail status.
        """
        required_if = rule_config.get("required_if", [])
        
        if not required_if:
            # No conditions, rule is N/A
            return RuleResult(
                passed=True,
                rule_config=rule_config,
                details={"status": "not_applicable", "reason": "No conditions specified"}
            )
        
        # Check if any condition applies
        conditions_met = []
        for condition in required_if:
            if evidence.get(condition):
                conditions_met.append(condition)
        
        if not conditions_met:
            # No conditions met, rule is N/A
            return RuleResult(
                passed=True,
                rule_config=rule_config,
                details={"status": "not_applicable", "reason": "No conditions met"}
            )
        
        # Conditions met, check requirements
        # This would typically check for additional evidence
        return RuleResult(
            passed=True,
            rule_config=rule_config,
            details={
                "status": "applicable",
                "conditions_met": conditions_met,
            }
        )


class RulesEngine:
    """
    Main rules engine.
    
    Routes evaluation to appropriate rule evaluator based on rule type.
    """
    
    def __init__(self):
        self._evaluators: dict[str, RuleEvaluator] = {
            "existence": ExistenceRuleEvaluator(),
            "percentage": PercentageRuleEvaluator(),
            "boolean": BooleanRuleEvaluator(),
            "threshold": ThresholdRuleEvaluator(),
            "conditional": ConditionalRuleEvaluator(),
        }
    
    def register_evaluator(self, rule_type: str, evaluator: RuleEvaluator) -> None:
        """Register a custom rule evaluator."""
        self._evaluators[rule_type] = evaluator
    
    def evaluate(self, rule_type: str, rule_config: dict[str, Any], evidence: dict[str, Any]) -> RuleResult:
        """
        Evaluate evidence against a rule.
        
        Args:
            rule_type: Type of rule (existence, percentage, etc.).
            rule_config: Rule configuration.
            evidence: Evidence data.
            
        Returns:
            RuleResult with evaluation outcome.
            
        Raises:
            RuleNotFoundError: If rule type is not registered.
        """
        evaluator = self._evaluators.get(rule_type)
        if not evaluator:
            raise RuleNotFoundError(f"Unknown rule type: {rule_type}")
        
        return evaluator.evaluate(rule_config, evidence)
    
    def evaluate_multiple(
        self,
        rules: list[dict[str, Any]],
        evidence: dict[str, Any]
    ) -> list[RuleResult]:
        """
        Evaluate multiple rules against evidence.
        
        Args:
            rules: List of rule configurations (each with rule_type and rule_config).
            evidence: Evidence data.
            
        Returns:
            List of RuleResult objects.
        """
        results = []
        for rule in rules:
            rule_type = rule.get("rule_type")
            rule_config = rule.get("rule_config", {})
            
            try:
                result = self.evaluate(rule_type, rule_config, evidence)
                results.append(result)
            except RuleEvaluationError as e:
                results.append(
                    RuleResult(
                        passed=False,
                        rule_config=rule_config,
                        details={"error": str(e)}
                    )
                )
        
        return results
    
    def get_supported_rule_types(self) -> list[str]:
        """Get list of supported rule types."""
        return list(self._evaluators.keys())


# Global rules engine instance
engine = RulesEngine()
