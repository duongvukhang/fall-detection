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
    # FIX: cap at bcrypt's effective 72-byte limit so validation, not the
    # hashing layer, is what rejects absurdly long input.
    password      : str = Field(min_length=8, max_length=72)
    facility_name : str = Field(min_length=2, max_length=255)
    ward_unit     : Optional[str] = Field(default=None, max_length=128)


class UserLoginRequest(BaseModel):
    email    : EmailStr
    password : str = Field(max_length=72)


class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"


class UserPublic(BaseModel):
    """
    Safe-to-repeat-anywhere user profile. Deliberately does NOT include
    `api_token` — that's a long-lived bearer credential for edge devices and
    should not be re-emitted on every `/auth/me` call. See UserRegisterOut.
    """
    id            : int
    email         : str
    facility_name : str
    ward_unit     : Optional[str]
    created_at    : datetime

    model_config = {"from_attributes": True}


class UserRegisterOut(UserPublic):
    """Returned once, at registration time, so the operator can copy the
    edge-device API key. Never returned again after this."""
    api_token: str


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
    patient_track_id  : int  = Field(ge=0)
    event_type        : str  = Field(pattern=r"^(FLOOR_FALL|BED_EXIT)$")
    # FIX: unbounded free-text fields from an edge device are a cheap DoS
    # vector (storage bloat + fan-out to every open dashboard WS connection).
    kinematics        : Optional[str] = Field(default=None, max_length=256)
    primary_impact    : Optional[str] = Field(default=None, max_length=64)
    head_strike_risk  : Optional[str] = Field(default=None, max_length=32)
    image_url         : Optional[str] = Field(default=None, max_length=2048)

    @field_validator("event_type")
    @classmethod
    def upper_event_type(cls, v: str) -> str:
        return v.upper()

    @field_validator("image_url")
    @classmethod
    def image_url_scheme(cls, v: Optional[str]) -> Optional[str]:
        if v and not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("image_url must be an http(s) URL")
        return v


class TelemetryResponse(BaseModel):
    event_id  : int
    status    : str = "accepted"
    timestamp : datetime

    model_config = {"from_attributes": True}


class HeartbeatIngest(BaseModel):
    room_number: str = Field(max_length=32)
    status: str = Field(default="ONLINE", pattern=r"^(ONLINE|DEGRADED)$")


class HeartbeatResponse(BaseModel):
    status: str = "ack"
    server_time: datetime


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