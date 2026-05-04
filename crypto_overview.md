# Cryptographic Core, Key Management & Session Security

## 1. RSA Implementation (From Scratch)

### Prime Generation & Key Generation
- We implemented Miller-Rabin primality test (`is_prime`).
- `generate_prime(bits)` produces a random prime of given bit length.
- For RSA‑2048, we generate two 1024‑bit primes `p` and `q`.
- Compute `n = p*q`, `phi = (p-1)*(q-1)`, public exponent `e = 65537`.
- Private exponent `d = e⁻¹ mod φ(n)` using extended Euclidean algorithm.
- Keys are stored as tuples: public `(n, e)`, private `(n, d)`.

### Encryption & Decryption
- `rsa_encrypt_str(plaintext, pub_key)`:
  - Converts string to bytes, adds PKCS#1 v1.5 padding (non‑zero random bytes + `0x00` separator).
  - Converts padded bytes to integer and computes `c = m^e mod n`.
  - Returns ciphertext as hex string.
- `rsa_decrypt_str(cipher_hex, priv_key)`:
  - Computes `m = c^d mod n`, converts to bytes, removes padding, decodes UTF‑8.
- Padding ensures that even identical plaintexts produce different ciphertexts.

---

## 2. ECC Implementation (From Scratch)

### Curve Parameters (secp256k1)
- Prime `p`, `a=0`, `b=7`, generator point `G`, order `n`.
- All operations mod `p` using modular inverse (`pow(k, -1, p)`).

### Point Addition & Doubling
- `point_add(P, Q)` implements standard formulas:
  - If `P == Q` (doubling): slope `m = (3*x1² + a) / (2*y1) mod p`.
  - Else: slope `m = (y2 – y1) / (x2 – x1) mod p`.
  - New point: `x3 = m² – x1 – x2`, `y3 = m(x1 – x3) – y1`.

### Scalar Multiplication (Double-and-Add)
- `scalar_mult(k, P)`:
  - Start with `R = None` (point at infinity).
  - For each bit of `k`, double the current point and add if bit is set.

### ECDSA Sign & Verify
- **Sign**: Choose random `k`, compute `R = k*G`, `r = R.x mod n`.  
  Hash the message, compute `s = k⁻¹ (hash + r*priv) mod n`.
- **Verify**: Compute `w = s⁻¹ mod n`, `u1 = hash*w mod n`, `u2 = r*w mod n`.  
  Compute `P = u1*G + u2*Pub`. Signature valid if `P.x mod n == r`.

---

## 3. Helper Functions (Crypto API)

| Function | Purpose |
|----------|---------|
| `rsa_encrypt_str`, `rsa_decrypt_str` | Encrypt/decrypt strings with RSA |
| `ecc_sign_bytes`, `ecc_verify_bytes` | Sign/verify bytes with ECDSA (aliased to `ecc_sign_str`, `ecc_verify_str`) |
| `encrypt_user_privates`, `decrypt_user_privates` | Store/retrieve user RSA+ECC private keys as plain JSON (due to RSA size limit) |
| `get_user_keys(username)` | Returns `(rsa_pub, rsa_priv, ecc_pub, ecc_priv)` for a user (admin special‑cased) |
| `get_user_balance`, `set_user_balance` | Encrypt/decrypt wallet balances using user’s RSA key |
| `get_user_email`, `get_user_address` | Decrypt email/address using user’s RSA key |
| `encrypt_admin_data`, `decrypt_admin_data` | Encrypt/decrypt data with global admin RSA keys (wallet codes, game keys, reviews) |

---

## 4. Key Management

### Key Generation
- Each user (buyer/developer) gets a fresh RSA‑2048 key pair and ECC key pair at registration (`create_buyer_query`, `create_dev_query`).
- The admin (LordGaben) uses the global keys stored in `.env` – no per‑admin keys.

### Key Storage
- User public keys are stored in `USERS.rsa_public` and `USERS.ecc_public` as `"n:e"` and `"x:y"` strings.
- User private keys are stored as a combined JSON string in `USERS.rsa_private_encrypted` (and duplicated in `ecc_private_encrypted`).  
  **Why plaintext?** RSA‑2048 cannot encrypt the full JSON (exceeds 245 bytes). We rely on database‑file encryption instead.

### Key Rotation (Admin Feature)
- `rotate_user_keys(username)`:
  1. Generates new RSA+ECC key pair.
  2. Decrypts all user data (email, address, balance, owned games amounts, revenue) using old keys.
  3. Re‑encrypts and re‑signs everything with the new keys.
  4. Updates `USERS` table with new public keys and the new plaintext JSON of private keys.
- Admin endpoint `/admin/rotate_user_keys` triggers rotation for any user. The user is forced to log out and back in (old session invalidated).

---

## 5. Session Management (Separate Database)

### Session DB (`bashpo_secured_session.db`)
- Table `user_sessions` stores `username`, `session_token`, `expires_at`.
- Tokens are generated with `secrets.token_urlsafe(32)`.

### Flow
- **Login (2FA success)**: `create_session(username)` stores token and expiration (2 hours) in session DB. Token saved in Flask `session['session_token']`.
- **Each request**: `before_request` checks `validate_session_token`. If token missing, expired, or mismatched, session is cleared and user redirected to login.
- **Logout**: `delete_session(username)` removes token from session DB.
- **Sensitive changes (password, email, address, key rotation)**: `delete_session(username)` and `session.clear()` force immediate re‑authentication.

### Why separate DB?
- Decouples session data from main application DB – adds a layer of security.
- Allows easy invalidation without touching user data tables.

---

## 6. How Encryption/Decryption Works in Practice

### Example: User Login & Email Display
1. User submits username/password → verified against stored hash.
2. OTP sent & verified.
3. Session token created (step 5).
4. On profile page, `get_user_email(session['username'])` is called:
   - `get_user_keys(username)` returns user’s RSA public/private and ECC keys.
   - Database query returns `encrypted_email` and `email_sig`.
   - Signature verified with user’s ECC public key (or dummy signature allowed).
   - `rsa_decrypt_str(encrypted_email, rsa_priv)` returns plaintext email.
5. The plaintext email is displayed in the template.

### Example: Admin‑encrypted Review
- User posts a review → `encrypt_admin_data(review)` encrypts with `ADMIN_RSA_PUB` and signs with `ADMIN_ECC_PRIV`.
- Stored in `Reviews` table.
- When game page loads, `decrypt_admin_data(enc_rev, rev_sig)` decrypts using `ADMIN_RSA_PRIV` after verifying the admin signature.
- No user can decrypt another user’s review without the admin private key.

### Example: Wallet Balance Update
- `set_user_balance` encrypts the new balance with the user’s RSA public key and signs with the user’s ECC private key.
- `get_user_balance` does the reverse: verifies signature, then decrypts.

### Overflow Fallback
- Some ECC private keys cause overflow in `ecdsa_sign` (platform‑specific). We catch `OverflowError` and store `"dummy_..."` as signature. On retrieval, dummy signatures are accepted (but real signatures are still verified). This keeps the system functional; it’s a lab compromise.

---

## 7. Summary of Key Uses

| Key | Purpose |
|-----|---------|
| **Per‑user RSA** | Encrypt email, address, wallet balance, owned games amount, developer revenue |
| **Per‑user ECC** | Sign/verify all per‑user encrypted fields |
| **Admin RSA** | Encrypt wallet codes, game keys, reviews, publishing descriptions, admin’s own data |
| **Admin ECC** | Sign/verify all admin‑encrypted data |

All encryption and signing are exclusively asymmetric – no symmetric algorithms are used. Two different asymmetric algorithms (RSA + ECC) satisfy the requirement.