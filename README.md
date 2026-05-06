# BashPO – Secure Game Publishing & Distribution Platform

**CSE447 Lab Project – Full Implementation with v1.2 Enhancements**

BashPO is a role‑based web platform where **buyers** purchase games, **developers** publish titles and manage product keys, and **administrators** oversee operations. The system enforces **exclusive asymmetric cryptography** (RSA + ECC + ElGamal) for all sensitive data, with **ECDSA** and **CBC‑MAC** providing strong integrity guarantees.

> ✅ All core requirements from the project specification are implemented, plus two major v1.2 features:
> - **Game key & wallet code system** (ElGamal encryption + ECDSA signatures)
> - **Chat message integrity** (CBC‑MAC with per‑user AES‑128 keys)

---

## 📁 Documentation Index

For detailed explanations of each subsystem, refer to the following markdown files:

| File | Description |
|------|-------------|
| [requirements_checklist.md](requirements_checklist.md) | Full compliance checklist covering core requirements, RBAC, v1.2 enhancements, and integrity methods (ECDSA + CBC‑MAC). |
| [crypto_overview.md](crypto_overview.md) | In‑depth description of RSA (from‑scratch prime generation, padding), ECC (secp256k1, point arithmetic, ECDSA), ElGamal over ECC, chunked key encryption, key rotation, and session management with a separate database. |
| [database_encryption_map.md](database_encryption_map.md) | Complete schema with per‑column encryption strategies: user RSA keys for personal data, admin RSA for private keys, admin ECC (ElGamal) for game keys / wallet codes / descriptions, and ECDSA signatures on every encrypted field. |
| [CHAT_AND_CBC_MAC_SYSTEM.md](CHAT_AND_CBC_MAC_SYSTEM.md) | Implementation of chat sessions, CBC‑MAC with AES‑128, per‑user MAC key storage (encrypted with RSA + signed), and wallet code redemption flow. |

---

## 🚀 Key Features

### Security & Cryptography
- **Asymmetric only** – RSA‑2048 for user data, ECDSA for signatures, ElGamal over secp256k1 for game keys / wallet codes.
- **Integrity by design** – Every encrypted field is accompanied by an ECDSA signature. Chat messages use CBC‑MAC (AES‑128).
- **User private keys** – Stored encrypted with the **admin RSA public key** using chunked encryption (RSA private keys exceed 245 bytes).
- **Key rotation** – Admin can rotate any user’s RSA+ECC keys, re‑encrypting all associated data.
- **Two‑factor authentication** – OTP via email (Resend) on every login.

### Access Control & Sessions
- **Role‑Based Access Control** – Buyers, developers, and administrators have separate dashboards and endpoint permissions.
- **Server‑side session tokens** – Stored in a dedicated `bashpo_secured_session.db` database, validated on every request.

### v1.2 Enhancements
- **Game Key Distribution** – Developers generate N UUID‑based keys, each encrypted with **ElGamal** (admin ECC public) and signed with **ECDSA** (admin ECC private). Status tracking (ACTIVE/USED) prevents reuse.
- **Wallet Code System** – Prepaid credit codes encrypted with the same ElGamal scheme, signed, and redeemed to increase buyer wallet balances.
- **Chat with CBC‑MAC** – Bidirectional chat sessions between friends. Each message includes a CBC‑MAC (AES‑128) computed with a per‑user key that is itself encrypted and signed.

---

## 🛠️ Running the Project

1. Clone the repository and install dependencies (Flask, PyJWT, requests, cryptography, sqlite3, etc.).
2. Configure environment variables:
   - `ADMIN_RSA_PUB`, `ADMIN_RSA_PRIV` (PEM format)
   - `ADMIN_ECC_PUB`, `ADMIN_ECC_PRIV` (as `"x:y"` strings)
   - `RESEND_API_KEY` (for OTP emails)
3. Initialize the databases:
   - `bashpos_--definitely--_secured_database.db` – main application data
   - `bashpo_secured_session.db` – session store
4. Run `app.py` (Flask development server or production WSGI).

> **Note** – The project sets `bcrypt` OTP emails to a test address; adjust `send_otp_email()` for production.

---

## 📊 Example Workflows

### Buyer purchases a game with a product key
1. Developer calls `/api/generate_keys` → N keys generated (ElGamal ciphertext + signature) and stored as ACTIVE.
2. Buyer enters the key on checkout → `prod_key_validation()` iterates over ACTIVE keys, verifies signature, decrypts, compares.
3. On match → `prod_key_activation_confirm()` inserts into `OWNED_GAMES` (encrypts amount paid with buyer’s RSA), marks key USED.

### Chat between two buyers
1. Both buyers have a MAC key encrypted with admin RSA (stored in `USERS.encrypted_mac_key`).
2. `/api/chat/send` → retrieve sender’s MAC key (decrypt with admin RSA), compute CBC‑MAC, store message + MAC.
3. `/api/chat/messages/<friend>` → retrieve all messages; optional server‑side verification of each MAC.

---

## 🧪 Integrity & Compliance

| Requirement | Implementation |
|-------------|----------------|
| Exclusive asymmetric encryption | RSA + ECC (no symmetric ciphers) |
| At least two different asymmetric algorithms | RSA (confidentiality) + ECC (signatures + ElGamal) |
| MAC (CBC‑MAC or HMAC) | CBC‑MAC with AES‑128 (per‑user keys) + ECDSA on all encrypted fields |
| Encryption before storage | Every sensitive column is ciphertext |
| Key management (generation, distribution, storage, rotation) | Admin‑controlled chunked RSA encryption for user private keys + rotation endpoint |
| Two‑step authentication | OTP via email |

All v1.2 requirements (game key / wallet code tables, gen_key, validation, activation, admin dashboard views) are fully met.

---

## 🤝 Acknowledgements

This project was developed as the final lab assignment for **CSE447 – Information Security** at the University of Washington (or similar). All cryptographic primitives (RSA, ECC point arithmetic, ECDSA, ElGamal over ECC, CBC‑MAC) are implemented from scratch for educational purposes.

For any questions, refer to the detailed markdown files linked above.