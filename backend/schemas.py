"""
SafeWatch — Pydantic v2 Schemas
Input validation, API response shapes, and telemetry payload contracts.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Auth / Account
# ─────────────────────────────────────────────────────────────────────────────

class UserRegisterRequest(BaseModel):
    email         : EmailStr
    password      : str = Field(min_length=8)
    facility_name : str = Field(min_length=2, max_length=255)
    ward_unit     : Optional[str] = Field(default=None, max_length=128)


class UserLoginRequest(BaseModel):
    email    : EmailStr
    password : str


class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"


class UserPublic(BaseModel):
    id            : int
    email         : str
    facility_name : str
    ward_unit     : Optional[str]
    api_token     : str            # shown once on registration; used by edge devices
    created_at    : datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry — Edge → Cloud  (authenticated via X-API-KEY header)
# ─────────────────────────────────────────────────────────────────────────────

class TelemetryIngest(BaseModel):
    """
    JSON payload posted by the edge device to /api/v1/telemetry/events.
    image_url is optional: the edge uploads the JPEG separately to object
    storage and passes the resulting URL here (or omits it).
    """
    room_number       : str  = Field(max_length=32)
    patient_track_id  : int
    event_type        : str  = Field(pattern=r"^(FLOOR_FALL|BED_EXIT)$")
    kinematics        : Optional[str] = None
    primary_impact    : Optional[str] = None
    head_strike_risk  : Optional[str] = None
    image_url         : Optional[str] = None

    @field_validator("event_type")
    @classmethod
    def upper_event_type(cls, v: str) -> str:
        return v.upper()


class TelemetryResponse(BaseModel):
    event_id  : int
    status    : str = "accepted"
    timestamp : datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Event — Dashboard reads
# ─────────────────────────────────────────────────────────────────────────────

class EventOut(BaseModel):
    id               : int
    room_number      : str
    patient_track_id : int
    event_type       : str
    kinematics       : Optional[str]
    primary_impact   : Optional[str]
    head_strike_risk : Optional[str]
    image_url        : Optional[str]
    timestamp        : datetime

    model_config = {"from_attributes": True}


class EventListResponse(BaseModel):
    total  : int
    page   : int
    limit  : int
    events : List[EventOut]


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard — KPI & Chart aggregations
# ─────────────────────────────────────────────────────────────────────────────

class KPIResponse(BaseModel):
    active_protected_beds  : int
    total_falls_24h        : int
    active_bed_exit_warnings: int


class HourlyBucket(BaseModel):
    hour  : str   # "2024-01-15T14:00"
    falls : int
    exits : int


class FallTypologySlice(BaseModel):
    label : str
    count : int


class DashboardAggregations(BaseModel):
    kpi             : KPIResponse
    hourly          : List[HourlyBucket]
    fall_typology   : List[FallTypologySlice]
