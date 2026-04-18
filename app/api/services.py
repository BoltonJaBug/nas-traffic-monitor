from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.database import db

router = APIRouter(prefix="/api/services", tags=["services"])


@router.get("")
async def list_services(_user: str = Depends(get_current_user)):
    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT * FROM services ORDER BY status, name").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{service_id}/traffic")
async def service_traffic(
    service_id: str,
    start: Optional[str] = Query(None, description="ISO8601 start time"),
    end: Optional[str] = Query(None, description="ISO8601 end time"),
    _user: str = Depends(get_current_user),
):
    conn = db.get_connection()
    try:
        if start and end:
            rows = conn.execute(
                "SELECT * FROM traffic_records WHERE service_id=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp",
                (service_id, start, end),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM traffic_records WHERE service_id=? ORDER BY timestamp DESC LIMIT 288",
                (service_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{service_id}/connections")
async def service_connections(
    service_id: str,
    start: Optional[str] = Query(None, description="ISO8601 start time"),
    end: Optional[str] = Query(None, description="ISO8601 end time"),
    _user: str = Depends(get_current_user),
):
    conn = db.get_connection()
    try:
        if start and end:
            rows = conn.execute(
                "SELECT * FROM connection_records WHERE service_id=? AND timestamp>=? AND timestamp<=? ORDER BY timestamp",
                (service_id, start, end),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM connection_records WHERE service_id=? ORDER BY timestamp DESC LIMIT 288",
                (service_id,),
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
