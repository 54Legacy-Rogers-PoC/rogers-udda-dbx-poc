"""Shared constants and helper utilities for schema-creation request scripts."""

from __future__ import annotations

from typing import Any

ALLOWED_ENVIRONMENTS = {"Production", "Development", "QA/Test"}
ALLOWED_SANDBOX_SELECTION = {"New Sandbox", "Existing Sandbox"}
EXPECTED_PLATFORM = "Databricks"
EXPECTED_REQUEST_TYPE = "Self Serve Request"
EXPECTED_ASSIGNMENT_GROUP = "RSO-EDA CLOUD DEPLOYMENT"

ENVIRONMENT_MAP = {
    "production": "PRD",
    "development": "DEV",
    "qa/test": "QA",
}

SANDBOX_MODE_MAP = {
    "new sandbox": "new",
    "existing sandbox": "existing",
}


def normalize(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_email(value: Any) -> str:
    email = normalize(value)
    return email.lower() if "@" in email else email


def as_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    normalized = normalize(value).lower()
    return normalized in {"1", "true", "yes", "y"}
