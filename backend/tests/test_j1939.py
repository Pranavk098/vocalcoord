import pytest
from backend.tools.j1939 import parse_fault_code, lookup_fault


def test_parse_standard_fault_code():
    spn, fmi = parse_fault_code("SPN 4334 FMI 18")
    assert spn == 4334
    assert fmi == 18


def test_parse_fault_code_case_insensitive():
    spn, fmi = parse_fault_code("spn 100 fmi 1")
    assert spn == 100
    assert fmi == 1


def test_lookup_known_fault_returns_data():
    fault = lookup_fault(4334)
    assert fault is not None
    assert fault["severity"] == "red_stop"
    assert fault["warranty_code"] == "EPA_EMISSION_COVERAGE"


def test_lookup_unknown_fault_returns_none():
    fault = lookup_fault(99999)
    assert fault is None
