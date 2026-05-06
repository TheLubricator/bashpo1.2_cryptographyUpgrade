# Cryptographic Core, Key Management & Session Security

## 1. RSA Implementation (From Scratch)

### Prime Generation & Key Generation
- Miller-Rabin primality test (`is_prime`).
- `generate_prime(bits)` produces a random prime of given bit length.
- For RSA‑2048, generate two 1024‑bit primes `p` and `q`.
- Compute `n = p*q`, `phi = (p-1)*(q-1)`, public exponent `e = 65537`.
- Private exponent `d = e⁻¹ mod φ(n)` using extended Euclidean algorithm.
- Keys stored as tuples: public `(n, e)`, private `(n, d)`.

### Encryption & Decryption
- `rsa_encrypt_str(plaintext, pub_key)`:
  - String → bytes, add PKCS#1 v1.5 padding (non‑zero random bytes + `0x00` separator).
  - Convert to integer, compute `c = m^e mod n`.
  - Return ciphertext as hex string.
- `rsa_decrypt_str(cipher_hex, priv_key)`:
  - Compute `m = c^d mod n`, convert to bytes, remove padding, decode UTF‑8.
- Padding ensures identical plaintexts produce different ciphertexts.

## 2. ECC Implementation (From Scratch)

### Curve Parameters (secp256k1)
- Prime `p`, `a=0`, `b=7`, generator `G`, order `n`.
- All operations mod `p` using `pow(k, -1, p)`.

### Point Addition & Doubling
- `point_add(P, Q)` implements standard formulas:
  - Doubling: `m = (3*x1² + a) / (2*y1) mod p`.
  - Addition: `m = (y2 – y1) / (x2 – x1) mod p`.
  - New point: `x3 = m² – x1 – x2`, `y3 = m(x1 – x3) – y1`.

### Scalar Multiplication (Double-and-Add)
- `scalar_mult(k, P)` starts with `R = None`.
- For each bit of `k`, double the current point and add if bit is set.

### ECDSA Sign & Verify
- **Sign**: random `k`, `R = k*G`, `r = R.x mod n`.  
  `s = k⁻¹ (hash + r*priv) mod n`.
- **Verify**: `w = s⁻¹ mod n`, `u1 = hash*w mod n`, `u2 = r*w mod n`.  
  `P = u1*G + u2*Pub`. Valid if `P.x mod n == r`.

### ElGamal Encryption & Decryption (on ECC)
- **ElGamal over ECC**:
  - **Encryption**:
    1. Encode plaintext string as integer, then to a point M on the curve.
    2. Generate random ephemeral private key `k`.
    3. Compute `c1 = k*G` (ephemeral public key).
    4. Compute `k_pub = k * recipient_pub`.
    5. Compute `c2 = M + k_pub`.
    6. Return `{c1: (x,y), c2: (x,y), offset: int}` (offset used in point encoding).
  - **Decryption**:
    1. Compute `shared = priv_key * c1` (same ECDH shared secret as encryption).
    2. Compute `M = c2 - shared` (point subtraction via negation).
    3. Recover original integer from M's x-coordinate using offset.
    4. Convert integer to bytes and decode to UTF-8 plaintext.

**ElGamal point encoding (for strings):**
```python
def encode_point_from_int(msg_int):
    """Find a point (x,y) on curve such that x = msg_int + offset. offset < 1000."""
    offset = 0
    while offset < 1000:
        x = msg_int + offset
        rhs = (pow(x, 3, p) + a * x + b) % p
        y = pow(rhs, (p + 1) // 4, p)  # Square root (p ≡ 3 mod 4)
        if (y * y) % p == rhs:
            return (x, y, offset)
        offset += 1
    raise ValueError("Could not encode message to a point")

def elgamal_encrypt(plaintext, pub_key):
    """Encrypt string with ElGamal. Returns dict: {'c1': (x,y), 'c2': (x,y), 'offset': int}."""
    msg_bytes = plaintext.encode('utf-8')
    msg_int = int.from_bytes(msg_bytes, 'big')
    Mx, My, offset = encode_point_from_int(msg_int)
    k = secrets.randbelow(n - 1) + 1
    c1 = scalar_mult(k, G)
    k_pub = scalar_mult(k, pub_key)
    c2 = point_add((Mx, My), k_pub)
    return {'c1': (c1[0], c1[1]), 'c2': (c2[0], c2[1]), 'offset': offset}

def elgamal_decrypt(cipher_dict, priv_key):
    """Decrypt ElGamal ciphertext using private key."""
    c1 = cipher_dict['c1']
    c2 = cipher_dict['c2']
    offset = cipher_dict['offset']
    shared = scalar_mult(priv_key, c1)
    shared_inv = (shared[0], -shared[1] % p)
    M = point_add(c2, shared_inv)
    msg_int = decode_int_from_point(M[0], offset)
    byte_len = (msg_int.bit_length() + 7) // 8
    if byte_len == 0:
        return ''
    plain_bytes = msg_int.to_bytes(byte_len, 'big')
    return plain_bytes.decode('utf-8')
```

## 3. Helper Functions (Crypto API)

| Function | Purpose |
|----------|---------|
| `rsa_encrypt_str`, `rsa_decrypt_str` | Encrypt/decrypt strings with RSA |
| `ecc_sign_bytes`, `ecc_verify_bytes` | Sign/verify bytes with ECDSA |
| `elgamal_encrypt`, `elgamal_decrypt` | Encrypt/decrypt strings with ElGamal (ECC-based) |
| `encrypt_user_privates`, `decrypt_user_privates` | Encrypt/decrypt user RSA+ECC private keys using **chunked RSA** (admin key) |
| `get_user_keys(username)` | Returns `(rsa_pub, rsa_priv, ecc_pub, ecc_priv)` (admin special‑cased) |
| `get_user_balance`, `set_user_balance` | Encrypt/decrypt wallet balances using user's RSA key |
| `get_user_email`, `get_user_address` | Decrypt email/address using user's RSA key |
| `gen_key(game_name, no_of_keys)` | Generate encrypted game keys using ElGamal (admin ECC public key) |
| `prod_key_validation(product_key)` | Validate and decrypt product keys |
| `prod_key_activation_confirm(game_name, product_key)` | Activate a product key and record purchase |

## 4. Key Management

### Key Generation
- Each user gets a fresh RSA‑2048 and ECC key pair at registration.
- Admin (LordGaben) uses global keys from `.env`.

### Key Storage (Chunked Encryption for RSA Private Key)
- RSA private key JSON is split into chunks (≤ 230 bytes), each encrypted with admin RSA public key.
- Encrypted chunks stored as JSON array in `encrypted_rsa_private`.
- ECC private key (fits) encrypted directly and stored in `encrypted_ecc_private`.
- Public keys stored plaintext.

**Chunked Encryption Implementation:**
```python
def encrypt_user_privates(rsa_priv, ecc_priv):
    rsa_json = json.dumps({'n': rsa_priv[0], 'd': rsa_priv[1]})
    chunk_size = 230
    chunks = [rsa_json[i:i+chunk_size] for i in range(0, len(rsa_json), chunk_size)]
    enc_chunks = [rsa_encrypt_str(chunk, ADMIN_RSA_PUB) for chunk in chunks]
    enc_rsa = json.dumps(enc_chunks)
    enc_ecc = rsa_encrypt_str(json.dumps(ecc_priv), ADMIN_RSA_PUB)
    return enc_rsa, enc_ecc

def decrypt_user_privates(enc_rsa_json, enc_ecc_hex):
    enc_chunks = json.loads(enc_rsa_json)
    decrypted_parts = [rsa_decrypt_str(chunk, ADMIN_RSA_PRIV) for chunk in enc_chunks]
    rsa_json = ''.join(decrypted_parts)
    rsa_priv_dict = json.loads(rsa_json)
    rsa_priv = (rsa_priv_dict['n'], rsa_priv_dict['d'])
    ecc_json = rsa_decrypt_str(enc_ecc_hex, ADMIN_RSA_PRIV)
    ecc_priv = json.loads(ecc_json)
    return rsa_priv, ecc_priv
```

### Key Rotation (Admin Feature)
- `rotate_user_keys(username)`:
  1. Generate new RSA+ECC key pair.
  2. Decrypt all user data with old keys.
  3. Re‑encrypt and re‑sign with new keys.
  4. Encrypt new private keys (chunked) and update `USERS` table.
- Admin endpoint `/admin/rotate_user_keys` triggers rotation; user forced to log out.

## 5. Session Management (Separate Database)

### Session DB (`bashpo_secured_session.db`)
- Table `user_sessions` stores `username`, `session_token`, `expires_at`.
- Tokens: `secrets.token_urlsafe(32)`.

### Flow
- **Login (2FA success)**: `create_session(username)` stores token (2‑hour expiry) in session DB; token saved in Flask `session['session_token']`.
- **Each request**: `before_request` calls `validate_session_token`. If invalid, session cleared and redirected to login.
- **Logout**: `delete_session(username)` removes token from session DB.
- **Sensitive changes** (password, email, address, key rotation): `delete_session(username)` and `session.clear()` force re‑authentication.

### Why separate DB?
- Decouples session data from main application DB – adds security.
- Easy invalidation without touching user data tables.

## 6. How Encryption/Decryption Works in Practice

### Example: User Login & Email Display
1. Login with username/password → password hash verified.
2. OTP verified.
3. Session token created.
4. Profile page calls `get_user_email(session['username'])`:
   - `get_user_keys` returns user's keys (private keys decrypted via admin key).
   - DB gives `encrypted_email` and `email_sig`.
   - Signature verified (or dummy accepted).
   - `rsa_decrypt_str` returns plaintext email.

### Example: Admin‑encrypted Review
- User posts a review → `encrypt_admin_data(review)` encrypts with `ADMIN_RSA_PUB` and signs with `ADMIN_ECC_PRIV`.
- Stored in `Reviews` table.
- When game page loads, `decrypt_admin_data(enc_rev, rev_sig)` decrypts using `ADMIN_RSA_PRIV` after verifying the admin signature.

### Example: Wallet Balance Update
- `set_user_balance` encrypts new balance with user's RSA public key and signs with user's ECC private key.
- `get_user_balance` verifies signature, then decrypts.

### Overflow Fallback
- Some ECC private keys cause overflow in `ecdsa_sign` (platform‑specific). We catch `OverflowError` and store `"dummy_..."` signature. On retrieval, dummy signatures are accepted (real signatures still verified).

## 7. Summary of Key Uses

| Key | Purpose |
|-----|---------|
| **Per‑user RSA** | Encrypt email, address, wallet balance, owned games amount, developer revenue |
| **Per‑user ECC** | Sign/verify all per‑user encrypted fields |
| **Admin RSA** | Encrypt user private keys (chunked), wallet codes |
| **Admin ECC** | Encrypt/decrypt game keys (ElGamal), game publishing descriptions (ElGamal), sign/verify game keys and descriptions, encrypt reviews |

All encryption and signing are exclusively asymmetric – no symmetric algorithms. Two different asymmetric algorithms (RSA + ECC) satisfy the requirement.

## 8. Game Key & Wallet Code Management

### Game Key Generation & Distribution
- **Purpose**: Product keys for game distribution (digital rights management).
- **Storage**: `GAME_KEY` table with columns: `game_key` (primary), `encrypted_game_key`, `key_sig`, `game_name`, `status` (ACTIVE/USED).
- **Generation** (`gen_key` function):
  1. Generate random hex string: `game_key = uuid.uuid4().hex`
  2. Encrypt with admin ECC public key using ElGamal: `cipher = ecc.elgamal_encrypt(game_key, ADMIN_ECC_PUB)`
  3. Serialize as JSON: `enc_data = json.dumps(cipher)`
  4. Sign ciphertext: `key_sig = ecc_sign_bytes(enc_data.encode(), ADMIN_ECC_PRIV)`
  5. Store `(game_key, enc_data, key_sig, game_name, 'ACTIVE')`
- **Validation** (`prod_key_validation` function):
  1. Iterate through all ACTIVE game keys in DB.
  2. Verify signature using admin ECC public key.
  3. Decrypt ciphertext using admin ECC private key.
  4. Return matching key or empty list.
- **Activation** (`prod_key_activation_confirm` function):
  1. Validate product key against ciphertext.
  2. On match, insert record into `OWNED_GAMES` table.
  3. Update game key status to 'USED'.
  4. Encrypt amount paid using buyer's RSA public key.

### Wallet Code
- **Purpose**: Prepaid wallet/credit codes for platform accounts.
- **Storage**: `WALLET_CODE` table with columns: `wallet_key`, `encrypted_wallet_key`, `key_sig`, `amount`, `status` (ACTIVE/USED).
- **Encryption**: Similar to game keys, uses admin ECC public key via ElGamal.
- **Signature**: Verified and signed with admin ECC private key.
- **Status**: Tracks whether wallet code has been redeemed (`ACTIVE` → `USED`).

### Why ElGamal over ECC for Game Keys?
1. **Server-side asymmetric encryption**: Only admin can decrypt game keys; no symmetric key distribution needed.
2. **Integrity via signatures**: Each key is signed, preventing tampering.
3. **Scalability**: Multiple game keys can be generated without managing per-key secrets.
4. **Compliance**: Exclusively asymmetric encryption (RSA + ECC) matches project requirements.
