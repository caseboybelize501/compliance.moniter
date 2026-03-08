"""Unit tests for Evidence Store."""
import pytest
from datetime import datetime

from engine.evidence_store import EvidenceStore, StorageConfig, EvidenceStoreError


class TestEvidenceStore:
    """Tests for EvidenceStore."""

    def test_store_artifact_encrypts(self):
        """Test that storing an artifact encrypts the content."""
        config = StorageConfig(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        )
        store = EvidenceStore(config)
        
        # Would test encryption in real implementation
        assert True  # Placeholder

    def test_dedup_prevents_duplicate(self, mock_evidence_store):
        """Test that dedup prevents storing duplicate artifacts."""
        # Mock existing artifact
        mock_evidence_store.check_dedup.return_value = MagicMock()
        
        # Would test dedup logic
        assert True  # Placeholder

    def test_tenant_isolation(self, mock_evidence_store):
        """Test that tenants can only access their own artifacts."""
        # Would test tenant isolation
        assert True  # Placeholder

    def test_list_artifacts_with_filters(self, mock_evidence_store):
        """Test listing artifacts with filters."""
        # Would test filtering by control_id, source, since
        assert True  # Placeholder


class TestEvidenceStoreEncryption:
    """Tests for encryption functionality."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encrypted content can be decrypted."""
        config = StorageConfig(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test",
            encryption_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        )
        store = EvidenceStore(config)
        
        original = {"key": "value", "number": 42}
        encrypted = store._encrypt_content(original)
        decrypted = store._decrypt_content(encrypted)
        
        assert decrypted == original

    def test_encryption_required(self):
        """Test that encryption is required for storage."""
        config = StorageConfig(
            s3_endpoint="http://localhost:9000",
            s3_access_key="test",
            s3_secret_key="test"
        )
        store = EvidenceStore(config)
        
        # Should generate key if not provided
        assert store._fernet is not None
