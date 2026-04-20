import json
from pathlib import Path
from typing import Optional

_DATA_PATH = Path(__file__).parent.parent / "data" / "fault_codes.json"
_fault_data: list[dict] = []
_by_spn: dict[int, dict] = {}


def _load() -> None:
    global _fault_data, _by_spn
    if _fault_data:
        return
    _fault_data = json.loads(_DATA_PATH.read_text())
    _by_spn = {f["spn"]: f for f in _fault_data}


def parse_fault_code(code: str) -> tuple[int, int]:
    """Parse 'SPN 4334 FMI 18' -> (4334, 18)"""
    parts = code.upper().split()
    spn = int(parts[parts.index("SPN") + 1])
    fmi = int(parts[parts.index("FMI") + 1]) if "FMI" in parts else 0
    return spn, fmi


def lookup_fault(spn: int) -> Optional[dict]:
    _load()
    return _by_spn.get(spn)
