from __future__ import annotations

import ipaddress
import logging
import re
import subprocess
from datetime import datetime, timezone

from app.database import db

logger = logging.getLogger(__name__)

_LAN_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def _is_lan_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in _LAN_NETWORKS)
    except ValueError:
        return False


def _run_ss() -> list[dict]:
    try:
        result = subprocess.run(
            ["ss", "-tunap"],
            capture_output=True, text=True, timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("ss command failed: %s", e)
        return []

    connections = []
    for line in result.stdout.split("\n")[1:]:
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        if len(parts) < 6:
            continue

        proto = parts[0]
        local = parts[4]
        remote = parts[5]
        pid = None

        for i, p in enumerate(parts):
            if p.startswith("pid="):
                try:
                    pid = int(p.split("=")[1].rstrip(","))
                except ValueError:
                    pass

        if not remote or remote == "*":
            continue

        remote_ip = remote.rsplit(":", 1)[0]
        remote_ip = re.sub(r"\[|\]", "", remote_ip)

        connections.append({
            "proto": proto,
            "local": local,
            "remote_ip": remote_ip,
            "pid": pid,
        })

    return connections


def collect_connections() -> None:
    raw_conns = _run_ss()
    if not raw_conns:
        logger.info("No connection data collected")
        return

    conn = db.get_connection()
    try:
        services = conn.execute("SELECT service_id, name, pid, source FROM services WHERE status='running'").fetchall()
    finally:
        conn.close()

    pid_to_service: dict[int, str] = {}
    name_to_service: dict[str, str] = {}
    for svc in services:
        if svc["pid"]:
            pid_to_service[svc["pid"]] = svc["service_id"]
        name_to_service[svc["name"]] = svc["service_id"]

    service_counts: dict[str, dict[str, int]] = {}

    for c in raw_conns:
        service_id = pid_to_service.get(c["pid"]) if c["pid"] else None

        if not service_id:
            continue

        if service_id not in service_counts:
            service_counts[service_id] = {"lan": 0, "wan": 0}

        if _is_lan_ip(c["remote_ip"]):
            service_counts[service_id]["lan"] += 1
        else:
            service_counts[service_id]["wan"] += 1

    now = datetime.now(timezone.utc).isoformat()
    conn = db.get_connection()
    try:
        for service_id, counts in service_counts.items():
            conn.execute(
                "INSERT INTO connection_records (service_id, timestamp, lan_connections, wan_connections) VALUES (?, ?, ?, ?)",
                (service_id, now, counts["lan"], counts["wan"]),
            )
        conn.commit()
    finally:
        conn.close()

    logger.info("Connection data collected for %d services", len(service_counts))
