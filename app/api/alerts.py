from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.database import db

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    limit: int = Query(100, ge=1, le=1000),
    _user: str = Depends(get_current_user),
):
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT a.*, s.name as service_name FROM alert_records a LEFT JOIN services s ON a.service_id=s.service_id ORDER BY a.triggered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/config")
async def get_alert_config(_user: str = Depends(get_current_user)):
    conn = db.get_connection()
    try:
        rows = conn.execute("SELECT * FROM alert_config ORDER BY rule_id").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.put("/config")
async def update_alert_config(configs: list[dict], _user: str = Depends(get_current_user)):
    conn = db.get_connection()
    try:
        for c in configs:
            conn.execute(
                "UPDATE alert_config SET threshold=?, window_minutes=?, enabled=? WHERE rule_id=?",
                (c.get("threshold"), c.get("window_minutes"), c.get("enabled", 1), c["rule_id"]),
            )
        conn.commit()
    finally:
        conn.close()
    return {"message": "更新成功"}
