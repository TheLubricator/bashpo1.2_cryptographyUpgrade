# Database Schema & Encryption Mapping

## Tables and Encrypted Columns

### Encryption Strategy Overview
- **User‑specific sensitive data** encrypted with **user's own RSA public key**.
- **User private keys** encrypted with **admin RSA public key** (chunked for RSA private key). This ensures that even if the database is stolen, private keys remain ciphertext without the admin private key (stored in `.env`).
- **Server‑only data** encrypted with **admin ECC public key via ElGamal** (e.g., wallet codes, game keys).
- **Game publishing descriptions** encrypted with **admin ECC public key via ElGamal**.
- **Asymmetric encryption only** – RSA for user data, ElGamal over ECC for game keys/wallet codes/descriptions, no symmetric ciphers.
- **Integrity** via ECDSA signatures using same key type as encryption (user ECC for user data, admin ECC for admin data).

### 1. `USERS` Table
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username` | No | – | Primary key, used in joins |
| `password` | No (hashed) | – | Hashed with salt |
| `store_region` | No | – | Used for price calculation |
| `card_info` | No | – | Not used (payment gateway) |
| `company_name` | No | – | Public info |
| `publisher_name` | No | – | Public info |
| `user_type`, `account_status` | No | – | RBAC logic |
| **`encrypted_email`** | Yes | **User's RSA public** | Personal info |
| `email_sig` | N/A | **User's ECC private** | Integrity |
| **`encrypted_buyer_address`** | Yes | **User's RSA public** | Personal address |
| `address_sig` | N/A | **User's ECC private** | Integrity |
| `rsa_public`, `ecc_public` | No | – | Public keys stored plain |
| **`encrypted_rsa_private`** | Yes | **Admin RSA public (chunked)** | User's RSA private key |
| **`encrypted_ecc_private`** | Yes | **Admin RSA public** | User's ECC private key |

### 2. `WALLET_BALANCE`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username` | No | – | Foreign key |
| **`encrypted_balance`** | Yes | **User's RSA public** | Financial data |
| `balance_sig` | N/A | **User's ECC private** | Integrity |

### 3. `GAME_PUBLISH_REQUEST`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| Most columns | No | – | Not sensitive |
| **`encrypted_basic_description`** | Yes | **Admin ECC public (ElGamal)** | Only admin reads; uses ElGamal over ECC |
| Stored as | – | – | JSON dict with `c1`, `c2`, `offset` |

### 4. `GAME_LIST`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| Most columns | No | – | Public metadata |
| **`encrypted_revenue_generated`** | Yes | **Developer's RSA public** | Only developer sees revenue |
| `revenue_sig` | N/A | **Developer's ECC private** | Integrity |

### 5. `OWNED_GAMES`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username`, `game_name`, `purchase_type`, `posted_review` | No | – | Foreign keys, status |
| **`encrypted_amount_paid`** | Yes | **Buyer's RSA public** | Purchase amount |
| `amount_sig` | N/A | **Buyer's ECC private** | Integrity |

### 6. `WALLET_CODE` Table
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `wallet_key` | No | – | Primary key (plaintext for reference) |
| **`encrypted_wallet_key`** | Yes | **Admin ECC public (ElGamal)** | Prepaid credit code; only admin can decrypt |
| `key_sig` | N/A | **Admin ECC private** | Verify integrity before decryption |
| `amount` | No | – | Metadata (credit amount) |
| `status` | No | – | ACTIVE (unused) or USED (redeemed) |

**Implementation:**
```python
# Generate wallet code
wallet_key = uuid.uuid4().hex  # Plain reference key
cipher = ecc.elgamal_encrypt(wallet_key, ADMIN_ECC_PUB)  # ElGamal encryption
enc_data = json.dumps(cipher)  # Store as JSON
key_sig = ecc_sign_bytes(enc_data.encode(), ADMIN_ECC_PRIV)  # Sign ciphertext
# Insert into DB with amount and ACTIVE status
```

### 7. `GAME_KEY` Table
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `game_key` | No | – | Primary key (plaintext for reference) |
| **`encrypted_game_key`** | Yes | **Admin ECC public (ElGamal)** | Product key; only admin can decrypt |
| `key_sig` | N/A | **Admin ECC private** | Verify integrity before decryption |
| `game_name` | No | – | Foreign key to GAME_LIST |
| `status` | No | – | ACTIVE (available) or USED (redeemed) |

**Implementation:**
```python
# Generate game key (in gen_key function)
game_key = uuid.uuid4().hex  # Plain reference key
cipher = ecc.elgamal_encrypt(game_key, ADMIN_ECC_PUB)  # ElGamal encryption
enc_data = json.dumps(cipher)  # Store as JSON
key_sig = ecc_sign_bytes(enc_data.encode(), ADMIN_ECC_PRIV)  # Sign ciphertext
# Insert into DB: (game_key, enc_data, key_sig, game_name, 'ACTIVE')

# Validate product key (in prod_key_validation function)
for stored_key, enc_data, key_sig, game_name, status in active_keys:
    if not ecc_verify_bytes(enc_data.encode(), key_sig, ADMIN_ECC_PUB):
        continue  # Skip tampered keys
    cipher_dict = json.loads(enc_data)
    decrypted_key = ecc.elgamal_decrypt(cipher_dict, ADMIN_ECC_PRIV)
    if decrypted_key == user_product_key:
        return (stored_key, enc_data, key_sig, game_name, status)

# Activate product key (in prod_key_activation_confirm function)
if prod_key_validation(product_key):
    insert_into_owned_games(username, game_name, encrypted_amount_paid)
    update_game_key_status(product_key, 'USED')
```

### 8. `Reviews`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `game_name`, `username`, `rating` | No | – | Not sensitive |
| **`encrypted_review`** | Yes | **Admin RSA public** | Review text (may contain PII) |
| `review_sig` | N/A | **Admin ECC private** | Integrity |

### 9. Other Tables (`WISHLIST`, `CART_SYSTEM`, `SENT_FRIEND_REQUEST`, `FRIENDS`, `otp_codes`)
- No encryption – contain only usernames, game names, flags, ephemeral OTPs.

## Why This Mapping?

- **User‑specific sensitive data** encrypted with **user's own RSA public key**: Only the user (and admin) can decrypt their personal data.
- **User private keys** encrypted with **admin RSA public key** (chunked): Protects against database theft.
- **Game keys & Wallet codes** encrypted with **admin ECC public key via ElGamal**: Only admin can decrypt these server-managed items; prevents unauthorized key generation or forgery.
- **No symmetric encryption**: Exclusively RSA + ECC (asymmetric).
- **Integrity via ECDSA**: All sensitive data is signed and verified before use.

## Functional Workflows

### Game Key Distribution Flow
```
1. Developer requests N game keys (gen_key endpoint)
   └─> Server generates N random keys
   └─> Each key encrypted with ElGamal (admin ECC public)
   └─> Each ciphertext signed with admin ECC private
   └─> All stored in GAME_KEY table with status='ACTIVE'

2. Buyer enters product key during purchase
   └─> prod_key_validation: Decrypt all ACTIVE keys
   └─> Compare decrypted key with buyer's input
   └─> If match: Verify signature, return row details

3. After buyer confirms purchase
   └─> prod_key_activation_confirm: Record in OWNED_GAMES
   └─> Update GAME_KEY.status = 'USED'
   └─> Buyer now owns game
```

### Wallet Code Redemption Flow
```
1. Admin/system generates wallet codes
   └─> Each code encrypted with ElGamal (admin ECC public)
   └─> Ciphertext signed with admin ECC private
   └─> Stored with amount and status='ACTIVE'

2. Buyer receives code (out-of-band)
   └─> Enters code in account settings

3. System validates code
   └─> Decrypt all ACTIVE wallet codes
   └─> Match against buyer input
   └─> Verify signature before use

4. On redemption
   └─> Update buyer's wallet balance (encrypted with buyer's RSA)
   └─> Update wallet code status = 'USED'
```

### Game Description Publishing Flow
```
1. Developer submits game description
   └─> Encrypt description with ElGamal (admin ECC public)
   └─> Store ciphertext + signature in GAME_PUBLISH_REQUEST

2. Admin reviews publishing requests
   └─> Decrypt description using admin ECC private key
   └─> Verify signature first (reject if tampered)
   └─> Display plaintext to admin

3. On approval
   └─> Create new GAME_LIST entry with encrypted description
   └─> Continue encrypting with same admin ECC key
```
