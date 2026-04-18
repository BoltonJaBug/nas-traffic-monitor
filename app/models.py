from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: int
    username: str
    password_hash: str
    created_at: str
    updated_at: str


@dataclass
class ServiceInfo:
    service_id: str
    name: str
    source: str
    status: str
    container_id: Optional[str] = None
    image: Optional[str] = None
    ports: str = "[]"
    pid: Optional[int] = None
    created_at: str = ""
    updated_at: str = ""


@dataclass
class TrafficRecord:
    id: int = 0
    service_id: str = ""
    timestamp: str = ""
    lan_rx_bytes: int = 0
    lan_tx_bytes: int = 0
    wan_rx_bytes: int = 0
    wan_tx_bytes: int = 0


@dataclass
class ConnectionRecord:
    id: int = 0
    service_id: str = ""
    timestamp: str = ""
    lan_connections: int = 0
    wan_connections: int = 0


@dataclass
class DailySummary:
    id: int = 0
    date: str = ""
    service_id: str = ""
    lan_rx_bytes: int = 0
    lan_tx_bytes: int = 0
    wan_rx_bytes: int = 0
    wan_tx_bytes: int = 0
    peak_wan_connections: int = 0
    avg_wan_connections: float = 0.0


@dataclass
class AlertRecord:
    id: int = 0
    service_id: str = ""
    rule_id: str = ""
    triggered_at: str = ""
    metric_value: float = 0.0
    threshold: float = 0.0
    message: str = ""
    notified: int = 0


@dataclass
class AlertConfig:
    rule_id: str
    service_id: Optional[str] = None
    metric: str = ""
    threshold: float = 0.0
    window_minutes: int = 60
    enabled: int = 1
