from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.database import db

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    elif value < 1024 ** 2:
        return f"{value / 1024:.1f} KB"
    elif value < 1024 ** 3:
        return f"{value / 1024 ** 2:.1f} MB"
    else:
        return f"{value / 1024 ** 3:.2f} GB"


@router.get("")
async def dashboard(_user: str = Depends(get_current_user)):
    conn = db.get_connection()
    try:
        services = conn.execute("SELECT * FROM services ORDER BY status, name").fetchall()

        now = datetime.now(timezone.utc)
        hour_ago = (now - timedelta(hours=1)).isoformat()

        recent_traffic = {}
        rows = conn.execute(
            "SELECT service_id, SUM(wan_tx_bytes) as wan_tx, SUM(wan_rx_bytes) as wan_rx FROM traffic_records WHERE timestamp>=? GROUP BY service_id",
            (hour_ago,),
        ).fetchall()
        for r in rows:
            recent_traffic[r["service_id"]] = {"wan_tx": r["wan_tx"], "wan_rx": r["wan_rx"]}

        recent_connections = {}
        rows = conn.execute(
            "SELECT service_id, wan_connections FROM connection_records WHERE timestamp=(SELECT MAX(timestamp) FROM connection_records) GROUP BY service_id",
        ).fetchall()
        for r in rows:
            recent_connections[r["service_id"]] = r["wan_connections"]

        alerts = conn.execute(
            "SELECT a.*, s.name as service_name FROM alert_records a LEFT JOIN services s ON a.service_id=s.service_id ORDER BY a.triggered_at DESC LIMIT 10",
        ).fetchall()

        service_list = []
        for svc in services:
            sid = svc["service_id"]
            traffic = recent_traffic.get(sid, {"wan_tx": 0, "wan_rx": 0})
            service_list.append({
                "service_id": sid,
                "name": svc["name"],
                "source": svc["source"],
                "status": svc["status"],
                "wan_tx_1h": traffic["wan_tx"],
                "wan_rx_1h": traffic["wan_rx"],
                "wan_connections": recent_connections.get(sid, 0),
            })

        return {
            "services": service_list,
            "recent_alerts": [dict(a) for a in alerts],
            "total_services": len(services),
            "running_services": sum(1 for s in services if s["status"] == "running"),
        }
    finally:
        conn.close()
