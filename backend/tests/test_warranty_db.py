# backend/tests/test_warranty_db.py
from backend.tools.warranty_db import lookup_warranty


def test_lookup_known_warranty_code():
    result = lookup_warranty("EPA_EMISSION_COVERAGE")
    assert result is not None
    assert result["claim_value"] == 340
    assert result["labor_included"] is True


def test_lookup_powertrain_warranty():
    result = lookup_warranty("POWERTRAIN_BASIC")
    assert result is not None
    assert result["claim_value"] == 95


def test_lookup_unknown_code_returns_none():
    result = lookup_warranty("NONEXISTENT_CODE")
    assert result is None
