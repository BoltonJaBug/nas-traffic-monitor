from __future__ import annotations

import json
import logging
import re
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import docker

from app.database import db
from app.models import ServiceInfo

logger = logging.getLogger(__name__)

_FNSTORE_IMAGE_PREFIXES = (
    "registry.cn-guangzhou.aliyuncs.com/fnapp/",
    "registry.fnnas.com/fnapp/",
)

_FNOS_SERVICE_PREFIXES = (
    "trim-",
    "fnos_",
)

_EXCLUDED_PROCESSES = {
    "nginx", "sshd", "systemd", "docker-proxy", "containerd",
    "rpcbind", "avahi", "dbus", "polkit", "cron", "beam.smp",
    "epmd", "redis-server", "postgres", "ovs-vswitchd", "ovsdb-server",
    "smbd", "smbd-scavenger", "nmbd", "wsdd2", "mdmonitor",
    "NetworkManager", "ModemManager", "libvirtd", "getty",
    "sssd", "rngd", "irqbalance", "smartd", "accountsrv",
    "trim-connect",
}

_EXCLUDED_SERVICES = {
    "systemd", "dbus", "network", "cron", "ssh", "docker",
    "containerd", "nginx", "postgresql", "redis", "rpcbind",
    "avahi", "smbd", "nmbd", "ovs-vswitchd", "ovsdb-server",
    "polkit", "libvirtd", "ModemManager", "NetworkManager",
    "smartd", "rngd", "irqbalance", "sssd", "mdmonitor",
    "getty", "accountsrv", "dbus-broker",
}


class ServiceDiscoveryBase(ABC):
    @abstractmethod
    def discover(self) -> list[ServiceInfo]:
        ...


def _is_fnstore_image(image_tag: str) -> bool:
    if not image_tag:
        return False
    return any(image_tag.startswith(prefix) for prefix in _FNSTORE_IMAGE_PREFIXES)


def _run_cmd(cmd: list[str], timeout: int = 10) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


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
            status = "running" if c.status == "running" else "stopped"
            container_id = c.short_id
            image = ""
            try:
                image = c.image.tags[0] if c.image.tags else str(c.image.id)[:19]
            except Exception:
                pass

            source = "fnstore" if _is_fnstore_image(image) else "docker"
            service_id = f"{source}-{name}"

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
                source=source,
                status=status,
                container_id=container_id,
                image=image,
                ports=json.dumps(ports_list),
                pid=pid,
            ))
        return services


class SystemdDiscovery(ServiceDiscoveryBase):
    def discover(self) -> list[ServiceInfo]:
        services = []
        output = _run_cmd(["systemctl", "list-units", "--type=service", "--state=running", "--no-pager", "--no-legend"])
        if not output:
            return services

        docker_names = set()
        try:
            client = docker.from_env()
            for c in client.containers.list(all=True):
                docker_names.add(c.name)
        except Exception:
            pass

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue

            unit_name = parts[0]
            if not unit_name.endswith(".service"):
                continue
            svc_name = unit_name[:-8]

            if svc_name in _EXCLUDED_SERVICES:
                continue
            if svc_name.startswith("docker"):
                continue
            if any(svc_name.startswith(p) for p in ("getty@", "session-", "user@", "system-", "dbus:", "snap.")):
                continue

            is_fnos = any(svc_name.startswith(p) for p in _FNOS_SERVICE_PREFIXES) or svc_name.endswith("_service")
            source = "fnstore" if is_fnos else "system"
            service_id = f"{source}-{svc_name}"

            main_pid = self._get_service_pid(svc_name)
            if main_pid and main_pid > 0:
                proc_name = self._get_pid_name(main_pid)
                if proc_name and proc_name in _EXCLUDED_PROCESSES:
                    continue

            ports = self._get_pid_ports(main_pid) if main_pid and main_pid > 0 else "[]"

            display_name = svc_name.replace("_", "-").replace("trim-", "").replace("_service", "")

            services.append(ServiceInfo(
                service_id=service_id,
                name=display_name,
                source=source,
                status="running",
                pid=main_pid if main_pid and main_pid > 0 else None,
                ports=ports,
            ))
        return services

    def _get_service_pid(self, svc_name: str) -> Optional[int]:
        output = _run_cmd(["systemctl", "show", svc_name, "--property=MainPID", "--value"])
        try:
            pid = int(output.strip())
            return pid if pid > 0 else None
        except (ValueError, TypeError):
            return None

    def _get_pid_name(self, pid: int) -> Optional[str]:
        try:
            with open(f"/proc/{pid}/comm", "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            return None

    def _get_pid_ports(self, pid: Optional[int]) -> str:
        if not pid:
            return "[]"
        output = _run_cmd(["ss", "-tlnp"])
        ports = []
        for line in output.split("\n"):
            if f"pid={pid}" in line:
                parts = line.strip().split()
                if len(parts) >= 4:
                    local = parts[3]
                    port = local.rsplit(":", 1)[-1]
                    try:
                        int(port)
                        ports.append(port)
                    except ValueError:
                        pass
        return json.dumps(ports)


class ServiceDiscovery:
    def __init__(self):
        self.discoverers: list[ServiceDiscoveryBase] = [
            DockerDiscovery(),
            SystemdDiscovery(),
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

            name_to_existing_id: dict[str, str] = {}
            for sid, row in existing.items():
                name_to_existing_id.setdefault(row["name"], sid)

            discovered_ids = set()
            for svc in services:
                old_id = name_to_existing_id.get(svc.name)
                if old_id and old_id != svc.service_id:
                    conn.execute("UPDATE services SET service_id=?, source=? WHERE service_id=?", (svc.service_id, svc.source, old_id))
                    existing[svc.service_id] = existing.pop(old_id, {})

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
