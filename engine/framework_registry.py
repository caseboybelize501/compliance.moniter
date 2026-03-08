"""
Framework Registry for ACMP.

Loads, versions, and manages compliance frameworks.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from server.models.framework import Framework, FrameworkVersion
from frameworks.loader import load_all_seed_frameworks, get_control_by_id


class FrameworkRegistryError(Exception):
    """Base exception for framework registry errors."""
    pass


class FrameworkNotFoundError(FrameworkRegistryError):
    """Raised when framework is not found."""
    pass


class ControlNotFoundError(FrameworkRegistryError):
    """Raised when control is not found."""
    pass


class FrameworkRegistry:
    """
    Registry for compliance frameworks.
    
    Responsibilities:
    - Load seed frameworks on startup
    - Track framework versions
    - Support custom frameworks per tenant
    - Provide control lookup
    """
    
    def __init__(self, frameworks_dir: Path | None = None):
        self._frameworks: dict[str, Framework] = {}
        self._framework_versions: dict[str, list[FrameworkVersion]] = {}
        self._custom_frameworks: dict[str, dict[str, Framework]] = {}  # tenant_id -> framework_id -> framework
        self._frameworks_dir = frameworks_dir or Path(__file__).parent.parent / "frameworks"
    
    async def initialize(self) -> None:
        """Initialize registry with seed frameworks."""
        seed_frameworks = load_all_seed_frameworks(self._frameworks_dir)
        
        for framework in seed_frameworks:
            self._frameworks[framework.id] = framework
            self._framework_versions[framework.id] = [
                FrameworkVersion(
                    id=f"{framework.id}_v1",
                    framework_id=framework.id,
                    version=framework.version,
                    change_summary="Initial seed load",
                    created_at=datetime.utcnow()
                )
            ]
    
    def get_framework(self, framework_id: str) -> Framework:
        """
        Get a framework by ID.
        
        Args:
            framework_id: ID of the framework.
            
        Returns:
            Framework object.
            
        Raises:
            FrameworkNotFoundError: If framework not found.
        """
        if framework_id not in self._frameworks:
            raise FrameworkNotFoundError(f"Framework not found: {framework_id}")
        return self._frameworks[framework_id]
    
    def get_control(self, framework_id: str, control_id: str) -> dict[str, Any]:
        """
        Get a specific control from a framework.
        
        Args:
            framework_id: ID of the framework.
            control_id: ID of the control.
            
        Returns:
            Control definition dictionary.
            
        Raises:
            FrameworkNotFoundError: If framework not found.
            ControlNotFoundError: If control not found.
        """
        framework = self.get_framework(framework_id)
        
        for control in framework.controls:
            if isinstance(control, dict) and control.get("id") == control_id:
                return control
        
        raise ControlNotFoundError(f"Control not found: {control_id} in {framework_id}")
    
    def list_frameworks(self, tenant_id: str | None = None) -> list[Framework]:
        """
        List all frameworks, optionally filtered by tenant.
        
        Args:
            tenant_id: Optional tenant ID to include custom frameworks.
            
        Returns:
            List of Framework objects.
        """
        frameworks = list(self._frameworks.values())
        
        if tenant_id and tenant_id in self._custom_frameworks:
            frameworks.extend(self._custom_frameworks[tenant_id].values())
        
        return frameworks
    
    def list_controls(self, framework_id: str) -> list[dict[str, Any]]:
        """
        List all controls in a framework.
        
        Args:
            framework_id: ID of the framework.
            
        Returns:
            List of control definitions.
        """
        framework = self.get_framework(framework_id)
        return framework.controls
    
    async def add_custom_framework(
        self,
        tenant_id: str,
        framework: Framework
    ) -> Framework:
        """
        Add a custom framework for a tenant.
        
        Args:
            tenant_id: ID of the tenant.
            framework: Custom framework to add.
            
        Returns:
            Added framework.
        """
        if tenant_id not in self._custom_frameworks:
            self._custom_frameworks[tenant_id] = {}
        
        framework.is_custom = True
        framework.tenant_id = tenant_id
        
        self._custom_frameworks[tenant_id][framework.id] = framework
        
        # Create version record
        if framework.id not in self._framework_versions:
            self._framework_versions[framework.id] = []
        
        self._framework_versions[framework.id].append(
            FrameworkVersion(
                id=f"{framework.id}_v{len(self._framework_versions[framework.id]) + 1}",
                framework_id=framework.id,
                version=framework.version,
                change_summary="Custom framework created",
                created_by=tenant_id,
                created_at=datetime.utcnow()
            )
        )
        
        return framework
    
    async def update_framework(
        self,
        framework_id: str,
        updates: dict[str, Any],
        tenant_id: str | None = None
    ) -> Framework:
        """
        Update a framework (creates new version).
        
        Args:
            framework_id: ID of the framework.
            updates: Dictionary of fields to update.
            tenant_id: Tenant ID (required for custom frameworks).
            
        Returns:
            Updated framework.
            
        Raises:
            FrameworkNotFoundError: If framework not found.
        """
        # Check if custom framework
        if tenant_id and framework_id in self._custom_frameworks.get(tenant_id, {}):
            framework = self._custom_frameworks[tenant_id][framework_id]
        elif framework_id in self._frameworks:
            # Seed frameworks can't be modified
            raise FrameworkRegistryError("Seed frameworks cannot be modified")
        else:
            raise FrameworkNotFoundError(f"Framework not found: {framework_id}")
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(framework, key):
                setattr(framework, key, value)
        
        framework.updated_at = datetime.utcnow()
        framework.version = self._bump_version(framework.version)
        
        # Create new version record
        versions = self._framework_versions.get(framework_id, [])
        versions.append(
            FrameworkVersion(
                id=f"{framework_id}_v{len(versions) + 1}",
                framework_id=framework_id,
                version=framework.version,
                change_summary=updates.get("change_summary", "Framework updated"),
                created_by=tenant_id,
                created_at=datetime.utcnow(),
                previous_version=versions[-1].version if versions else None
            )
        )
        self._framework_versions[framework_id] = versions
        
        return framework
    
    def get_framework_versions(self, framework_id: str) -> list[FrameworkVersion]:
        """Get version history for a framework."""
        return self._framework_versions.get(framework_id, [])
    
    def get_controls_by_category(
        self,
        framework_id: str,
        category: str
    ) -> list[dict[str, Any]]:
        """
        Get all controls in a category.
        
        Args:
            framework_id: ID of the framework.
            category: Category name.
            
        Returns:
            List of control definitions.
        """
        framework = self.get_framework(framework_id)
        return [
            control for control in framework.controls
            if isinstance(control, dict) and control.get("category") == category
        ]
    
    def _bump_version(self, version: str) -> str:
        """Bump minor version number."""
        try:
            parts = version.split(".")
            if len(parts) >= 2:
                parts[1] = str(int(parts[1]) + 1)
                return ".".join(parts)
        except (ValueError, IndexError):
            pass
        return version
    
    async def export_framework(self, framework_id: str) -> dict[str, Any]:
        """
        Export a framework as JSON-serializable dict.
        
        Args:
            framework_id: ID of the framework.
            
        Returns:
            Framework as dictionary.
        """
        framework = self.get_framework(framework_id)
        return {
            "id": framework.id,
            "name": framework.name,
            "version": framework.version,
            "description": framework.description,
            "metadata": framework.metadata,
            "controls": framework.controls,
            "is_custom": framework.is_custom,
        }
    
    def search_controls(
        self,
        query: str,
        framework_ids: list[str] | None = None
    ) -> list[tuple[str, dict[str, Any]]]:
        """
        Search controls across frameworks.
        
        Args:
            query: Search query string.
            framework_ids: Optional list of framework IDs to search.
            
        Returns:
            List of (framework_id, control) tuples.
        """
        results = []
        query_lower = query.lower()
        
        frameworks_to_search = framework_ids or list(self._frameworks.keys())
        
        for fw_id in frameworks_to_search:
            try:
                framework = self.get_framework(fw_id)
                for control in framework.controls:
                    if isinstance(control, dict):
                        control_text = f"{control.get('id', '')} {control.get('name', '')} {control.get('description', '')}".lower()
                        if query_lower in control_text:
                            results.append((fw_id, control))
            except FrameworkNotFoundError:
                continue
        
        return results


# Global registry instance
registry = FrameworkRegistry()
