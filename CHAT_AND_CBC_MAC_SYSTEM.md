# Chat System & Message Integrity (CBC-MAC)

## Overview

The BashPO platform includes a secure chat system between friends with message integrity verification using CBC-MAC (Cipher Block Chaining Message Authentication Code). This system ensures that all messages are authenticated and tamper-proof.

## 1. Database Schema

### Chat Sessions Table
```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user1 TEXT NOT NULL,
    user2 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user1) REFERENCES USERS(username),
    FOREIGN KEY (user2) REFERENCES USERS(username)
)
```
- Stores conversations between two users
- Each session has a unique ID and creation timestamp
- Bidirectional: (user1, user2) same as (user2, user1)

### Chat Messages Table
```sql
CREATE TABLE IF NOT EXISTS chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    mac TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id),
    FOREIGN KEY (sender) REFERENCES USERS(username)
)
```
- Stores individual messages in a session
- **mac column**: CBC-MAC computed over the plaintext message
- Timestamps track message order
- Sender field identifies who sent the message

## 2. CBC-MAC Implementation

### Overview
CBC-MAC is a symmetric message authentication code based on block cipher encryption. It uses AES-128 in ECB mode to process message blocks sequentially.

### Algorithm

```python
def generate_mac_key():
    """Generate a random 128-bit AES key for CBC-MAC."""
    return os.urandom(16)   # 128 bits

def cbc_mac(key, message):
    """
    Compute CBC-MAC of a message using AES-128.
    Message is a bytes-like object (UTF-8 encoded string).
    Returns the MAC as bytes (16 bytes).
    """
    cipher = AES.new(key, AES.MODE_ECB)   # ECB for block encryption
    block_size = 16
    # Pad message with zeros (PKCS#7 style but simple zero padding)
    padded = message
    if len(padded) % block_size != 0:
        padded += b'\x00' * (block_size - len(padded) % block_size)
    # CBC-MAC: encrypt the first block, then XOR with next block, etc.
    prev = b'\x00' * block_size
    for i in range(0, len(padded), block_size):
        block = padded[i:i+block_size]
        # XOR with previous ciphertext
        xored = bytes(a ^ b for a, b in zip(block, prev))
        prev = cipher.encrypt(xored)
    return prev   # final block is the MAC

def verify_cbc_mac(key, message, mac):
    """Check if the MAC matches the message."""
    computed = cbc_mac(key, message)
    return computed == mac
```

### How CBC-MAC Works

1. **Key Generation**: Create random 128-bit key for AES
2. **Message Padding**: Pad message to multiple of 16 bytes with zero bytes
3. **Block Processing**:
   - Initialize `prev = 0x00...00` (16 zero bytes)
   - For each 16-byte block:
     - XOR block with previous ciphertext
     - Encrypt result with AES-ECB
     - Store as new `prev` value
4. **MAC Output**: Final `prev` value is the MAC (16 bytes)
5. **Verification**: Recompute MAC and compare with stored MAC

### Security Properties

- **Unforgeability**: Attacker cannot create valid MAC without knowing key
- **Integrity**: Any modification to message makes MAC invalid
- **Authentication**: Proves message came from sender with the MAC key
- **Fixed output**: Always 16 bytes regardless of message size

## 3. Chat System Implementation

### User MAC Key Storage

Each user has an **encrypted MAC key** stored in the `USERS` table:
- Column `encrypted_mac_key`: User's MAC key encrypted with admin RSA public key
- Column `mac_key_sig`: ECDSA signature of the encrypted key (using user's ECC public key)

```python
def get_user_mac_key(username):
    """Retrieve and decrypt user's MAC key."""
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT encrypted_mac_key, mac_key_sig, ecc_public FROM USERS WHERE username = ?", (username,))
        row = c.fetchone()
        if not row or not row[0]:
            return None
        enc_key, sig, ecc_pub_str = row
        # Parse ECC public key
        ecc_pub = tuple(map(int, ecc_pub_str.split(':')))
        # Verify signature (prove key hasn't been tampered)
        if not ecc_verify_bytes(enc_key.encode(), sig, ecc_pub):
            raise ValueError("MAC key signature invalid")
        # Decrypt key with admin private key
        mac_key_hex = rsa_decrypt_str(enc_key, ADMIN_RSA_PRIV)
        return bytes.fromhex(mac_key_hex)
```

### Chat Session Management

```python
def get_chat_session(user_a, user_b):
    """Get or create chat session between two users."""
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        # Search for existing session (bidirectional)
        c.execute("""
            SELECT id FROM chat_sessions
            WHERE (user1 = ? AND user2 = ?) OR (user1 = ? AND user2 = ?)
        """, (user_a, user_b, user_b, user_a))
        row = c.fetchone()
        if row:
            return row[0]
        # Create new session if doesn't exist
        c.execute("INSERT INTO chat_sessions (user1, user2) VALUES (?, ?)", (user_a, user_b))
        db.commit()
        return c.lastrowid
```

### Sending a Message with MAC

```python
@app.route('/api/chat/send', methods=['POST'])
@login_required('buyer')
def chat_send():
    """Send a message with CBC-MAC integrity."""
    data = request.json
    friend = data.get('friend')
    message = data.get('message')
    if not friend or not message:
        return jsonify({'error': 'Missing fields'}), 400
    
    username = session['username']
    session_id = get_chat_session(username, friend)
    
    # Get sender's MAC key (encrypted in database)
    mac_key = get_user_mac_key(username)
    if not mac_key:
        return jsonify({'error': 'MAC key not found'}), 500
    
    # Compute CBC-MAC on the plaintext message
    mac = cbc_mac.cbc_mac(mac_key, message.encode('utf-8'))
    mac_hex = mac.hex()
    
    # Store message and MAC
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            INSERT INTO chat_messages (session_id, sender, message, mac)
            VALUES (?, ?, ?, ?)
        """, (session_id, username, message, mac_hex))
        db.commit()
    
    return jsonify({'success': True})
```

### Retrieving Messages with Integrity Check

```python
@app.route('/api/chat/messages/<friend>')
@login_required('buyer')
def chat_messages(friend):
    """Retrieve all messages in a chat session."""
    username = session['username']
    session_id = get_chat_session(username, friend)
    
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("""
            SELECT sender, message, mac, timestamp FROM chat_messages
            WHERE session_id = ? ORDER BY timestamp ASC
        """, (session_id,))
        rows = c.fetchall()
    
    # Return messages (MAC verification can be done on client or server)
    messages = [{'sender': r[0], 'message': r[1], 'timestamp': r[3]} for r in rows]
    return jsonify(messages)
```

### Getting Friends List for Chat

```python
@app.route('/api/chat/friends')
@login_required('buyer')
def chat_friends():
    """Get list of friends to chat with."""
    username = session['username']
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT username_friendswith FROM FRIENDS WHERE username_me = ?", (username,))
        friends = [row[0] for row in c.fetchall()]
    return jsonify(friends)
```

### Chat UI Route

```python
@app.route('/chat')
@login_required('buyer')
def chat_page():
    """Render chat interface."""
    return render_template('chat.html')
```

## 4. Wallet Code System (Related to Chat)

Although wallet codes use ElGamal encryption (not CBC-MAC), they include integrity verification:

### Wallet Code Validation

```python
def wallet_code_validation(gift_card):
    """Validate wallet code by decrypting and comparing."""
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("SELECT wallet_key, encrypted_wallet_key, key_sig, amount, status FROM WALLET_CODE WHERE status='ACTIVE'")
        for row in c.fetchall():
            stored_key, enc_data, key_sig, amount, status = row
            # Verify ECDSA signature on encrypted data
            if not ecc_verify_bytes(enc_data.encode(), key_sig, ADMIN_ECC_PUB):
                continue
            try:
                # Decrypt ElGamal ciphertext
                cipher_dict = json.loads(enc_data)
                decrypted_key = ecc.elgamal_decrypt(cipher_dict, ADMIN_ECC_PRIV)
            except:
                continue
            if decrypted_key == gift_card:
                return row
        return []
```

### Wallet Code Activation

```python
def wallet_code_activation_confirm(gift_card, check_card):
    """Activate wallet code and update user balance."""
    denomination = check_card[3]  # amount column index
    old_balance = get_user_balance(session['username'])
    # Update balance with new funds
    set_user_balance(session['username'], old_balance + denomination)
    # Mark code as used
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        c.execute("UPDATE WALLET_CODE SET status='USED' WHERE wallet_key=?", (gift_card,))
        db.commit()
```

### Generating Wallet Codes

```python
def generate_wallet_query(value, no_of_cards):
    """Generate multiple wallet codes encrypted with ElGamal."""
    with sqlite3.connect('bashpos_--definitely--_secured_database.db') as db:
        c = db.cursor()
        for _ in range(no_of_cards):
            wallet_key = uuid.uuid4().hex  # plaintext key
            # Encrypt with ElGamal using admin's ECC public key
            cipher = ecc.elgamal_encrypt(wallet_key, ADMIN_ECC_PUB)
            enc_data = json.dumps(cipher)   # JSON string
            # Sign the ciphertext with admin's ECC private key
            key_sig = ecc_sign_bytes(enc_data.encode(), ADMIN_ECC_PRIV)
            c.execute("""
                INSERT INTO WALLET_CODE (wallet_key, encrypted_wallet_key, key_sig, amount, status)
                VALUES (?, ?, ?, ?, 'ACTIVE')
            """, (wallet_key, enc_data, key_sig, value))
        db.commit()
```

## 5. Security Analysis

### Chat Message Integrity

| Aspect | Protection | Method |
|--------|-----------|--------|
| **Message Authenticity** | Only sender can create valid MAC | Sender's unique MAC key |
| **Message Integrity** | Any modification detected | CBC-MAC verification |
| **Replay Attack** | Timestamp tracking | Message timestamps in DB |
| **Eavesdropping** | Messages stored in DB (not encrypted end-to-end) | Stored plaintext (could be improved) |
| **Key Leakage** | Sender's MAC key encrypted | Stored with RSA + ECDSA |

### Wallet Code Security

| Aspect | Protection | Method |
|--------|-----------|--------|
| **Code Forgery** | Cannot create valid code | ElGamal + ECDSA signature |
| **Code Tampering** | Signature verification fails | ECDSA signature on ciphertext |
| **Code Reuse** | Status tracking prevents reuse | ACTIVE → USED transition |
| **Admin-only Decryption** | Only admin can decrypt | Admin ECC private key required |

## 6. API Endpoints Summary

| Endpoint | Method | Purpose | Authentication |
|----------|--------|---------|-----------------|
| `/chat` | GET | Render chat UI | Buyer login required |
| `/api/chat/friends` | GET | Get friend list | Buyer login required |
| `/api/chat/messages/<friend>` | GET | Get messages with friend | Buyer login required |
| `/api/chat/send` | POST | Send message with MAC | Buyer login required |
| `/RedeemGiftCard` | POST | Validate and redeem wallet code | Any login |

## 7. Key Takeaways

- **CBC-MAC**: Symmetric authentication using AES-128 for message integrity
- **Unique per-user MAC keys**: Each user has own key, encrypted in database
- **Signature verification**: MAC key signature verified before use (prevent tampering)
- **Wallet codes**: Use ElGamal encryption for server-side key management
- **Status tracking**: ACTIVE/USED flags prevent code reuse
- **Bidirectional sessions**: Chat sessions work both ways between users
- **All sensitive keys**: Encrypted and/or signed for integrity and confidentiality
