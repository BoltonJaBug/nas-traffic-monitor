from __future__ import annotations

import json
import logging

import httpx

from app.config import config
from app.database import db

logger = logging.getLogger(__name__)


def get_webhook_url() -> str:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key='feishu_webhook_url'").fetchone()
        if row:
            return row["value"]
    finally:
        conn.close()
    return config.FEISHU_WEBHOOK_URL


def set_webhook_url(url: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('feishu_webhook_url', ?)", (url,))
        conn.commit()
    finally:
        conn.close()


def _format_bytes(value: float) -> str:
    if value < 1024:
        return f"{value:.0f} B"
    elif value < 1024 ** 2:
        return f"{value / 1024:.2f} KB"
    elif value < 1024 ** 3:
        return f"{value / 1024 ** 2:.2f} MB"
    else:
        return f"{value / 1024 ** 3:.2f} GB"


def send_feishu_alert(
    service_id: str,
    rule_id: str,
    metric_value: float,
    threshold: float,
    message: str,
    triggered_at: str,
) -> None:
    webhook_url = get_webhook_url()
    if not webhook_url:
        logger.warning("Feishu webhook URL not configured, skipping alert")
        return

    conn = db.get_connection()
    try:
        svc = conn.execute("SELECT name FROM services WHERE service_id=?", (service_id,)).fetchone()
        service_name = svc["name"] if svc else service_id
    finally:
        conn.close()

    rule_label = {
        "high_upload": "互联网上行流量过高",
        "high_download": "互联网下行流量过高",
        "high_connections": "互联网连接数过高",
    }.get(rule_id, rule_id)

    if "bytes" in message:
        metric_display = _format_bytes(metric_value)
        threshold_display = _format_bytes(threshold)
    else:
        metric_display = str(int(metric_value))
        threshold_display = str(int(threshold))

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": f"[NAS 告警] {rule_label}"},
                "template": "red",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**服务:** {service_name}\n**告警规则:** {rule_label}\n**当前值:** {metric_display}\n**阈值:** {threshold_display}\n**时间:** {triggered_at}",
                    },
                },
            ],
        },
    }

    try:
        resp = httpx.post(webhook_url, json=card, timeout=10)
        if resp.status_code != 200:
            logger.error("Feishu webhook returned %d: %s", resp.status_code, resp.text)
    except httpx.HTTPError as e:
        logger.error("Failed to send Feishu alert: %s", e)
        raise


def test_webhook(url: str) -> tuple[bool, str]:
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "[NAS 监控] Webhook 测试"},
                "template": "blue",
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "这是一条测试消息，确认飞书 Webhook 配置正确。",
                    },
                },
            ],
        },
    }
    try:
        resp = httpx.post(url, json=card, timeout=10)
        if resp.status_code == 200:
            return True, "发送成功"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except httpx.HTTPError as e:
        return False, str(e)
