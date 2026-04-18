from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Optional

from app.config import config
from app.database import db

logger = logging.getLogger(__name__)

_CHAIN_PREFIX = "NASMON"


def _run_iptables(args: list[str]) -> str:
    cmd = ["iptables"] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        logger.error("iptables command failed: %s", e)
        return ""


def _get_container_ips() -> dict[str, str]:
    result = {}
    try:
        output = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}} {{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}", "$(docker ps -q)"],
            capture_output=True, text=True, timeout=15, shell=False,
        )
    except Exception:
        try:
            ps_out = subprocess.run(["docker", "ps", "-q"], capture_output=True, text=True, timeout=10).stdout.strip()
            if not ps_out:
                return result
            ids = " ".join(ps_out.split())
            output = subprocess.run(
                f'docker inspect --format "{{{{.Name}}}} {{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}} {{{{end}}}}" {ids}',
                capture_output=True, text=True, timeout=15, shell=True,
            )
        except Exception as e:
            logger.error("Failed to get container IPs: %s", e)
            return result

    for line in output.stdout.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.strip().split()
        if len(parts) >= 2:
            name = parts[0].lstrip("/")
            ip = parts[1]
            result[name] = ip
    return result


def ensure_chains() -> None:
    for chain_name in [_CHAIN_PREFIX, f"{_CHAIN_PREFIX}-OUT"]:
        _run_iptables(["-N", chain_name])
    for hook in ["FORWARD", "OUTPUT"]:
        existing = _run_iptables(["-n", "-L", hook])
        if _CHAIN_PREFIX not in existing:
            _run_iptables(["-I", hook, "-j", _CHAIN_PREFIX])

    existing_out = _run_iptables(["-n", "-L", "OUTPUT"])
    if f"{_CHAIN_PREFIX}-OUT" not in existing_out:
        _run_iptables(["-I", "OUTPUT", "-j", f"{_CHAIN_PREFIX}-OUT"])


def sync_rules() -> None:
    ensure_chains()
    container_ips = _get_container_ips()

    conn = db.get_connection()
    try:
        running = conn.execute("SELECT service_id, name FROM services WHERE source='docker' AND status='running'").fetchall()
    finally:
        conn.close()

    existing_forward = _parse_chain_rules(_CHAIN_PREFIX)
    existing_out = _parse_chain_rules(f"{_CHAIN_PREFIX}-OUT")

    for row in running:
        name = row["name"]
        ip = container_ips.get(name)
        if not ip:
            continue

        for direction, chain, existing in [
            ("in", _CHAIN_PREFIX, existing_forward),
            ("out", f"{_CHAIN_PREFIX}-OUT", existing_out),
        ]:
            for net_type, dst_match in [("lan", config.LAN_NETWORKS), ("wan", None)]:
                comment = f"{name}_{direction}_{net_type}"
                if comment in existing:
                    continue

                if net_type == "lan":
                    for cidr in dst_match:
                        if direction == "in":
                            _run_iptables(["-A", chain, "-s", ip, "-d", cidr, "-m", "comment", "--comment", comment])
                        else:
                            _run_iptables(["-A", chain, "-d", ip, "-s", cidr, "-m", "comment", "--comment", comment])
                else:
                    lan_excludes = ",".join(config.LAN_NETWORKS)
                    if direction == "in":
                        _run_iptables(["-A", chain, "-s", ip, "!", "-d", lan_excludes.split(",")[0], "-m", "comment", "--comment", comment])
                        for i, cidr in enumerate(config.LAN_NETWORKS):
                            _run_iptables(["-D", chain, "-s", ip, "!", "-d", cidr, "-m", "comment", "--comment", comment])
                            if i == 0:
                                _run_iptables(["-A", chain, "-s", ip, "-m", "comment", "--comment", comment])
                    else:
                        _run_iptables(["-A", chain, "-d", ip, "-m", "comment", "--comment", comment])
                        for cidr in config.LAN_NETWORKS:
                            _run_iptables(["-I", chain, "-d", ip, "-s", cidr, "-m", "comment", "--comment", f"{name}_{direction}_lan"])

    logger.info("Traffic rules synced for %d containers", len(running))


def _parse_chain_rules(chain: str) -> set[str]:
    output = _run_iptables(["-n", "-v", "-L", chain])
    rules = set()
    for line in output.split("\n"):
        for match in re.finditer(r'comment\s+"([^"]+)"', line):
            rules.add(match.group(1))
    return rules


def _read_counters() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for chain_name, direction in [(_CHAIN_PREFIX, "in"), (f"{_CHAIN_PREFIX}-OUT", "out")]:
        output = _run_iptables(["-n", "-v", "-L", chain_name])
        for line in output.split("\n"):
            match = re.search(r'comment\s+"([^"]+)"', line)
            if not match:
                continue
            comment = match.group(1)
            parts = line.strip().split()
            if len(parts) < 2:
                continue
            try:
                bytes_val = int(parts[1])
            except ValueError:
                continue
            if comment not in result:
                result[comment] = {}
            result[comment][f"{direction}_bytes"] = bytes_val
    return result


_last_counters: dict[str, dict[str, int]] = {}


def collect_traffic() -> None:
    global _last_counters

    sync_rules()
    current = _read_counters()

    now = datetime.now(timezone.utc).isoformat()
    conn = db.get_connection()
    try:
        for comment, counters in current.items():
            parts = comment.split("_")
            if len(parts) < 3:
                continue
            name = parts[0]
            direction = parts[1]
            net_type = parts[2]

            service_id = f"docker-{name}"

            key = f"{direction}_bytes"
            current_val = counters.get(key, 0)
            last_val = _last_counters.get(comment, {}).get(key, 0)
            delta = current_val - last_val

            if delta < 0:
                logger.warning("Counter reset detected for %s, skipping", comment)
                delta = 0

            field_map = {
                "in_lan": "lan_rx_bytes",
                "in_wan": "wan_rx_bytes",
                "out_lan": "lan_tx_bytes",
                "out_wan": "wan_tx_bytes",
            }
            field_key = f"{direction}_{net_type}"
            if field_key not in field_map:
                continue

            db_field = field_map[field_key]

            existing = conn.execute(
                "SELECT id, lan_rx_bytes, lan_tx_bytes, wan_rx_bytes, wan_tx_bytes FROM traffic_records WHERE service_id=? AND timestamp=?",
                (service_id, now),
            ).fetchone()

            if existing:
                vals = dict(existing)
                vals[db_field] = vals[db_field] + delta
                conn.execute(
                    "UPDATE traffic_records SET lan_rx_bytes=?, lan_tx_bytes=?, wan_rx_bytes=?, wan_tx_bytes=? WHERE id=?",
                    (vals["lan_rx_bytes"], vals["lan_tx_bytes"], vals["wan_rx_bytes"], vals["wan_tx_bytes"], vals["id"]),
                )
            else:
                init = {"lan_rx_bytes": 0, "lan_tx_bytes": 0, "wan_rx_bytes": 0, "wan_tx_bytes": 0}
                init[db_field] = delta
                conn.execute(
                    "INSERT INTO traffic_records (service_id, timestamp, lan_rx_bytes, lan_tx_bytes, wan_rx_bytes, wan_tx_bytes) VALUES (?, ?, ?, ?, ?, ?)",
                    (service_id, now, init["lan_rx_bytes"], init["lan_tx_bytes"], init["wan_rx_bytes"], init["wan_tx_bytes"]),
                )

        conn.commit()
    finally:
        conn.close()

    _last_counters = current
    logger.info("Traffic data collected")
