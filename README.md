# BashPo – Secure Game Store with Asymmetric Cryptography

This project is a complete implementation of a **secure digital game store** (similar to Steam) developed for the CSE447 lab. It satisfies all requirements of the assignment:

- **Login & Registration** with password hashing (SHA‑256 + salt)
- **Two‑factor authentication** (OTP via Resend)
- **Asymmetric encryption only** (RSA for confidentiality, ECC for digital signatures)
- **No symmetric encryption** – exclusively RSA and ECDSA
- **Role‑Based Access Control** (Buyer, Developer, Admin)
- **Key management** – generation, encrypted storage, and rotation
- **Secure session management** with server‑side tokens
- **Encryption of all sensitive data** (email, address, wallet balance, revenue, amount paid, wallet keys, game keys, reviews, publishing descriptions) – stored encrypted, decrypted on retrieval
- **Integrity** via ECDSA signatures for every encrypted field

The system is built with **Flask**, **SQLite**, and custom‑implemented RSA (PKCS#1 v1.5) and ECC (secp256k1) from scratch, without using any built‑in cryptographic libraries (except for hashing and secure random).

---

## Repository Structure
bashpov1.1/
├── app.py # Main Flask application (routes, login, 2FA, session)
├── model/
│ ├── req_auth.py # Crypto helpers, key management, DB schema, registration
│ └── route_help.py # Business logic (dashboards, cart, payments, reviews, key rotation)
├── crypto/
│ ├── rsa.py # RSA implementation (prime generation, encrypt, decrypt, padding)
│ └── ecc.py # ECC implementation (secp256k1, point ops, ECDSA)
├── session_manager.py # Separate session DB with token validation
├── templates/ # All HTML templates (DaisyUI + Tailwind)
├── static/ # Images, CSS, uploaded game files
├── .env # Environment variables (admin keys, API keys)
└── requirements.txt # Python dependencies
---

## Detailed Documentation

For in‑depth explanations, please refer to the following markdown files:

| File | Description |
|------|-------------|
| [`crypto_overview.md`](crypto_overview.md) | How RSA and ECC work from scratch, helper functions, key management (generation, chunked encryption of private keys, rotation), and session security. |
| [`database_encryption_map.md`](database_encryption_map.md) | Complete database schema, which columns are encrypted, which keys are used (per‑user RSA, per‑user ECC, admin RSA/ECC), and why. |
| [`requirements_checklist.md`](requirements_checklist.md) | A line‑by‑line check of every lab requirement, with implementation details and justifications. |

---

## Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
2. Generate admin keys (run once)
 ```bash
 python generate_admin_key.py
 ```
3. Run the application
```bash
 python app.py
 ```
The server starts at http://127.0.0.1:1097.
4. Default admin login
- Username: LordGaben

-Password: 123456

-OTP is always sent to kansainoryu404@gmail.com (test mode). The OTP code will appear in that inbox. (want to  change? find the api key then change the test email)
