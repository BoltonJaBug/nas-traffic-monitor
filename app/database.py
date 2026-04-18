from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional

from app.config import config
from app.models import AlertConfig

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    service_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL,
    container_id TEXT,
    image TEXT,
    ports TEXT DEFAULT '[]',
    pid INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS traffic_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    lan_rx_bytes INTEGER NOT NULL DEFAULT 0,
    lan_tx_bytes INTEGER NOT NULL DEFAULT 0,
    wan_rx_bytes INTEGER NOT NULL DEFAULT 0,
    wan_tx_bytes INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (service_id) REFERENCES services(service_id)
);

CREATE INDEX IF NOT EXISTS idx_traffic_service_time ON traffic_records(service_id, timestamp);

CREATE TABLE IF NOT EXISTS connection_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    lan_connections INTEGER NOT NULL DEFAULT 0,
    wan_connections INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (service_id) REFERENCES services(service_id)
);

CREATE INDEX IF NOT EXISTS idx_conn_service_time ON connection_records(service_id, timestamp);

CREATE TABLE IF NOT EXISTS daily_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    service_id TEXT NOT NULL,
    lan_rx_bytes INTEGER NOT NULL DEFAULT 0,
    lan_tx_bytes INTEGER NOT NULL DEFAULT 0,
    wan_rx_bytes INTEGER NOT NULL DEFAULT 0,
    wan_tx_bytes INTEGER NOT NULL DEFAULT 0,
    peak_wan_connections INTEGER NOT NULL DEFAULT 0,
    avg_wan_connections REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (service_id) REFERENCES services(service_id),
    UNIQUE(date, service_id)
);

CREATE INDEX IF NOT EXISTS idx_summary_date ON daily_summaries(date);

CREATE TABLE IF NOT EXISTS alert_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    metric_value REAL NOT NULL,
    threshold REAL NOT NULL,
    message TEXT NOT NULL,
    notified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (service_id) REFERENCES services(service_id)
);

CREATE INDEX IF NOT EXISTS idx_alerts_time ON alert_records(triggered_at);

CREATE TABLE IF NOT EXISTS alert_config (
    rule_id TEXT PRIMARY KEY,
    service_id TEXT,
    metric TEXT NOT NULL,
    threshold REAL NOT NULL,
    window_minutes INTEGER NOT NULL DEFAULT 60,
    enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

_DEFAULT_ALERT_CONFIG = [
    ("high_upload", None, "wan_tx_bytes_1h", config.DEFAULT_HIGH_UPLOAD_BYTES, 60),
    ("high_download", None, "wan_rx_bytes_1h", config.DEFAULT_HIGH_DOWNLOAD_BYTES, 60),
    ("high_connections", None, "wan_connections", config.DEFAULT_HIGH_CONNECTIONS, 5),
]


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or config.DB_PATH

    def _connect(self) -> sqlite3.Connection:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_SCHEMA)
            self._init_defaults(conn)
            conn.commit()
        finally:
            conn.close()

    def _init_defaults(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT COUNT(*) FROM alert_config").fetchone()
        if row[0] == 0:
            for rule_id, service_id, metric, threshold, window in _DEFAULT_ALERT_CONFIG:
                conn.execute(
                    "INSERT OR IGNORE INTO alert_config (rule_id, service_id, metric, threshold, window_minutes) VALUES (?, ?, ?, ?, ?)",
                    (rule_id, service_id, metric, threshold, window),
                )

    def get_connection(self) -> sqlite3.Connection:
        return self._connect()


db = Database()
