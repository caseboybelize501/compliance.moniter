"""
ACMP Connectors

Source connectors for collecting compliance evidence.
"""
from connectors.base import (
    BaseConnector,
    ConnectorError,
    ConnectorAuthenticationError,
    ConnectorRateLimitError,
    ConnectorConfigError,
    RateLimitConfig,
)
from connectors.connector_manager import (
    ConnectorManager,
    ConnectorRegistry,
    registry,
    register_default_connectors,
)

__all__ = [
    # Base classes
    "BaseConnector",
    "ConnectorError",
    "ConnectorAuthenticationError",
    "ConnectorRateLimitError",
    "ConnectorConfigError",
    "RateLimitConfig",
    # Manager
    "ConnectorManager",
    "ConnectorRegistry",
    "registry",
    "register_default_connectors",
]
