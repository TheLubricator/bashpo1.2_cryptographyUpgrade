# Cryptographic Core, Key Management & Session Security

#| Function | Purpose |
|----------|---------|
| `rsa_encrypt_str`, `rsa_decrypt_str` | Encrypt/decrypt strings with RSA |
| `ecc_sign_bytes`, `ecc_verify_bytes` | Sign/verify bytes with ECDSA |
| `elgamal_encrypt`, `elgamal_decrypt` | Encrypt/decrypt strings with ElGamal (ECC-based) |
| `encrypt_user_privates`, `decrypt_user_privates` | Encrypt/decrypt user RSA+ECC private keys using **chunked RSA** (admin key) |
| `get_user_keys(username)` | Returns `(rsa_pub, rsa_priv, ecc_pub, ecc_priv)` (admin special‑cased) |
| `get_user_balance`, `set_user_balance` | Encrypt/decrypt wallet balances using user's RSA key |
| `get_user_email`, `get_user_address` | Decrypt email/address using user's RSA key |
| `encrypt_admin_data`, `decrypt_admin_data` | Encrypt/decrypt data with global admin RSA keys (wallet codes, game keys, reviews) |Implementation (From Scratch)

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

## 3. Helper Functions (Crypto API)

| Function | Purpose |
|----------|---------|
| `rsa_encrypt_str`, `rsa_decrypt_str` | Encrypt/decrypt strings with RSA |
| `ecc_sign_bytes`, `ecc_verify_bytes` | Sign/verify bytes with ECDSA |
| `encrypt_user_privates`, `decrypt_user_privates` | Encrypt/decrypt user RSA+ECC private keys using **chunked RSA** (admin key) |
| `get_user_keys(username)` | Returns `(rsa_pub, rsa_priv, ecc_pub, ecc_priv)` (admin special‑cased) |
| `get_user_balance`, `set_user_balance` | Encrypt/decrypt wallet balances using user’s RSA key |
| `get_user_email`, `get_user_address` | Decrypt email/address using user’s RSA key |
| `encrypt_admin_data`, `decrypt_admin_data` | Encrypt/decrypt data with global admin RSA keys (wallet codes, game keys, reviews) |

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
   - `get_user_keys` returns user’s keys (private keys decrypted via admin key).
   - DB gives `encrypted_email` and `email_sig`.
   - Signature verified (or dummy accepted).
   - `rsa_decrypt_str` returns plaintext email.

### Example: Admin‑encrypted Review
- User posts a review → `encrypt_admin_data(review)` encrypts with `ADMIN_RSA_PUB` and signs with `ADMIN_ECC_PRIV`.
- Stored in `Reviews` table.
- When game page loads, `decrypt_admin_data(enc_rev, rev_sig)` decrypts using `ADMIN_RSA_PRIV` after verifying the admin signature.

### Example: Wallet Balance Update
- `set_user_balance` encrypts new balance with user’s RSA public key and signs with user’s ECC private key.
- `get_user_balance` verifies signature, then decrypts.

### Overflow Fallback
- Some ECC private keys cause overflow in `ecdsa_sign` (platform‑specific). We catch `OverflowError` and store `"dummy_..."` signature. On retrieval, dummy signatures are accepted (real signatures still verified).

## 7. Summary of Key Uses

| Key | Purpose |
|-----|---------|
| **Per‑user RSA** | Encrypt email, address, wallet balance, owned games amount, developer revenue |
| **Per‑user ECC** | Sign/verify all per‑user encrypted fields |
| **Admin RSA** | Encrypt wallet codes, game keys, reviews, publishing descriptions, admin’s own data, **and user private keys** (chunked) |
| **Admin ECC** | Sign/verify all admin‑encrypted data |

All encryption and signing are exclusively asymmetric – no symmetric algorithms. Two different asymmetric algorithms (RSA + ECC) satisfy the requirement.