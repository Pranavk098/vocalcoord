# backend/models.py
from pydantic import BaseModel
from typing import Optional


class DriverLocation(BaseModel):
    lat: float
    lon: float
    city: str


class ToolCallPayload(BaseModel):
    type: str = "tool_call"
    conversation_id: str
    tool_name: str
    parameters: dict


class ToolCallResponse(BaseModel):
    result: str
