from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import config
from app.database import db
from app.notifier import send_feishu_alert

logger = logging.getLogger(__name__)


def check_alerts() -> None:
    conn = db.get_connection()
    try:
        rules = conn.execute("SELECT * FROM alert_config WHERE enabled=1").fetchall()

        for rule in rules:
            metric = rule["metric"]
            threshold = rule["threshold"]
            window_minutes = rule["window_minutes"]
            rule_id = rule["rule_id"]
            target_service = rule["service_id"]

            if metric == "wan_tx_bytes_1h" or metric == "wan_rx_bytes_1h":
                _check_traffic_rule(conn, rule_id, metric, threshold, window_minutes, target_service)
            elif metric == "wan_connections":
                _check_connection_rule(conn, rule_id, threshold, target_service)

    finally:
        conn.close()


def _check_traffic_rule(
    conn,
    rule_id: str,
    metric: str,
    threshold: float,
    window_minutes: int,
    target_service: Optional[str],
) -> None:
    since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()

    field = "wan_tx_bytes" if metric == "wan_tx_bytes_1h" else "wan_rx_bytes"
    label = "互联网上行" if metric == "wan_tx_bytes_1h" else "互联网下行"

    if target_service:
        services = [target_service]
    else:
        rows = conn.execute("SELECT service_id FROM services WHERE status='running'").fetchall()
        services = [r["service_id"] for r in rows]

    for service_id in services:
        row = conn.execute(
            f"SELECT COALESCE(SUM({field}),0) as total FROM traffic_records WHERE service_id=? AND timestamp>=?",
            (service_id, since),
        ).fetchone()

        if not row:
            continue

        total = row["total"]
        if total > threshold:
            _trigger_alert(conn, rule_id, service_id, total, threshold, f"{label}流量异常: {total} bytes 超过阈值 {threshold} bytes")


def _check_connection_rule(
    conn,
    rule_id: str,
    threshold: float,
    target_service: Optional[str],
) -> None:
    if target_service:
        services = [target_service]
    else:
        rows = conn.execute("SELECT service_id FROM services WHERE status='running'").fetchall()
        services = [r["service_id"] for r in rows]

    for service_id in services:
        row = conn.execute(
            "SELECT wan_connections FROM connection_records WHERE service_id=? ORDER BY timestamp DESC LIMIT 1",
            (service_id,),
        ).fetchone()

        if not row:
            continue

        count = row["wan_connections"]
        if count > threshold:
            _trigger_alert(conn, rule_id, service_id, count, threshold, f"互联网连接数异常: {count} 超过阈值 {threshold}")


def _trigger_alert(
    conn,
    rule_id: str,
    service_id: str,
    metric_value: float,
    threshold: float,
    message: str,
) -> None:
    dedup_key = f"{rule_id}:{service_id}"
    dedup_since = (datetime.now(timezone.utc) - timedelta(minutes=config.ALERT_DEDUP_MINUTES)).isoformat()

    existing = conn.execute(
        "SELECT id FROM alert_records WHERE rule_id=? AND service_id=? AND triggered_at>=?",
        (rule_id, service_id, dedup_since),
    ).fetchone()

    if existing:
        return

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO alert_records (service_id, rule_id, triggered_at, metric_value, threshold, message, notified) VALUES (?, ?, ?, ?, ?, ?, 0)",
        (service_id, rule_id, now, metric_value, threshold, message),
    )
    conn.commit()

    try:
        send_feishu_alert(service_id, rule_id, metric_value, threshold, message, now)
        conn.execute("UPDATE alert_records SET notified=1 WHERE service_id=? AND rule_id=? AND triggered_at=?", (service_id, rule_id, now))
        conn.commit()
    except Exception as e:
        logger.error("Failed to send alert notification: %s", e)
