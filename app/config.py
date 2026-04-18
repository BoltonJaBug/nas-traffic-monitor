import os


class Config:
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "changeme")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "please-change-this-secret")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    DB_PATH: str = os.getenv("DB_PATH", "/app/data/monitor.db")

    FEISHU_WEBHOOK_URL: str = os.getenv("FEISHU_WEBHOOK_URL", "")

    COLLECT_INTERVAL_MINUTES: int = 5
    SUMMARY_HOUR: int = 0
    SUMMARY_MINUTE: int = 5
    CLEANUP_HOUR: int = 1
    CLEANUP_MINUTE: int = 0

    DATA_RETENTION_DAYS: int = 90
    ALERT_RETENTION_DAYS: int = 180
    ALERT_DEDUP_MINUTES: int = 30

    DEFAULT_HIGH_UPLOAD_BYTES: int = 5 * 1024 ** 3
    DEFAULT_HIGH_DOWNLOAD_BYTES: int = 10 * 1024 ** 3
    DEFAULT_HIGH_CONNECTIONS: int = 200

    LAN_NETWORKS: tuple = ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")

    WEB_PORT: int = int(os.getenv("WEB_PORT", "8888"))


config = Config()
