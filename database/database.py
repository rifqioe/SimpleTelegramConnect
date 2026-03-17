import sqlite3
import hashlib
import os
from datetime import datetime

DB_NAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_connect.db")

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telegram_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            telegram_id TEXT UNIQUE,
            telegram_username TEXT,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            otp_code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_used INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    salt = "telegramconnect_salt"
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

# SEED DUMMY USERS FOR TESTING -----------------------------------------------------
def seed_dummy_users():
    conn = get_connection()
    cursor = conn.cursor()

    dummy_users = [
        ("admin", "admin123", "Administrator"),
        ("rifqi", "password123", "Rifqi"),
        ("john", "john456", "John Doe"),
        ("jane", "jane789", "Jane Smith"),
    ]

    for username, password, name in dummy_users:
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                (username, hash_password(password), name)
            )
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
# ----------------------------------------------------------------------------------

def authenticate_user(username: str, password: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username = ? AND password_hash = ?",
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()

    return dict(user) if user else None

def get_user_by_id(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def save_otp(user_id: int, otp_code: str, expires_at: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE otp_codes SET is_used = 1 WHERE user_id = ? AND is_used = 0",
        (user_id,)
    )

    cursor.execute(
        "INSERT INTO otp_codes (user_id, otp_code, expires_at) VALUES (?, ?, ?)",
        (user_id, otp_code, expires_at)
    )

    conn.commit()
    conn.close()

def verify_otp(otp_code: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM otp_codes WHERE otp_code = ? AND is_used = 0 AND expires_at > ?",
        (otp_code, datetime.now().isoformat())
    )
    otp_record = cursor.fetchone()

    if otp_record:
        cursor.execute(
            "UPDATE otp_codes SET is_used = 1 WHERE id = ?",
            (otp_record["id"],)
        )
        conn.commit()
        conn.close()
        return otp_record["user_id"]

    conn.close()
    return None

def link_telegram(user_id: int, telegram_id: str, telegram_username: str = None):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM telegram_links WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute(
                "UPDATE telegram_links SET telegram_id = ?, telegram_username = ?, linked_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                (telegram_id, telegram_username, user_id)
            )
        else:
            cursor.execute(
                "INSERT INTO telegram_links (user_id, telegram_id, telegram_username) VALUES (?, ?, ?)",
                (user_id, telegram_id, telegram_username)
            )

        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_telegram_link(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM telegram_links WHERE user_id = ?", (user_id,))
    link = cursor.fetchone()
    conn.close()
    return dict(link) if link else None

def get_user_by_telegram_id(telegram_id: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT u.* FROM users u JOIN telegram_links tl ON u.id = tl.user_id WHERE tl.telegram_id = ?",
        (telegram_id,)
    )
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def unlink_telegram(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM telegram_links WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

if __name__ == "__main__":
    init_db()
    seed_dummy_users()
