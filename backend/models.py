# backend/models.py
from typing import Optional, Union

from pydantic import BaseModel, Field


class DriverLocation(BaseModel):
    lat: Optional[float] = None
    lon: Optional[float] = None
    city: str


class ToolCallPayload(BaseModel):
    type: str = "tool_call"
    conversation_id: str
    tool_name: str
    parameters: dict


class FaultParameters(BaseModel):
    """Validated shape of the resolved tool-call parameters. hos_hours_remaining is
    bounded [0, 11] — the actual FMCSA 11-hour driving limit, so the bound is
    semantically correct, not just defensive. Values outside pydantic's coercion
    (e.g. "about four") or outside the bound are rejected by the caller and replaced
    with a safe default rather than reaching HOS logic."""
    fault_code: str = ""
    driver_location: Union[str, dict] = ""
    hos_hours_remaining: float = Field(default=8.0, ge=0, le=11)
    load_number: str = "FRT-28470"


class ToolCallResponse(BaseModel):
    result: str
