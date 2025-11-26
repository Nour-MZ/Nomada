"""
Simple SQLite-backed user store for name, email, and password hash.
"""

import sqlite3
import hashlib
from typing import Optional, Dict

DB_PATH = "databases/users.sqlite"


def _ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
        """
    )
    conn.commit()


def _hash_password(password: str) -> str:
    # Simple SHA256 hash; replace with a stronger hash (bcrypt/argon2) for production
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(name: str, email: str, password: str, db_path: str = DB_PATH) -> int:
    conn = sqlite3.connect(db_path)
    _ensure_schema(conn)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        (name, email, _hash_password(password)),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return user_id


def get_user(email: str, db_path: str = DB_PATH) -> Optional[Dict[str, str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def authenticate(email: str, password: str, db_path: str = DB_PATH) -> bool:
    user = get_user(email, db_path=db_path)
    if not user:
        return False
    return user.get("password_hash") == _hash_password(password)
