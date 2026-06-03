import sqlite3
import json
from datetime import datetime
import base64
import uuid
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

import os
USER_HOME = os.path.expanduser("~")
LOGDAY_DIR = os.path.join(USER_HOME, ".logday-wfh")
os.makedirs(LOGDAY_DIR, exist_ok=True)
DB_FILE = os.path.join(LOGDAY_DIR, "agent_queue.db")

def _get_encryption_key() -> bytes:
    """Derives a secure, machine-locked symmetric key from motherboard node ID."""
    system_salt = b"LogDayWfhOfflineEncryptionSalt"
    node_id = str(uuid.getnode()).encode('utf-8')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=system_salt,
        iterations=10000
    )
    return base64.urlsafe_b64encode(kdf.derive(node_id))

def encrypt_payload(data: dict) -> str:
    """Encrypts a dictionary payload into an encrypted base64 string."""
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        serialized = json.dumps(data).encode('utf-8')
        return f.encrypt(serialized).decode('utf-8')
    except Exception:
        return json.dumps(data)

def decrypt_payload(encrypted_str: str) -> dict:
    """Decrypts an encrypted base64 string back into a dictionary."""
    try:
        key = _get_encryption_key()
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_str.encode('utf-8'))
        return json.loads(decrypted.decode('utf-8'))
    except Exception:
        try:
            return json.loads(encrypted_str)
        except Exception:
            return {}


def get_connection():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS upload_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            last_error TEXT
        )
    """)

    conn.commit()
    conn.close()


def add_to_queue(item_type: str, payload: dict):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO upload_queue (type, payload, created_at, status)
        VALUES (?, ?, ?, ?)
        """,
        (
            item_type,
            encrypt_payload(payload),
            datetime.utcnow().isoformat(),
            "pending"
        )
    )

    conn.commit()
    conn.close()


def get_pending_items(limit: int = 10):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, type, payload, attempts
        FROM upload_queue
        WHERE status = 'pending'
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,)
    )

    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "type": row[1],
            "payload": decrypt_payload(row[2]),
            "attempts": row[3]
        }
        for row in rows
    ]


def mark_done(item_id: int):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "UPDATE upload_queue SET status = 'done' WHERE id = ?",
        (item_id,)
    )

    conn.commit()
    conn.close()


def mark_failed(item_id: int, error: str):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE upload_queue
        SET attempts = attempts + 1,
            last_error = ?
        WHERE id = ?
        """,
        (error, item_id)
    )

    conn.commit()
    conn.close()


def queue_count():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM upload_queue WHERE status = 'pending'")
    count = cur.fetchone()[0]

    conn.close()
    return count