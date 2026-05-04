import secrets
import hashlib

# Parameters for secp256k1 (mod p)
p = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
a = 0
b = 7
G = (0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798,
     0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8)
n = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # order


# ---------- Modular Inverse (same as in RSA) ----------
def modinv(k, p):
    return pow(k, -1, p)  # Python 3.8+


# ---------- Point Addition / Doubling ----------
def point_add(P, Q):
    """Return P+Q on secp256k1; P or Q can be None (point at infinity)."""
    if P is None:
        return Q
    if Q is None:
        return P
    x1, y1 = P
    x2, y2 = Q

    if P == Q:
        # doubling
        if y1 == 0:
            return None
        m = (3 * x1 * x1 + a) * modinv(2 * y1, p) % p
    else:
        if x1 == x2:
            return None
        m = (y2 - y1) * modinv(x2 - x1, p) % p

    x3 = (m * m - x1 - x2) % p
    y3 = (m * (x1 - x3) - y1) % p
    return (x3, y3)


# ---------- Scalar Multiplication (Double-and-Add) ----------
def scalar_mult(k, P):
    """Return k*P using double-and-add."""
    result = None
    addend = P
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result


# ---------- ECC Key Generation ----------
def generate_ecc_keypair():
    """Return (private_key, public_key) where private is int < n, public is (x,y)."""
    priv = secrets.randbelow(n - 1) + 1
    pub = scalar_mult(priv, G)
    return priv, pub


# ---------- ECDH Shared Secret ----------
def ecdh_shared_secret(private_key, other_public):
    """Compute shared secret (x-coordinate of private * other_public)."""
    point = scalar_mult(private_key, other_public)
    if point is None:
        return None
    # return x-coordinate as integer
    return point[0]


# ---------- ECDSA Sign & Verify (simplified) ----------
def ecdsa_sign(message_bytes, private_key):
    """Return signature (r, s) as tuple of ints."""
    # hash message
    h = int.from_bytes(hashlib.sha256(message_bytes).digest(), 'big')
    # use deterministic k? For demo, random k
    while True:
        k = secrets.randbelow(n - 1) + 1
        R = scalar_mult(k, G)
        if R is None:
            continue
        r = R[0] % n
        if r == 0:
            continue
        s = (modinv(k, n) * (h + r * private_key)) % n
        if s != 0:
            return (r, s)


def ecdsa_verify(message_bytes, signature, public_key):
    """Return True if signature valid."""
    r, s = signature
    if not (1 <= r < n and 1 <= s < n):
        return False
    h = int.from_bytes(hashlib.sha256(message_bytes).digest(), 'big')
    w = modinv(s, n)
    u1 = (h * w) % n
    u2 = (r * w) % n
    P = point_add(scalar_mult(u1, G), scalar_mult(u2, public_key))
    if P is None:
        return False
    return (P[0] % n) == r