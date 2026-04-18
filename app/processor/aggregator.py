from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.database import db

logger = logging.getLogger(__name__)


def generate_daily_summary(date_str: str | None = None) -> None:
    if date_str is None:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        date_str = yesterday.strftime("%Y-%m-%d")

    conn = db.get_connection()
    try:
        services = conn.execute("SELECT service_id FROM services").fetchall()

        for svc in services:
            service_id = svc["service_id"]

            start = f"{date_str}T00:00:00+00:00"
            end = f"{date_str}T23:59:59+00:00"

            traffic = conn.execute(
                "SELECT COALESCE(SUM(lan_rx_bytes),0) as lan_rx, COALESCE(SUM(lan_tx_bytes),0) as lan_tx, COALESCE(SUM(wan_rx_bytes),0) as wan_rx, COALESCE(SUM(wan_tx_bytes),0) as wan_tx FROM traffic_records WHERE service_id=? AND timestamp>=? AND timestamp<=?",
                (service_id, start, end),
            ).fetchone()

            conn_stats = conn.execute(
                "SELECT COALESCE(MAX(wan_connections),0) as peak, COALESCE(AVG(wan_connections),0) as avg FROM connection_records WHERE service_id=? AND timestamp>=? AND timestamp<=?",
                (service_id, start, end),
            ).fetchone()

            conn.execute(
                "INSERT OR REPLACE INTO daily_summaries (date, service_id, lan_rx_bytes, lan_tx_bytes, wan_rx_bytes, wan_tx_bytes, peak_wan_connections, avg_wan_connections) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    date_str,
                    service_id,
                    traffic["lan_rx"],
                    traffic["lan_tx"],
                    traffic["wan_rx"],
                    traffic["wan_tx"],
                    conn_stats["peak"],
                    conn_stats["avg"],
                ),
            )

        conn.commit()
        logger.info("Daily summary generated for %s", date_str)
    finally:
        conn.close()
