from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.collector.connections import collect_connections
from app.collector.discovery import ServiceDiscovery
from app.collector.traffic import collect_traffic
from app.config import config
from app.database import db
from app.processor.aggregator import generate_daily_summary
from app.processor.alert_engine import check_alerts

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _job_service_discovery() -> None:
    try:
        ServiceDiscovery().sync_to_db()
    except Exception as e:
        logger.error("Service discovery job failed: %s", e)


def _job_traffic_collect() -> None:
    try:
        collect_traffic()
    except Exception as e:
        logger.error("Traffic collect job failed: %s", e)


def _job_connection_collect() -> None:
    try:
        collect_connections()
    except Exception as e:
        logger.error("Connection collect job failed: %s", e)


def _job_daily_summary() -> None:
    try:
        generate_daily_summary()
    except Exception as e:
        logger.error("Daily summary job failed: %s", e)


def _job_alert_check() -> None:
    try:
        check_alerts()
    except Exception as e:
        logger.error("Alert check job failed: %s", e)


def _job_data_cleanup() -> None:
    try:
        conn = db.get_connection()
        try:
            traffic_cutoff = (datetime.now(timezone.utc) - timedelta(days=config.DATA_RETENTION_DAYS)).isoformat()
            alert_cutoff = (datetime.now(timezone.utc) - timedelta(days=config.ALERT_RETENTION_DAYS)).isoformat()

            conn.execute("DELETE FROM traffic_records WHERE timestamp < ?", (traffic_cutoff,))
            conn.execute("DELETE FROM connection_records WHERE timestamp < ?", (traffic_cutoff,))
            conn.execute("DELETE FROM alert_records WHERE triggered_at < ?", (alert_cutoff,))
            conn.commit()
        finally:
            conn.close()

        logger.info("Data cleanup completed")
    except Exception as e:
        logger.error("Data cleanup job failed: %s", e)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return

    _scheduler = BackgroundScheduler()

    interval = config.COLLECT_INTERVAL_MINUTES

    _scheduler.add_job(_job_service_discovery, "interval", minutes=interval, id="service_discovery")
    _scheduler.add_job(_job_traffic_collect, "interval", minutes=interval, id="traffic_collect")
    _scheduler.add_job(_job_connection_collect, "interval", minutes=interval, id="connection_collect")
    _scheduler.add_job(_job_alert_check, "interval", minutes=interval, id="alert_check")
    _scheduler.add_job(
        _job_daily_summary,
        "cron",
        hour=config.SUMMARY_HOUR,
        minute=config.SUMMARY_MINUTE,
        id="daily_summary",
    )
    _scheduler.add_job(
        _job_data_cleanup,
        "cron",
        hour=config.CLEANUP_HOUR,
        minute=config.CLEANUP_MINUTE,
        id="data_cleanup",
    )

    _scheduler.start()
    logger.info("Scheduler started with %d min interval", interval)


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        logger.info("Scheduler stopped")
