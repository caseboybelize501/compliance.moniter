"""Pytest configuration and shared fixtures."""
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_evidence_store():
    """Mock evidence store for testing."""
    store = MagicMock()
    store.store_artifact = AsyncMock()
    store.get_artifact = AsyncMock()
    store.check_dedup = AsyncMock()
    store.list_artifacts = AsyncMock()
    return store


@pytest.fixture
def mock_framework_registry():
    """Mock framework registry for testing."""
    registry = MagicMock()
    registry.get_framework = MagicMock()
    registry.get_control = MagicMock()
    registry.list_frameworks = MagicMock(return_value=["soc2", "hipaa"])
    return registry


@pytest.fixture
def mock_rules_engine():
    """Mock rules engine for testing."""
    engine = MagicMock()
    engine.evaluate = MagicMock()
    return engine


@pytest.fixture
def mock_connector_manager():
    """Mock connector manager for testing."""
    manager = MagicMock()
    manager.list_sources = MagicMock()
    manager.collect_evidence = AsyncMock()
    manager.validate_source = AsyncMock()
    return manager


@pytest.fixture
def sample_control():
    """Sample control definition for testing."""
    return {
        "id": "CC6.1",
        "name": "Logical Access - Authentication",
        "description": "The entity implements logical access security.",
        "category": "CC6",
        "evidence_types": ["mfa_status", "authentication_policy"],
        "rule_type": "percentage",
        "rule_config": {"threshold": 100, "metric": "users_with_mfa"},
        "severity": "HIGH"
    }


@pytest.fixture
def sample_evidence_artifact():
    """Sample evidence artifact for testing."""
    return {
        "id": "artifact_123",
        "control_id": "CC6.1",
        "source": "okta",
        "artifact_hash": "abc123",
        "content": {
            "users_with_mfa": 95,
            "total_users": 100,
            "mfa_coverage_percent": 95.0
        },
        "tenant_id": "tenant_123"
    }


@pytest.fixture
def sample_violation():
    """Sample violation for testing."""
    return {
        "id": "violation_123",
        "control_id": "CC6.1",
        "severity": "HIGH",
        "description": "MFA not enabled for all users",
        "status": "OPEN",
        "tenant_id": "tenant_123"
    }
