from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import docker

from app.database import db
from app.models import ServiceInfo

logger = logging.getLogger(__name__)


class ServiceDiscoveryBase(ABC):
    @abstractmethod
    def discover(self) -> list[ServiceInfo]:
        ...


class DockerDiscovery(ServiceDiscoveryBase):
    def __init__(self):
        try:
            self.client = docker.from_env()
        except docker.errors.DockerException:
            logger.warning("Docker daemon not accessible")
            self.client = None

    def discover(self) -> list[ServiceInfo]:
        if not self.client:
            return []
        services = []
        try:
            containers = self.client.containers.list(all=True)
        except docker.errors.DockerException as e:
            logger.error("Failed to list Docker containers: %s", e)
            return []

        for c in containers:
            name = c.name
            service_id = f"docker-{name}"
            status = "running" if c.status == "running" else "stopped"
            container_id = c.short_id
            image = ""
            try:
                image = c.image.tags[0] if c.image.tags else str(c.image.id)[:19]
            except Exception:
                pass

            ports_list = []
            if c.ports:
                for container_port, host_bindings in c.ports.items():
                    if host_bindings:
                        for binding in host_bindings:
                            ports_list.append(f"{binding.get('HostPort', '?')}:{container_port}")
                    else:
                        ports_list.append(container_port)

            pid: Optional[int] = None
            try:
                top = c.top()
                if top and top.get("Processes"):
                    for proc in top["Processes"]:
                        try:
                            pid = int(proc[1])
                            break
                        except (IndexError, ValueError):
                            continue
            except docker.errors.APIError:
                pass

            services.append(ServiceInfo(
                service_id=service_id,
                name=name,
                source="docker",
                status=status,
                container_id=container_id,
                image=image,
                ports=json.dumps(ports_list),
                pid=pid,
            ))
        return services


class FnStoreDiscovery(ServiceDiscoveryBase):
    def discover(self) -> list[ServiceInfo]:
        return []


class ServiceDiscovery:
    def __init__(self):
        self.discoverers: list[ServiceDiscoveryBase] = [
            DockerDiscovery(),
            FnStoreDiscovery(),
        ]

    def discover_all(self) -> list[ServiceInfo]:
        all_services = []
        for d in self.discoverers:
            try:
                all_services.extend(d.discover())
            except Exception as e:
                logger.error("Discovery error from %s: %s", type(d).__name__, e)
        return all_services

    def sync_to_db(self) -> None:
        services = self.discover_all()
        now = datetime.now(timezone.utc).isoformat()
        conn = db.get_connection()
        try:
            existing = {
                row["service_id"]: dict(row)
                for row in conn.execute("SELECT * FROM services").fetchall()
            }

            discovered_ids = set()
            for svc in services:
                discovered_ids.add(svc.service_id)
                if svc.service_id in existing:
                    conn.execute(
                        "UPDATE services SET name=?, source=?, status=?, container_id=?, image=?, ports=?, pid=?, updated_at=? WHERE service_id=?",
                        (svc.name, svc.source, svc.status, svc.container_id, svc.image, svc.ports, svc.pid, now, svc.service_id),
                    )
                else:
                    conn.execute(
                        "INSERT INTO services (service_id, name, source, status, container_id, image, ports, pid, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (svc.service_id, svc.name, svc.source, svc.status, svc.container_id, svc.image, svc.ports, svc.pid, now, now),
                    )

            for sid in existing:
                if sid not in discovered_ids:
                    conn.execute(
                        "UPDATE services SET status='stopped', updated_at=? WHERE service_id=?",
                        (now, sid),
                    )

            conn.commit()
        finally:
            conn.close()
        logger.info("Service discovery synced %d services", len(services))
