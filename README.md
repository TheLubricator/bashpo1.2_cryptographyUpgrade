# BashPO v1.1 - Secure Game Distribution Platform

## Overview

BashPO is a secure game distribution and marketplace platform built with Flask. It implements enterprise-grade cryptography and key management to protect user data, sensitive information, and secure transactions. This project demonstrates a complete end-to-end encrypted system with asymmetric cryptography, digital signatures, and role-based access control.

## Project Structure

### Core Components

1. **`crypto_overview.md`** – Cryptographic Architecture & Implementation
   - RSA-2048 encryption from scratch with PKCS#1 v1.5 padding
   - ECC (secp256k1) implementation with ECDSA digital signatures
   - Cryptographic API for user data and session management
   - Key generation, storage, and rotation mechanisms
   - Session management with server-side token validation

2. **`database_encryption_map.md`** – Database Schema & Encryption Mapping
   - Complete table structure and sensitive column identification
   - Encryption key assignments for different data types
   - User-specific vs. admin-managed encryption strategies
   - ECDSA signature verification for data integrity
   - 9+ database tables with strategic encryption placement

3. **`requirements_checklist.md`** – CSE447 Lab Requirements Completion
   - All 9 explicit requirements fully implemented
   - Login/registration with password hashing and salting
   - Two-factor authentication (OTP via email)
   - End-to-end encryption for critical data
   - Role-based access control (RBAC)
   - MAC/ECDSA integrity verification
   - Compliance notes and implementation details

## Key Features

### Security
- ✅ **Asymmetric Encryption Only**: RSA-2048 for user data, ElGamal for game descriptions, ECC for signatures
- ✅ **ElGamal over ECC**: Point-based encryption on elliptic curves for game publishing descriptions
- ✅ **Chunked Encryption**: RSA private keys split into chunks and encrypted with admin key
- ✅ **Zero-Knowledge Architecture**: Sensitive data encrypted before database storage
- ✅ **Digital Signatures**: ECDSA signatures on all encrypted data for integrity verification
- ✅ **Session Security**: Server-side token validation in separate session database
- ✅ **Password Hashing**: SHA-256 with 16-byte random salt and constant-time comparison

### Functionality
- ✅ **Multi-role System**: Buyers, Developers, and Admins with role-based dashboards
- ✅ **Key Management**: Generation, storage, rotation, and user-specific encryption
- ✅ **Game Distribution**: Publishing, searching, purchasing, and reviewing games
- ✅ **Wallet System**: Encrypted balance tracking and wallet code management
- ✅ **User Profiles**: Encrypted email, address, and personal information
- ✅ **Two-Factor Authentication**: OTP verification via email (Resend integration)

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Set up environment variables in `.env`:
```
ADMIN_RSA_PUBLIC_KEY=...
ADMIN_RSA_PRIVATE_KEY=...
ADMIN_ECC_PUBLIC_KEY=...
ADMIN_ECC_PRIVATE_KEY=...
```

Generate admin keys using:
```bash
python generate_admin_key.py
```

### Running the Application

```bash
python app.py
```

The application will start on `http://localhost:5000`

## Documentation Guide

**Start here for understanding the system:**

1. Read [`crypto_overview.md`](./crypto_overview.md) first
   - Understand RSA and ECC implementations
   - Learn how keys are generated and stored
   - Review the cryptographic API design

2. Then read [`database_encryption_map.md`](./database_encryption_map.md)
   - See how encryption is applied to specific data
   - Understand which keys encrypt what
   - Review the database schema

3. Finally, check [`requirements_checklist.md`](./requirements_checklist.md)
   - Verify all requirements are met
   - Review implementation notes
   - Check for workarounds and exceptions

## Database Files

- **`bashpo_secured_session.db`** – Server-side session tokens with encryption
- **`bashpos_--definitely--_secured_database.db`** – Main application database with encrypted user data

## Project Files

### Root Level
- `app.py` – Main Flask application and routes
- `generate_admin_key.py` – Admin key generation utility
- `tree_maker.py` – Directory structure generator

### Crypto Module (`crypto/`)
- `rsa.py` – RSA-2048 implementation from scratch
- `ecc.py` – ECC (secp256k1) implementation with ECDSA
- Helper functions for encryption/decryption operations

### Models Module (`model/`)
- `session_manager.py` – Server-side session management
- `req_auth.py` – Authentication and authorization
- `route_help.py` – Route helper functions

### Templates (`templates/`)
- Admin dashboard, buyer/developer dashboards
- Game pages, cart, profiles, authentication forms
- Two-factor authentication interface

### Static Assets (`static/`)
- Game images, logos, carousel images
- Uploaded game files and metadata

## Security Considerations

### Threat Model

This system protects against:
- **Database breach**: Encrypted data remains secure without admin key
- **Man-in-the-middle attacks**: ECDSA signatures prevent tampering
- **Session hijacking**: Server-side token validation
- **Weak passwords**: SHA-256 hashing with salting
- **Unauthorized access**: Role-based access control

### Limitations

- Admin key must be protected in `.env` file (not version controlled)
- Chunked RSA encryption is needed due to plaintext size limitations
- Session tokens require server-side database (not stateless)

## Contributing

This is a CSE447 lab project demonstrating cryptographic principles and secure development practices.

## License

Academic project – CSE447 Lab

---

**For detailed technical information, see the linked documentation files above.**
