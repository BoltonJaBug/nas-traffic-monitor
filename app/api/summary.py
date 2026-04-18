from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.database import db

router = APIRouter(prefix="/api/daily-summary", tags=["summary"])


@router.get("")
async def list_summaries(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    _user: str = Depends(get_current_user),
):
    conn = db.get_connection()
    try:
        if start_date and end_date:
            rows = conn.execute(
                "SELECT * FROM daily_summaries WHERE date>=? AND date<=? ORDER BY date DESC, service_id",
                (start_date, end_date),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM daily_summaries ORDER BY date DESC, service_id LIMIT 500",
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/{date}")
async def daily_detail(date: str, _user: str = Depends(get_current_user)):
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM daily_summaries WHERE date=? ORDER BY wan_tx_bytes + wan_rx_bytes DESC",
            (date,),
        ).fetchall()
        total = {
            "date": date,
            "lan_rx_bytes": 0,
            "lan_tx_bytes": 0,
            "wan_rx_bytes": 0,
            "wan_tx_bytes": 0,
        }
        services = []
        for r in rows:
            d = dict(r)
            total["lan_rx_bytes"] += d["lan_rx_bytes"]
            total["lan_tx_bytes"] += d["lan_tx_bytes"]
            total["wan_rx_bytes"] += d["wan_rx_bytes"]
            total["wan_tx_bytes"] += d["wan_tx_bytes"]
            services.append(d)
        return {"total": total, "services": services}
    finally:
        conn.close()
