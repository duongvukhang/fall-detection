"""
SafeWatch — API Route Handlers
  /api/v1/auth/*         — registration, login
  /api/v1/telemetry/*    — edge-device ingest (X-API-KEY)
  /api/v1/dashboard/*    — KPIs, charts, audit trail (JWT)
  /api/v1/ws/{user_id}   — WebSocket real-time push
"""

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
import json
import asyncio

from database import get_db
from models import Event, User
from schemas import (
    DashboardAggregations,
    EventListResponse,
    EventOut,
    FallTypologySlice,
    HourlyBucket,
    KPIResponse,
    TelemetryIngest,
    TelemetryResponse,
    TokenResponse,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
)
from security import (
    create_access_token,
    decode_access_token,
    get_current_user,
    get_facility_from_api_key,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/v1")


# ─────────────────────────────────────────────────────────────────────────────
# WebSocket Connection Manager
# ─────────────────────────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        # Maps user_id → list of active WebSocket connections
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        conns = self.active.get(user_id, [])
        if ws in conns:
            conns.remove(ws)

    async def push(self, user_id: int, payload: dict):
        """Push JSON payload to all connections belonging to a tenant."""
        for ws in list(self.active.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.disconnect(user_id, ws)


manager = ConnectionManager()


# ─────────────────────────────────────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/auth/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(body: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email         = body.email,
        password_hash = hash_password(body.password),
        facility_name = body.facility_name,
        ward_unit     = body.ward_unit,
        api_token     = User.generate_api_token(),
    )
    db.add(user)
    await db.flush()
    return UserPublic.model_validate(user)


@router.post("/auth/login", response_model=TokenResponse)
async def login(body: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user   = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return TokenResponse(access_token=create_access_token(user.id, user.facility_name))


@router.get("/auth/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)


# ─────────────────────────────────────────────────────────────────────────────
# TELEMETRY INGEST  (edge devices → cloud)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/telemetry/events",
    response_model=TelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(
    body    : TelemetryIngest,
    facility: User         = Depends(get_facility_from_api_key),
    db      : AsyncSession = Depends(get_db),
):
    event = Event(
        user_id          = facility.id,
        room_number      = body.room_number,
        patient_track_id = body.patient_track_id,
        event_type       = body.event_type,
        kinematics       = body.kinematics,
        primary_impact   = body.primary_impact,
        head_strike_risk = body.head_strike_risk,
        image_url        = body.image_url,
    )
    db.add(event)
    await db.flush()

    # ── Real-time push to all dashboard tabs for this tenant ──────────────
    await manager.push(facility.id, {
        "type"  : "NEW_EVENT",
        "event" : {
            "id"               : event.id,
            "room_number"      : event.room_number,
            "patient_track_id" : event.patient_track_id,
            "event_type"       : event.event_type,
            "kinematics"       : event.kinematics,
            "primary_impact"   : event.primary_impact,
            "head_strike_risk" : event.head_strike_risk,
            "image_url"        : event.image_url,
            "timestamp"        : event.timestamp.isoformat(),
        },
    })

    return TelemetryResponse(event_id=event.id, timestamp=event.timestamp)


# ─────────────────────────────────────────────────────────────────────────────
# WEBSOCKET  (dashboard real-time feed)
# ─────────────────────────────────────────────────────────────────────────────

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    user_id : int,
    ws      : WebSocket,
    token   : str = Query(...),
    db      : AsyncSession = Depends(get_db),
):
    """
    Authenticated WebSocket.
    Connect: wss://your-domain/api/v1/ws/{user_id}?token=<JWT>
    Messages pushed: { type: "NEW_EVENT", event: {...} }
                     { type: "PING" }  ← keepalive every 25 s
    """
    # Validate JWT before accepting
    uid = decode_access_token(token)
    if uid is None or uid != user_id:
        await ws.close(code=4001)
        return

    await manager.connect(user_id, ws)
    try:
        while True:
            # Keepalive ping every 25 s; client should pong (or just keep open)
            await asyncio.sleep(25)
            await ws.send_text(json.dumps({"type": "PING"}))
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)
    except Exception:
        manager.disconnect(user_id, ws)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD — KPIs
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard/kpi", response_model=KPIResponse)
async def dashboard_kpi(
    current_user: User         = Depends(get_current_user),
    db          : AsyncSession = Depends(get_db),
):
    window_start = datetime.now(timezone.utc) - timedelta(hours=24)

    falls_24h = await db.scalar(
        select(func.count(Event.id)).where(
            Event.user_id    == current_user.id,
            Event.event_type == "FLOOR_FALL",
            Event.timestamp  >= window_start,
        )
    )

    active_window = datetime.now(timezone.utc) - timedelta(minutes=5)
    bed_exit_rooms = await db.scalar(
        select(func.count(func.distinct(Event.room_number))).where(
            Event.user_id    == current_user.id,
            Event.event_type == "BED_EXIT",
            Event.timestamp  >= active_window,
        )
    )

    active_beds = await db.scalar(
        select(func.count(func.distinct(Event.room_number))).where(
            Event.user_id   == current_user.id,
            Event.timestamp >= window_start,
        )
    )

    return KPIResponse(
        active_protected_beds    = active_beds or 0,
        total_falls_24h          = falls_24h or 0,
        active_bed_exit_warnings = bed_exit_rooms or 0,
    )


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD — Chart aggregations
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard/aggregations", response_model=DashboardAggregations)
async def dashboard_aggregations(
    current_user: User         = Depends(get_current_user),
    db          : AsyncSession = Depends(get_db),
):
    window_start = datetime.now(timezone.utc) - timedelta(hours=24)

    kpi = (await dashboard_kpi(current_user=current_user, db=db))

    rows = (await db.execute(
        select(Event.timestamp, Event.event_type).where(
            Event.user_id   == current_user.id,
            Event.timestamp >= window_start,
        )
    )).fetchall()

    hourly_map: dict[str, dict] = {}
    for ts, etype in rows:
        bucket = ts.strftime("%Y-%m-%dT%H:00")
        if bucket not in hourly_map:
            hourly_map[bucket] = {"falls": 0, "exits": 0}
        if etype == "FLOOR_FALL":
            hourly_map[bucket]["falls"] += 1
        else:
            hourly_map[bucket]["exits"] += 1

    hourly = [
        HourlyBucket(hour=h, falls=v["falls"], exits=v["exits"])
        for h, v in sorted(hourly_map.items())
    ]

    fall_rows = (await db.execute(
        select(Event.kinematics).where(
            Event.user_id    == current_user.id,
            Event.event_type == "FLOOR_FALL",
            Event.timestamp  >= window_start,
            Event.kinematics.isnot(None),
        )
    )).scalars().all()

    typology_map: dict[str, int] = {}
    for k in fall_rows:
        typology_map[k] = typology_map.get(k, 0) + 1

    fall_typology = [
        FallTypologySlice(label=label, count=count)
        for label, count in typology_map.items()
    ]

    return DashboardAggregations(
        kpi=kpi, hourly=hourly, fall_typology=fall_typology
    )


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD — Audit trail (paginated)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard/events", response_model=EventListResponse)
async def list_events(
    page        : int          = Query(default=1, ge=1),
    limit       : int          = Query(default=25, le=100),
    event_type  : str | None   = Query(default=None),
    room_number : str | None   = Query(default=None),
    current_user: User         = Depends(get_current_user),
    db          : AsyncSession = Depends(get_db),
):
    q = select(Event).where(Event.user_id == current_user.id)
    if event_type:
        q = q.where(Event.event_type == event_type.upper())
    if room_number:
        q = q.where(Event.room_number == room_number)

    total_result = await db.scalar(
        select(func.count()).select_from(q.subquery())
    )

    events = (await db.execute(
        q.order_by(Event.timestamp.desc())
         .offset((page - 1) * limit)
         .limit(limit)
    )).scalars().all()

    return EventListResponse(
        total  = total_result or 0,
        page   = page,
        limit  = limit,
        events = [EventOut.model_validate(e) for e in events],
    )


@router.get("/dashboard/events/{event_id}", response_model=EventOut)
async def get_event(
    event_id    : int,
    current_user: User         = Depends(get_current_user),
    db          : AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Event).where(Event.id == event_id, Event.user_id == current_user.id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return EventOut.model_validate(event)