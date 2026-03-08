"""
Base Connector for ACMP.

Abstract base class for all source connectors.
Implements rate limiting, evidence artifact creation, and common functionality.
"""
import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field

import httpx

from server.models.control import EvidenceArtifact
from server.models.tenant import SourceProfile


@dataclass
class RateLimitConfig:
    """Rate limit configuration for a connector."""
    requests_per_second: float = 10.0
    requests_per_minute: int | None = None
    requests_per_hour: int | None = None
    burst_size: int = 20


@dataclass
class RateLimitState:
    """Current rate limit state."""
    tokens: float = field(default_factory=lambda: 20.0)
    last_update: float = field(default_factory=time.time)
    minute_count: int = 0
    minute_reset: float = field(default_factory=time.time)
    hour_count: int = 0
    hour_reset: float = field(default_factory=time.time)


class ConnectorError(Exception):
    """Base exception for connector errors."""
    pass


class ConnectorAuthenticationError(ConnectorError):
    """Raised when authentication fails."""
    pass


class ConnectorRateLimitError(ConnectorError):
    """Raised when rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ConnectorConfigError(ConnectorError):
    """Raised when connector configuration is invalid."""
    pass


class BaseConnector(ABC):
    """
    Abstract base class for all source connectors.
    
    Implements:
    - Rate limiting with token bucket algorithm
    - Evidence artifact creation with dedup
    - Common authentication patterns
    - Error handling and retry logic
    """
    
    # Class-level configuration
    source_type: str = "base"
    default_rate_limit: RateLimitConfig = RateLimitConfig()
    
    def __init__(
        self,
        source_profile: SourceProfile,
        rate_limit_config: RateLimitConfig | None = None
    ):
        self.source_profile = source_profile
        self.rate_limit_config = rate_limit_config or self.default_rate_limit
        self._rate_state = RateLimitState()
        self._http_client: httpx.AsyncClient | None = None
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name for this connector."""
        pass
    
    @abstractmethod
    async def validate_credentials(self) -> bool:
        """
        Validate that credentials are working.
        
        Returns:
            True if credentials are valid and read-only access confirmed.
            
        Raises:
            ConnectorAuthenticationError: If authentication fails.
            ConnectorConfigError: If configuration is invalid.
        """
        pass
    
    @abstractmethod
    async def collect_evidence(self, evidence_type: str, **kwargs: Any) -> list[EvidenceArtifact]:
        """
        Collect evidence for a specific evidence type.
        
        Args:
            evidence_type: Type of evidence to collect (e.g., 'mfa_status', 'iam_users').
            **kwargs: Additional parameters for evidence collection.
            
        Returns:
            List of EvidenceArtifact objects.
            
        Raises:
            ConnectorError: If evidence collection fails.
        """
        pass
    
    @abstractmethod
    async def get_available_evidence_types(self) -> list[str]:
        """
        Get list of evidence types this connector can collect.
        
        Returns:
            List of evidence type strings.
        """
        pass
    
    def _compute_artifact_hash(self, content: dict[str, Any]) -> str:
        """
        Compute SHA256 hash of artifact content for dedup.
        
        Args:
            content: Artifact content dictionary.
            
        Returns:
            Hex-encoded SHA256 hash.
        """
        # Sort keys for consistent hashing
        content_str = str(sorted(content.items()))
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    def _create_artifact(
        self,
        control_id: str,
        content: dict[str, Any],
        source_id: str | None = None,
        metadata: dict[str, Any] | None = None
    ) -> EvidenceArtifact:
        """
        Create an EvidenceArtifact with proper hashing and metadata.
        
        Args:
            control_id: Associated control ID.
            content: Artifact content.
            source_id: Optional source profile ID.
            metadata: Optional additional metadata.
            
        Returns:
            EvidenceArtifact ready for storage.
        """
        artifact_hash = self._compute_artifact_hash(content)
        return EvidenceArtifact(
            id=f"{self.source_type}_{control_id}_{artifact_hash[:12]}",
            control_id=control_id,
            source=self.source_type,
            source_id=source_id or self.source_profile.id,
            artifact_hash=artifact_hash,
            content=content,
            collected_at=datetime.utcnow(),
            tenant_id=self.source_profile.tenant_id,
            metadata=metadata or {}
        )
    
    async def _acquire_rate_limit(self) -> None:
        """
        Acquire a rate limit token using token bucket algorithm.
        
        Raises:
            ConnectorRateLimitError: If rate limit exceeded and no retry possible.
        """
        config = self.rate_limit_config
        state = self._rate_state
        now = time.time()
        
        # Refill tokens based on time elapsed
        elapsed = now - state.last_update
        state.tokens = min(
            config.burst_size,
            state.tokens + elapsed * config.requests_per_second
        )
        state.last_update = now
        
        # Check minute rate limit
        if config.requests_per_minute:
            if now - state.minute_reset >= 60:
                state.minute_count = 0
                state.minute_reset = now
            if state.minute_count >= config.requests_per_minute:
                retry_after = int(60 - (now - state.minute_reset))
                raise ConnectorRateLimitError(
                    f"Minute rate limit exceeded for {self.source_type}",
                    retry_after=retry_after
                )
        
        # Check hour rate limit
        if config.requests_per_hour:
            if now - state.hour_reset >= 3600:
                state.hour_count = 0
                state.hour_reset = now
            if state.hour_count >= config.requests_per_hour:
                retry_after = int(3600 - (now - state.hour_reset))
                raise ConnectorRateLimitError(
                    f"Hour rate limit exceeded for {self.source_type}",
                    retry_after=retry_after
                )
        
        # Wait for token if bucket is empty
        if state.tokens < 1:
            wait_time = (1 - state.tokens) / config.requests_per_second
            await self._sleep(wait_time)
            state.tokens = 0
        
        # Consume token
        state.tokens -= 1
        state.minute_count += 1
        state.hour_count += 1
    
    async def _sleep(self, seconds: float) -> None:
        """Sleep for specified seconds (async-compatible)."""
        await asyncio.sleep(seconds)
    
    async def _request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        **kwargs: Any
    ) -> httpx.Response:
        """
        Make an HTTP request with rate limiting and error handling.
        
        Args:
            method: HTTP method.
            url: Request URL.
            headers: Optional headers.
            **kwargs: Additional arguments for httpx.
            
        Returns:
            httpx.Response object.
            
        Raises:
            ConnectorRateLimitError: If rate limited.
            ConnectorAuthenticationError: If authentication fails.
            ConnectorError: If request fails.
        """
        await self._acquire_rate_limit()
        
        client = self._get_http_client()
        
        try:
            response = await client.request(method, url, headers=headers, **kwargs)
            
            # Handle rate limit response
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise ConnectorRateLimitError(
                    f"Rate limited by {self.source_type} API",
                    retry_after=retry_after
                )
            
            # Handle authentication errors
            if response.status_code in (401, 403):
                raise ConnectorAuthenticationError(
                    f"Authentication failed for {self.source_type}: {response.text}"
                )
            
            response.raise_for_status()
            return response
            
        except httpx.HTTPError as e:
            raise ConnectorError(f"HTTP error for {self.source_type}: {e}")
    
    def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0, connect=10.0),
                follow_redirects=True
            )
        return self._http_client
    
    async def close(self) -> None:
        """Close the connector and release resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def __aenter__(self) -> "BaseConnector":
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.close()


# Import asyncio at module level for the sleep method
import asyncio
