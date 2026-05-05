# Database Schema & Encryption Mapping

## Tables and Encrypted Columns

### 1. `USERS`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username` | No | – | Primary key, used in joins |
| `password` | No (hashed) | – | Hashed with salt |
| `store_region` | No | – | Used for price calculation |
| `card_info` | No | – | Not used (payment gateway) |
| `company_name` | No | – | Public info |
| `publisher_name` | No | – | Public info |
| `user_type`, `account_status` | No | – | RBAC logic |
| **`encrypted_email`** | Yes | **User’s RSA public** | Personal info |
| `email_sig` | N/A | **User’s ECC private** | Integrity |
| **`encrypted_buyer_address`** | Yes | **User’s RSA public** | Personal address |
| `address_sig` | N/A | **User’s ECC private** | Integrity |
| `rsa_public`, `ecc_public` | No | – | Public keys stored plain |
| **`encrypted_rsa_private`** | Yes | **Admin RSA public (chunked)** | User’s RSA private key |
| **`encrypted_ecc_private`** | Yes | **Admin RSA public** | User’s ECC private key |

### 2. `WALLET_BALANCE`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username` | No | – | Foreign key |
| **`encrypted_balance`** | Yes | **User’s RSA public** | Financial data |
| `balance_sig` | N/A | **User’s ECC private** | Integrity |

### 3. `GAME_PUBLISH_REQUEST`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| Most columns | No | – | Not sensitive |
| **`encrypted_basic_description`** | Yes | **Admin RSA public** | Only admin reads |
| `desc_sig` | N/A | **Admin ECC private** | Integrity |

### 4. `GAME_LIST`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| Most columns | No | – | Public metadata |
| **`encrypted_revenue_generated`** | Yes | **Developer’s RSA public** | Only developer sees revenue |
| `revenue_sig` | N/A | **Developer’s ECC private** | Integrity |

### 5. `OWNED_GAMES`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `username`, `game_name`, `purchase_type`, `posted_review` | No | – | Foreign keys, status |
| **`encrypted_amount_paid`** | Yes | **Buyer’s RSA public** | Purchase amount |
| `amount_sig` | N/A | **Buyer’s ECC private** | Integrity |

### 6. `WALLET_CODE`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `wallet_key` (replaced) | – | – | Not stored plain |
| **`encrypted_wallet_key`** | Yes | **Admin RSA public** | Server‑only decryption |
| `key_sig` | N/A | **Admin ECC private** | Integrity |
| `amount`, `status` | No | – | Metadata |

### 7. `GAME_KEY`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `game_key` (replaced) | – | – | Not stored plain |
| **`encrypted_game_key`** | Yes | **Admin RSA public** | Server‑only decryption |
| `key_sig` | N/A | **Admin ECC private** | Integrity |
| `game_name`, `status` | No | – | Metadata |

### 8. `Reviews`
| Column | Encrypted? | Key Used | Reason |
|--------|------------|----------|--------|
| `game_name`, `username`, `rating` | No | – | Not sensitive |
| **`encrypted_review`** | Yes | **Admin RSA public** | Review text (may contain PII) |
| `review_sig` | N/A | **Admin ECC private** | Integrity |

### 9. Other Tables (`WISHLIST`, `CART_SYSTEM`, `SENT_FRIEND_REQUEST`, `FRIENDS`, `otp_codes`)
- No encryption – contain only usernames, game names, flags, ephemeral OTPs.

## Why This Mapping?

- **User‑specific sensitive data** encrypted with **user’s own RSA public key**.
- **User private keys** encrypted with **admin RSA public key** (chunked for RSA private key). This ensures that even if the database is stolen, private keys remain ciphertext without the admin private key (stored in `.env`).
- **Server‑only data** encrypted with **global admin RSA key**.
- **No symmetric encryption** – exclusively RSA + ECC.
- **Integrity** via ECDSA signatures using same key type as encryption (user ECC for user data, admin ECC for admin data).