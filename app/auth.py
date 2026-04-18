from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import config
from app.database import db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def ensure_admin_user() -> None:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (config.ADMIN_USERNAME,)).fetchone()
        if not row:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (config.ADMIN_USERNAME, hash_password(config.ADMIN_PASSWORD), now, now),
            )
            conn.commit()
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> Optional[str]:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if row and verify_password(password, row["password_hash"]):
            return create_access_token(username)
        return None
    finally:
        conn.close()


def change_password(username: str, old_password: str, new_password: str) -> bool:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if not row or not verify_password(old_password, row["password_hash"]):
            return False
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE username = ?",
            (hash_password(new_password), now, username),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def get_user_info(username: str) -> Optional[dict]:
    conn = db.get_connection()
    try:
        row = conn.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "created_at": row["created_at"]}
        return None
    finally:
        conn.close()
