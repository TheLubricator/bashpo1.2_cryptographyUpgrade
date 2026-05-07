from flask import *
import sqlite3
import uuid
from functools import wraps
from flask_apscheduler import APScheduler
from datetime import datetime
import logging
from datetime import timedelta
from sslcommerz_lib import SSLCOMMERZ
import random
import hashlib
import secrets
import json
import os
import time
from crypto import cbc_mac

def retry_on_lock(max_retries=5, delay=0.1):
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    last_exception = e
                    if "database is locked" in str(e) and attempt < max_retries-1:
                        time.sleep(delay * (2 ** attempt))
                        continue
                    raise
            raise last_exception
        return wrapper
    return decorator
# Import crypto modules
from crypto import rsa, ecc
from dotenv import load_dotenv
load_dotenv()

# ---------- Admin keys (loaded from environment) ----------
ADMIN_RSA_PUB = tuple(map(int, os.getenv('ADMIN_RSA_PUB').split(':')))
ADMIN_RSA_PRIV = tuple(map(int, os.getenv('ADMIN_RSA_PRIV').split(':')))
ADMIN_ECC_PUB = tuple(map(int, os.getenv('ADMIN_ECC_PUB').split(':')))
ADMIN_ECC_PRIV = int(os.getenv('ADMIN_ECC_PRIV'))

# ---------- Basic crypto helpers ----------
def rsa_encrypt_str(plaintext, pub_key):
    """Encrypt a string with RSA public key (n,e). Return hex string."""
    cipher_int = rsa.encrypt_string(plaintext, pub_key)
    return hex(cipher_int)[2:]

def rsa_decrypt_str(cipher_hex, priv_key):
    """Decrypt hex string with RSA private key (n,d). Return original string."""
    cipher_int = int(cipher_hex, 16)
    return rsa.decrypt_string(cipher_int, priv_key)

import traceback

def ecc_sign_str(data_bytes, priv_key):
    print(f"[SIGN DEBUG] priv_key type={type(priv_key)} val={str(priv_key)[:30]}")
    if isinstance(priv_key, tuple):
        print("[SIGN DEBUG] !! GOT TUPLE - STACK TRACE:")
        traceback.print_stack()
    r, s = ecc.ecdsa_sign(data_bytes, priv_key)
    return f"{hex(r)[2:]}:{hex(s)[2:]}"

def ecc_verify_str(data_bytes, sig_hex, pub_key):
    """Verify signature hex string with ECC public key (x,y)."""
    try:
        r_hex, s_hex = sig_hex.split(':')
        r = int(r_hex, 16)
        s = int(s_hex, 16)
        return ecc.ecdsa_verify(data_bytes, (r, s), pub_key)
    except:
        return False

# Aliases for route_help compatibility (to match expected function names)
ecc_sign_bytes = ecc_sign_str
ecc_verify_bytes = ecc_verify_str

# ---------- User private keys (stored as plain JSON, not RSA encrypted) ----------
import math

def encrypt_user_privates(rsa_priv, ecc_priv):
    """
    Encrypt RSA private key (chunked) and ECC private key (single) with admin RSA.
    """
    # RSA private key – chunked encryption
    rsa_json = json.dumps({'n': rsa_priv[0], 'd': rsa_priv[1]})
    rsa_bytes = rsa_json.encode('utf-8')
    key_len = (ADMIN_RSA_PUB[0].bit_length() + 7) // 8   # 256 for 2048-bit RSA
    max_chunk = key_len - 11   # PKCS#1 v1.5 padding requires at least 11 bytes overhead
    chunks = [rsa_bytes[i:i+max_chunk] for i in range(0, len(rsa_bytes), max_chunk)]
    encrypted_chunks = []
    for chunk in chunks:
        chunk_str = chunk.decode('utf-8')
        enc_chunk = rsa_encrypt_str(chunk_str, ADMIN_RSA_PUB)
        encrypted_chunks.append(enc_chunk)
    enc_rsa = json.dumps(encrypted_chunks)   # store as JSON list

    # ECC private key – simple encryption (fits)
    ecc_json = json.dumps(ecc_priv)
    enc_ecc = rsa_encrypt_str(ecc_json, ADMIN_RSA_PUB)

    return enc_rsa, enc_ecc

def decrypt_user_privates(enc_rsa_json, enc_ecc_hex):
    """
    Decrypt RSA private key (chunked) and ECC private key (single).
    """
    # Decrypt RSA private key
    encrypted_chunks = json.loads(enc_rsa_json)
    decrypted_bytes = b''
    for chunk_hex in encrypted_chunks:
        plain_chunk = rsa_decrypt_str(chunk_hex, ADMIN_RSA_PRIV)
        decrypted_bytes += plain_chunk.encode('utf-8')
    rsa_json = decrypted_bytes.decode('utf-8')
    rsa_priv_dict = json.loads(rsa_json)
    rsa_priv = (rsa_priv_dict['n'], rsa_priv_dict['d'])

    # Decrypt ECC private key
    ecc_json = rsa_decrypt_str(enc_ecc_hex, ADMIN_RSA_PRIV)
    ecc_priv = json.loads(ecc_json)

    return rsa_priv, ecc_priv

# ---------- High‑level key and data access helpers ----------
def get_user_keys(username):
    if username == 'LordGaben':
        return ADMIN_RSA_PUB, ADMIN_RSA_PRIV, ADMIN_ECC_PUB, ADMIN_ECC_PRIV
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            SELECT rsa_public, encrypted_rsa_private, ecc_public, encrypted_ecc_private
            FROM USERS WHERE username = ?
        """, (username,))
        row = c.fetchone()
        if not row:
            return None, None, None, None
        rsa_pub_str, enc_rsa_priv, ecc_pub_str, enc_ecc_priv = row
        rsa_pub = tuple(map(int, rsa_pub_str.split(':')))
        ecc_pub = tuple(map(int, ecc_pub_str.split(':')))
        rsa_priv, ecc_priv = decrypt_user_privates(enc_rsa_priv, enc_ecc_priv)
        return rsa_pub, rsa_priv, ecc_pub, ecc_priv

@retry_on_lock()
def get_user_balance(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT encrypted_balance, balance_sig FROM WALLET_BALANCE WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            return 0.0
        enc_balance, bal_sig = row
        _, rsa_priv, ecc_pub, _ = get_user_keys(username)
        if bal_sig == "dummy_balance" or username == 'LordGaben':
            balance_str = rsa_decrypt_str(enc_balance, rsa_priv)
        else:
            if not ecc_verify_bytes(enc_balance.encode(), bal_sig, ecc_pub):
                raise ValueError("Balance signature mismatch")
            balance_str = rsa_decrypt_str(enc_balance, rsa_priv)
        return float(balance_str)

@retry_on_lock()
def set_user_balance(username, new_balance):
    rsa_pub, rsa_priv, ecc_pub, ecc_priv = get_user_keys(username)
    enc_balance = rsa_encrypt_str(str(new_balance), rsa_pub)
    try:
        bal_sig = ecc_sign_bytes(enc_balance.encode(), ecc_priv)
    except OverflowError:
        bal_sig = "dummy_balance"
    with sqlite3.connect('bashpos_--definitely--_secured_database.db', timeout=30) as db:
        c = db.cursor()
        c.execute("UPDATE WALLET_BALANCE SET encrypted_balance = ?, balance_sig = ? WHERE username = ?",
                  (enc_balance, bal_sig, username))
        db.commit()

def get_user_email(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT encrypted_email, email_sig FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        if not row:
            return ''
        enc_email, email_sig = row
        _, _, ecc_pub, _ = get_user_keys(username)
        if email_sig != "dummy_email" and not ecc_verify_bytes(enc_email.encode(), email_sig, ecc_pub):
            raise ValueError("Email signature invalid")
        _, rsa_priv, _, _ = get_user_keys(username)
        return rsa_decrypt_str(enc_email, rsa_priv)

def get_user_address(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT encrypted_buyer_address, address_sig FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        if not row or not row[0]:
            return ''
        enc_addr, addr_sig = row
        _, _, ecc_pub, _ = get_user_keys(username)
        if addr_sig != "dummy_address" and not ecc_verify_bytes(enc_addr.encode(), addr_sig, ecc_pub):
            raise ValueError("Address signature invalid")
        _, rsa_priv, _, _ = get_user_keys(username)
        return rsa_decrypt_str(enc_addr, rsa_priv)

def get_user_account_status(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT account_status FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        return row[0] if row else 'terminated'

def encrypt_admin_data(plaintext):
    cipher = rsa_encrypt_str(plaintext, ADMIN_RSA_PUB)
    sig = ecc_sign_bytes(cipher.encode(), ADMIN_ECC_PRIV)
    return cipher, sig

def decrypt_admin_data(cipher_hex, sig_hex):
    if not ecc_verify_bytes(cipher_hex.encode(), sig_hex, ADMIN_ECC_PUB):
        raise ValueError("Admin data signature invalid")
    return rsa_decrypt_str(cipher_hex, ADMIN_RSA_PRIV)

# ---------- Password hashing ----------
def hash_password(plain_password: str) -> str:
    salt = secrets.token_hex(16)
    salted = (plain_password + salt).encode('utf-8')
    hash_obj = hashlib.sha256(salted)
    hash_hex = hash_obj.hexdigest()
    return f"{salt}:{hash_hex}"

def verify_password(stored: str, provided: str) -> bool:
    if ':' not in stored:
        return stored == provided
    salt, stored_hash = stored.split(':', 1)
    salted = (provided + salt).encode('utf-8')
    computed_hash = hashlib.sha256(salted).hexdigest()
    return secrets.compare_digest(computed_hash, stored_hash)

# ---------- Database connection and schema ----------
def connect_db():
    db = sqlite3.connect('bashpos_--definitely--_secured_database.db')
    c = db.cursor()

    # USERS table (encrypted)
    c.execute("""
CREATE TABLE IF NOT EXISTS USERS(
    username TEXT PRIMARY KEY UNIQUE NOT NULL,
    password TEXT NOT NULL,
    store_region TEXT CHECK(store_region IN('NA','LA','EU','ASI','')),
    card_info INT,
    company_name TEXT,
    publisher_name TEXT CHECK(publisher_name IN('bandai_namco','playstation_publishing','xbox_game_studios','square_enix','sega','self','')),
    user_type TEXT CHECK(user_type IN('buyer','developer','admin')) NOT NULL,
    account_status TEXT CHECK(account_status IN('active','terminated')) NOT NULL,
    encrypted_email TEXT NOT NULL,
    email_sig TEXT NOT NULL,
    encrypted_buyer_address TEXT,
    address_sig TEXT,
    rsa_public TEXT NOT NULL,
    encrypted_rsa_private TEXT NOT NULL,      
    ecc_public TEXT NOT NULL,
    encrypted_ecc_private TEXT NOT NULL,
              encrypted_mac_key TEXT, 
              mac_key_sig TEXT 
)
""")

    # WALLET_BALANCE (encrypted balance)
    c.execute("""
    CREATE TABLE IF NOT EXISTS WALLET_BALANCE (
        username TEXT PRIMARY KEY,
        encrypted_balance TEXT NOT NULL,
        balance_sig TEXT NOT NULL,
        FOREIGN KEY (username) REFERENCES USERS(username)
    )
    """)
    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1 TEXT NOT NULL,
    user2 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user1) REFERENCES USERS(username),
    FOREIGN KEY (user2) REFERENCES USERS(username)
)
              """)
    c.execute("""CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    mac TEXT NOT NULL,          
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (sender) REFERENCES USERS(username)
)
              """)

    # OTP codes (unchanged)
    c.execute("""
    CREATE TABLE IF NOT EXISTS otp_codes (
        id TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        email TEXT NOT NULL,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        used BOOLEAN DEFAULT 0,
        attempts INTEGER DEFAULT 0,
        max_attempts INTEGER DEFAULT 3
    )
    """)

    # Admin user creation
  # Admin user creation
    c.execute("SELECT * FROM USERS WHERE username = 'LordGaben'")
    existing_user = c.fetchone()
    if existing_user is None:
        # Admin uses global master keys – no private keys stored in DB
        enc_admin_rsa_priv = ""   # empty placeholder
        enc_admin_ecc_priv = ""   # empty placeholder
        rsa_pub_str = f"{ADMIN_RSA_PUB[0]}:{ADMIN_RSA_PUB[1]}"
        ecc_pub_str = f"{ADMIN_ECC_PUB[0]}:{ADMIN_ECC_PUB[1]}"
        admin_email = "newell@steampowered.com"
        enc_email = rsa_encrypt_str(admin_email, ADMIN_RSA_PUB)
        email_sig = ecc_sign_str(enc_email.encode(), ADMIN_ECC_PRIV)
        admin_password_hash = hash_password('123456')
        c.execute("""
            INSERT INTO USERS (username, password, user_type, account_status,
                encrypted_email, email_sig, rsa_public, encrypted_rsa_private, ecc_public, encrypted_ecc_private)
            VALUES ('LordGaben', ?, 'admin', 'active', ?, ?, ?, ?, ?, ?)
        """, (admin_password_hash, enc_email, email_sig, rsa_pub_str, enc_admin_rsa_priv, ecc_pub_str, enc_admin_ecc_priv))
        # Admin wallet balance
        enc_balance = rsa_encrypt_str('0', ADMIN_RSA_PUB)
        balance_sig = ecc_sign_str(enc_balance.encode(), ADMIN_ECC_PRIV)
        c.execute("INSERT INTO WALLET_BALANCE (username, encrypted_balance, balance_sig) VALUES (?, ?, ?)",
                ('LordGaben', enc_balance, balance_sig))
        db.commit()

    # GAME_PUBLISH_REQUEST (encrypted basic_description)
    c.execute("""
    CREATE TABLE IF NOT EXISTS GAME_PUBLISH_REQUEST(
        request_id TEXT PRIMARY KEY,
        username TEXT,
        game_name TEXT,
        game_genre TEXT,
        estimated_release_year INT(4),
        encrypted_basic_description TEXT,
        desc_sig TEXT,
        status TEXT CHECK(status IN ('Pending', 'Accepted', 'Rejected','Completed')),
        payment_status INT CHECK(payment_status IN (True,False)),
        FOREIGN KEY (username) REFERENCES USERS(username)
    )
    """)

    # SENT_FRIEND_REQUEST, FRIENDS unchanged
    c.execute("""
    CREATE TABLE IF NOT EXISTS SENT_FRIEND_REQUEST (
        username_from TEXT,
        username_to TEXT,
        request_status TEXT CHECK (request_status IN ('Pending', 'Accepted', 'Rejected')),
        FOREIGN KEY (username_from) REFERENCES USERS(username),
        FOREIGN KEY (username_to) REFERENCES USERS(username)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS FRIENDS (
        username_me TEXT,
        username_friendswith TEXT,
        FOREIGN KEY (username_me) REFERENCES USERS(username),
        FOREIGN KEY (username_friendswith) REFERENCES USERS(username)
    )
    """)

    # GAME_LIST (encrypted revenue_generated)
    c.execute("""
    CREATE TABLE IF NOT EXISTS GAME_LIST(
        game_name TEXT UNIQUE NOT NULL,
        game_genre TEXT NOT NULL,
        game_description TEXT NOT NULL,
        base_price INT NOT NULL CHECK(base_price between 0 AND 120),
        game_status TEXT CHECK(game_status in ('Active','Delisted')) NOT NULL,
        dev_username TEXT NOT NULL,
        rating_yes INT NOT NULL,
        rating_no INT NOT NULL,
        copies_sold INT NOT NULL,
        encrypted_revenue_generated TEXT NOT NULL,
        revenue_sig TEXT NOT NULL,
        img_path_logo TEXT NOT NULL,
        img_path_ss1 TEXT NOT NULL,
        img_path_ss2 TEXT NOT NULL,
        game_file_path TEXT NOT NULL,
        sale_status TEXT CHECK(sale_status in(True,False)),
        actual_price INT NOT NULL CHECK(actual_price between 0 AND 120),
        sale_end_time DATETIME,
        sale_percentage INT CHECK(sale_percentage between 0 AND 90),
        release_year INT NOT NULL,
        yt_embed TEXT NOT NULL,
        FOREIGN KEY (dev_username) REFERENCES USERS(username)
    )
    """)

    # WISHLIST, CART_SYSTEM unchanged
    c.execute("""
    CREATE TABLE IF NOT EXISTS WISHLIST(
        username TEXT NOT NULL,
        game_name TEXT NOT NULL,
        FOREIGN KEY (username) REFERENCES USERS(username),
        FOREIGN KEY (game_name) REFERENCES GAME_LIST(game_name)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS CART_SYSTEM (
        username TEXT NOT NULL,
        game_name TEXT NOT NULL,
        was_it_on_sale TEXT check(was_it_on_sale in(True,False)),
        FOREIGN KEY (username) REFERENCES USERS(username),
        FOREIGN KEY (game_name) REFERENCES GAME_LIST(game_name)
    )
    """)

    # OWNED_GAMES (encrypted amount_paid)
    c.execute("""
    CREATE TABLE IF NOT EXISTS OWNED_GAMES(
        username TEXT NOT NULL,
        game_name TEXT NOT NULL,
        encrypted_amount_paid TEXT NOT NULL,
        amount_sig TEXT NOT NULL,
        purchase_type TEXT NOT NULL CHECK (purchase_type in ('Digital','Product_key')),
        posted_review TEXT NOT NULL CHECK (posted_review in ('yes','no')),
        FOREIGN KEY (username) REFERENCES USERS(username),
        FOREIGN KEY (game_name) REFERENCES GAME_LIST(game_name)
    )
    """)

    # WALLET_CODE (encrypted wallet_key)
    c.execute("""
    CREATE TABLE IF NOT EXISTS WALLET_CODE(
        wallet_key TEXT PRIMARY KEY,
        encrypted_wallet_key TEXT NOT NULL,
        key_sig TEXT NOT NULL,
        amount INT NOT NULL,
        status TEXT CHECK (status in('ACTIVE','USED'))
    )
    """)

    # GAME_KEY (encrypted game_key)
    c.execute("""
    CREATE TABLE IF NOT EXISTS GAME_KEY(
        game_key TEXT PRIMARY KEY,
        encrypted_game_key TEXT NOT NULL,
        key_sig TEXT NOT NULL,
        game_name TEXT NOT NULL,
        status TEXT CHECK (status in('ACTIVE','USED')),
        FOREIGN KEY (game_name) REFERENCES GAME_LIST(game_name)
    )
    """)

    # Reviews (encrypted review)
    c.execute("""
    CREATE TABLE IF NOT EXISTS Reviews(
        game_name TEXT NOT NULL,
        username TEXT NOT NULL,
        encrypted_review TEXT NOT NULL,
        review_sig TEXT NOT NULL,
        rating TEXT NOT NULL CHECK(rating IN('yes','no')),
        FOREIGN KEY (game_name) REFERENCES GAME_LIST(game_name),
        FOREIGN KEY (username) REFERENCES USERS(username)
    )
    """)

    db.commit()
    c.connection.close()

# ---------- User retrieval (login) ----------
def retrieve_user(username, password):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT username, user_type, store_region, password FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        if row and verify_password(row[3], password):
            return (row[0], row[1], row[2])
        return None

def active_users(username, password):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT username, user_type, password FROM USERS WHERE username = ? AND account_status='active'", (username,))
        row = c.fetchone()
        if row and verify_password(row[2], password):
            return (row[0], row[1])
        return None

# ---------- Email (decrypted) retrieval for session ----------
def current_user_query(username):
    if username == 'LordGaben':
        with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
            c = db.cursor()
            c.execute("SELECT encrypted_email, email_sig FROM USERS WHERE username = ?", (username,))
            row = c.fetchone()
            if not row:
                return None
            enc_email, email_sig = row
            # Accept dummy signature from overflow
            if email_sig != "dummy_email" and not ecc_verify_str(enc_email.encode(), email_sig, ADMIN_ECC_PUB):
                raise ValueError("Admin email signature invalid")
            email = rsa_decrypt_str(enc_email, ADMIN_RSA_PRIV)
            return (email,)
    else:
        with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
            c = db.cursor()
            c.execute("SELECT encrypted_email, email_sig, encrypted_rsa_private, encrypted_ecc_private, ecc_public FROM USERS WHERE username = ?", (username,))
            row = c.fetchone()
            if not row:
                return None
            enc_email, email_sig, enc_rsa_priv, enc_ecc_priv, ecc_pub_str = row
            ecc_pub = tuple(map(int, ecc_pub_str.split(':')))
            if email_sig != "dummy_email" and not ecc_verify_str(enc_email.encode(), email_sig, ecc_pub):
                raise ValueError("Email signature invalid")
            user_rsa_priv, _ = decrypt_user_privates(enc_rsa_priv, enc_ecc_priv)  # returns (rsa_priv, ecc_priv) but we only need RSA
            email = rsa_decrypt_str(enc_email, user_rsa_priv)
            return (email,)

# ---------- Password reset ----------
def forget_password_email_verification(email):
    # We cannot search by encrypted email directly. We'll search by username in practice.
    # For simplicity, we assume the frontend sends username, not email.
    # This function will be reimplemented to use username.
    pass

def forget_password_update_password(username, new_password):
    hashed = hash_password(new_password)
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("UPDATE USERS SET password = ? WHERE username = ?", (hashed, username))
        db.commit()

def get_stored_password_hash(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT password FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        return row[0] if row else None

def update_password_passed_check(hashed_password, username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("UPDATE USERS SET password = ? WHERE username = ?", (hashed_password, username))
        db.commit()

# ---------- OTP (unchanged) ----------
import uuid
import random
from datetime import datetime, timedelta

def generate_otp_code():
    return f"{random.randint(0, 999999):06d}"

def create_otp_record(email, expiration_minutes=5):
    code = generate_otp_code()
    now = datetime.now()
    expires_at = now + timedelta(minutes=expiration_minutes)
    return {
        'id': uuid.uuid4().hex,
        'code': code,
        'email': email,
        'created_at': now,
        'expires_at': expires_at,
        'used': False,
        'attempts': 0,
        'max_attempts': 3
    }

def save_otp_record(record):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            INSERT INTO otp_codes (id, code, email, created_at, expires_at, used, attempts, max_attempts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (record['id'], record['code'], record['email'],
              record['created_at'], record['expires_at'],
              record['used'], record['attempts'], record['max_attempts']))
        db.commit()
        return record['id']

def get_latest_otp_record(email):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            SELECT id, code, email, created_at, expires_at, used, attempts, max_attempts
            FROM otp_codes
            WHERE email = ? AND used = 0
            ORDER BY created_at DESC
            LIMIT 1
        """, (email,))
        row = c.fetchone()
        if row:
            return {
                'id': row[0],
                'code': row[1],
                'email': row[2],
                'created_at': datetime.fromisoformat(row[3]) if isinstance(row[3], str) else row[3],
                'expires_at': datetime.fromisoformat(row[4]) if isinstance(row[4], str) else row[4],
                'used': row[5],
                'attempts': row[6],
                'max_attempts': row[7]
            }
        return None

def verify_otp(email, entered_code):
    record = get_latest_otp_record(email)
    if not record:
        return False, "OTP not found. Please request a new code."
    if record['used']:
        return False, "OTP already used. Request a new code."
    now = datetime.now()
    if now > record['expires_at']:
        return False, "OTP expired. Request a new code."
    if record['attempts'] >= record['max_attempts']:
        return False, "Too many failed attempts. Request a new code."
    if entered_code == record['code']:
        with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
            c = db.cursor()
            c.execute("UPDATE otp_codes SET used = 1 WHERE id = ?", (record['id'],))
            db.commit()
        return True, "OTP verified successfully."
    else:
        new_attempts = record['attempts'] + 1
        with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
            c = db.cursor()
            c.execute("UPDATE otp_codes SET attempts = ? WHERE id = ?", (new_attempts, record['id']))
            db.commit()
        remaining = record['max_attempts'] - new_attempts
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."

def delete_old_otps(email):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
        db.commit()

# ---------- Scheduler (unchanged) ----------
def sale_reset_query(current_time):
    db = sqlite3.connect("bashpos_--definitely--_secured_database.db")
    c = db.cursor()
    c.execute("""
        UPDATE GAME_LIST SET actual_price = base_price, sale_status = ?, sale_end_time=?, sale_percentage=? 
        WHERE sale_end_time IS NOT NULL AND sale_end_time <= ?
    """, (False, None, None, current_time))
    db.commit()
    db.close()

# ---------- Registration with encryption ----------
def create_buyer_query(username, email, password, buyer_address, store_region, card_info, user_type):
    hashed = hash_password(password)
    user_rsa_pub, user_rsa_priv = rsa.generate_rsa_keys(2048)
    user_ecc_priv, user_ecc_pub = ecc.generate_ecc_keypair()
    # Generate MAC key for CBC-MAC
    mac_key = cbc_mac.generate_mac_key()
    # Encrypt MAC key with admin RSA public key
    mac_key_hex = rsa_encrypt_str(mac_key.hex(), ADMIN_RSA_PUB)
    mac_key_sig = ecc_sign_bytes(mac_key_hex.encode(), user_ecc_priv)  # sign with user's ECC

    enc_email = rsa_encrypt_str(email, user_rsa_pub)
    email_sig = ecc_sign_str(enc_email.encode(), user_ecc_priv)
    enc_address = rsa_encrypt_str(buyer_address, user_rsa_pub) if buyer_address else ''
    address_sig = ecc_sign_str(enc_address.encode(), user_ecc_priv) if buyer_address else ''

    # Encrypt private keys with admin RSA
    enc_rsa_priv, enc_ecc_priv = encrypt_user_privates(user_rsa_priv, user_ecc_priv)
    rsa_pub_str = f"{user_rsa_pub[0]}:{user_rsa_pub[1]}"
    ecc_pub_str = f"{user_ecc_pub[0]}:{user_ecc_pub[1]}"

    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            INSERT INTO USERS (username, password, store_region, card_info, user_type, account_status,
                               encrypted_email, email_sig, encrypted_buyer_address, address_sig,
                               rsa_public, encrypted_rsa_private, ecc_public, encrypted_ecc_private,encrypted_mac_key,mac_key_sig)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?,?,?)
        """, (username, hashed, store_region, card_info, user_type,
              enc_email, email_sig, enc_address, address_sig,
              rsa_pub_str, enc_rsa_priv, ecc_pub_str, enc_ecc_priv,mac_key_hex, mac_key_sig))
        # Insert wallet balance (unchanged)
        enc_balance = rsa_encrypt_str('0', user_rsa_pub)
        balance_sig = ecc_sign_str(enc_balance.encode(), user_ecc_priv)
        c.execute("INSERT INTO WALLET_BALANCE (username, encrypted_balance, balance_sig) VALUES (?, ?, ?)",
                  (username, enc_balance, balance_sig))
        db.commit()

# Similarly for create_dev_query (no address, but same key storage)
def get_user_mac_key(username):
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT encrypted_mac_key, mac_key_sig, ecc_public FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        if not row or not row[0]:
            return None
        enc_key, sig, ecc_pub_str = row
        ecc_pub = tuple(map(int, ecc_pub_str.split(':')))
        if not ecc_verify_bytes(enc_key.encode(), sig, ecc_pub):
            raise ValueError("MAC key signature invalid")
        mac_key_hex = rsa_decrypt_str(enc_key, ADMIN_RSA_PRIV)
        return bytes.fromhex(mac_key_hex)

def verify_chat_mac(sender: str, message: str, mac_hex: str) -> bool:
    """
    Verify CBC-MAC of a chat message using the sender's MAC key.
    Returns True if valid, False otherwise.
    """
    key = get_user_mac_key(sender)
    if key is None:
        return False
    computed = cbc_mac.cbc_mac(key, message.encode('utf-8'))
    return computed.hex() == mac_hex   

def create_dev_query(username, email, password, company_name, publisher_name, user_type):
    hashed = hash_password(password)
    # Generate user keys
    user_rsa_pub, user_rsa_priv = rsa.generate_rsa_keys(2048)
    user_ecc_priv, user_ecc_pub = ecc.generate_ecc_keypair()

    # Encrypt email
    enc_email = rsa_encrypt_str(email, user_rsa_pub)
    email_sig = ecc_sign_str(enc_email.encode(), user_ecc_priv)

    # Encrypt private keys with admin RSA
    enc_rsa_priv, enc_ecc_priv = encrypt_user_privates(user_rsa_priv, user_ecc_priv)

    rsa_pub_str = f"{user_rsa_pub[0]}:{user_rsa_pub[1]}"
    ecc_pub_str = f"{user_ecc_pub[0]}:{user_ecc_pub[1]}"

    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            INSERT INTO USERS (username, password, company_name, publisher_name, user_type, account_status,
                               encrypted_email, email_sig,
                               rsa_public, encrypted_rsa_private,
                               ecc_public, encrypted_ecc_private)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?)
        """, (username, hashed, company_name, publisher_name, user_type,
              enc_email, email_sig,
              rsa_pub_str, enc_rsa_priv,
              ecc_pub_str, enc_ecc_priv))

        # Developers also have a wallet balance
        enc_balance = rsa_encrypt_str('0', user_rsa_pub)
        balance_sig = ecc_sign_str(enc_balance.encode(), user_ecc_priv)
        c.execute("INSERT INTO WALLET_BALANCE (username, encrypted_balance, balance_sig) VALUES (?, ?, ?)",
                  (username, enc_balance, balance_sig))
        db.commit()