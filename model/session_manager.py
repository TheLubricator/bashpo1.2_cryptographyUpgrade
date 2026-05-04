import sqlite3
import secrets
from datetime import datetime, timezone, timedelta

SESSION_DB = 'bashpo_secured_session.db'

def init_session_db():
    with sqlite3.connect(SESSION_DB, timeout=30) as db:
        c = db.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                username TEXT PRIMARY KEY,
                session_token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            )
        ''')
        db.commit()

def generate_session_token():
    return secrets.token_urlsafe(32)

def create_session(username, expiry_minutes=120):   # 2 hours
    token = generate_session_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)
    with sqlite3.connect(SESSION_DB, timeout=30) as db:
        c = db.cursor()
        c.execute('''
            INSERT OR REPLACE INTO user_sessions (username, session_token, expires_at)
            VALUES (?, ?, ?)
        ''', (username, token, expires_at.isoformat()))
        db.commit()
    return token

def validate_session_token(username, token):
    with sqlite3.connect(SESSION_DB, timeout=30) as db:
        c = db.cursor()
        c.execute('''
            SELECT session_token, expires_at FROM user_sessions WHERE username = ?
        ''', (username,))
        row = c.fetchone()
        if not row:
            return False
        stored_token, expires_at_str = row
        # parse stored expiry (ISO format)
        expires_at = datetime.fromisoformat(expires_at_str)
        # compare with current UTC
        if stored_token != token or datetime.now(timezone.utc) > expires_at:
            return False
        return True

def delete_session(username):
    with sqlite3.connect(SESSION_DB, timeout=30) as db:
        c = db.cursor()
        c.execute("DELETE FROM user_sessions WHERE username = ?", (username,))
        db.commit()

def delete_all_sessions():
    with sqlite3.connect(SESSION_DB, timeout=30) as db:
        c = db.cursor()
        c.execute("DELETE FROM user_sessions")
        db.commit()