"""
Framework Loader for ACMP.

Parses, validates, and versions framework JSON files.
"""
import json
from pathlib import Path
from typing import Any
from datetime import datetime

import jsonschema
from server.models.framework import Framework


FRAMEWORK_SCHEMA = {
    "type": "object",
    "required": ["id", "name", "version", "controls"],
    "properties": {
        "id": {"type": "string"},
        "name": {"type": "string"},
        "version": {"type": "string"},
        "description": {"type": "string"},
        "metadata": {"type": "object"},
        "controls": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description", "category", "evidence_types", "rule_type", "rule_config", "severity"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "category": {"type": "string"},
                    "evidence_types": {"type": "array", "items": {"type": "string"}},
                    "rule_type": {"type": "string"},
                    "rule_config": {"type": "object"},
                    "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
                }
            }
        }
    }
}


class FrameworkLoadError(Exception):
    """Raised when framework loading fails."""
    pass


class FrameworkValidationError(Exception):
    """Raised when framework validation fails."""
    pass


def load_framework_json(file_path: Path) -> dict[str, Any]:
    """Load and parse a framework JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise FrameworkLoadError(f"Invalid JSON in {file_path}: {e}")
    except FileNotFoundError:
        raise FrameworkLoadError(f"Framework file not found: {file_path}")


def validate_framework(data: dict[str, Any], file_path: Path) -> None:
    """Validate framework data against schema."""
    try:
        jsonschema.validate(instance=data, schema=FRAMEWORK_SCHEMA)
    except jsonschema.ValidationError as e:
        raise FrameworkValidationError(f"Framework validation failed for {file_path}: {e.message}")


def parse_framework(data: dict[str, Any]) -> Framework:
    """Convert raw framework data to Framework model."""
    return Framework(
        id=data["id"],
        name=data["name"],
        version=data["version"],
        description=data.get("description"),
        metadata=data.get("metadata", {}),
        controls=data.get("controls", []),
        is_custom=data.get("is_custom", False),
        updated_at=datetime.utcnow()
    )


def load_framework_from_file(file_path: Path) -> Framework:
    """Load, validate, and parse a framework file."""
    data = load_framework_json(file_path)
    validate_framework(data, file_path)
    return parse_framework(data)


def load_all_seed_frameworks(frameworks_dir: Path | None = None) -> list[Framework]:
    """Load all seed frameworks from the frameworks directory."""
    if frameworks_dir is None:
        frameworks_dir = Path(__file__).parent.parent / "frameworks"
    
    frameworks = []
    for file_path in frameworks_dir.glob("*.json"):
        try:
            framework = load_framework_from_file(file_path)
            frameworks.append(framework)
        except (FrameworkLoadError, FrameworkValidationError) as e:
            # Log error but continue loading other frameworks
            print(f"Warning: Failed to load {file_path}: {e}")
    
    return frameworks


def get_control_by_id(framework: Framework, control_id: str) -> dict[str, Any] | None:
    """Get a specific control from a framework by ID."""
    for control in framework.controls:
        if isinstance(control, dict) and control.get("id") == control_id:
            return control
    return None


def get_controls_by_category(framework: Framework, category: str) -> list[dict[str, Any]]:
    """Get all controls in a specific category."""
    return [
        control for control in framework.controls
        if isinstance(control, dict) and control.get("category") == category
    ]
