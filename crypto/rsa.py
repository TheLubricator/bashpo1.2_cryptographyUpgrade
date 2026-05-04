import random
import secrets

# ---------- Miller-Rabin Primality Test ----------
def is_prime(n, k=40):
    if n <= 3:
        return n == 2 or n == 3
    if n % 2 == 0:
        return False
    r = 0
    d = n - 1
    while d % 2 == 0:
        d //= 2
        r += 1
    def check(a):
        x = pow(a, d, n)
        if x == 1 or x == n-1:
            return False
        for _ in range(r-1):
            x = pow(x, 2, n)
            if x == n-1:
                return False
        return True
    for _ in range(k):
        a = random.randrange(2, n-1)
        if check(a):
            return False
    return True

def generate_prime(bits):
    while True:
        p = random.getrandbits(bits)
        p |= (1 << bits-1) | 1
        if is_prime(p):
            return p

# ---------- Extended Euclidean Algorithm ----------
def egcd(a, b):
    if a == 0:
        return b, 0, 1
    g, y, x = egcd(b % a, a)
    return g, x - (b//a)*y, y

def modinv(a, m):
    g, x, _ = egcd(a, m)
    if g != 1:
        raise ValueError("Modular inverse does not exist")
    return x % m

# ---------- RSA Key Generation ----------
def generate_rsa_keys(bits=2048):
    p = generate_prime(bits//2)
    q = generate_prime(bits//2)
    n = p * q
    phi = (p-1)*(q-1)
    e = 65537
    if phi % e == 0:   # very rare, but regenerate
        return generate_rsa_keys(bits)
    d = modinv(e, phi)
    return (n, e), (n, d)

# ---------- PKCS#1 v1.5 Padding (fixed non-zero PS) ----------
def pkcs1_pad(data, key_len):
    """Pad data for RSA encryption (PKCS#1 v1.5)."""
    max_data = key_len - 11
    if len(data) > max_data:
        raise ValueError(f"Data too long (max {max_data} bytes)")
    ps_len = key_len - 3 - len(data)
    # Generate random non-zero bytes
    ps = bytearray()
    for _ in range(ps_len):
        b = 0
        while b == 0:
            b = secrets.randbelow(256)
        ps.append(b)
    return b'\x00\x02' + bytes(ps) + b'\x00' + data

def pkcs1_unpad(padded):
    """Remove PKCS#1 v1.5 padding."""
    if len(padded) < 11:
        raise ValueError("Padded block too short")
    if padded[0] != 0 or padded[1] != 2:
        raise ValueError("Invalid padding header")
    # Find the first zero byte after index 1
    sep = 2
    while sep < len(padded) and padded[sep] != 0:
        sep += 1
    if sep == len(padded):
        raise ValueError("Separator not found")
    if sep - 2 < 8:
        raise ValueError("Padding string too short")
    return padded[sep+1:]

# ---------- Encryption / Decryption ----------
def encrypt_string(plaintext, public_key):
    n, e = public_key
    key_len = (n.bit_length() + 7) // 8
    data = plaintext.encode('utf-8')
    padded = pkcs1_pad(data, key_len)
    m = int.from_bytes(padded, 'big')
    return pow(m, e, n)

def decrypt_string(cipher_int, private_key):
    n, d = private_key
    key_len = (n.bit_length() + 7) // 8
    m = pow(cipher_int, d, n)
    # Force to exact key length (restore leading zeros)
    block = m.to_bytes(key_len, 'big')
    print("Decrypted hex:", block.hex())
    unpadded = pkcs1_unpad(block)
    return unpadded.decode('utf-8')