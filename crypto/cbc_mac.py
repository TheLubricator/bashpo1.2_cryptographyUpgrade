from Crypto.Cipher import AES
import os

def generate_mac_key():
    """Generate a random 128-bit AES key for CBC-MAC."""
    return os.urandom(16)   # 128 bits

def cbc_mac(key, message):
    """
    Compute CBC-MAC of a message using AES-128.
    Message is a bytes-like object (UTF-8 encoded string).
    Returns the MAC as bytes (16 bytes).
    """
    cipher = AES.new(key, AES.MODE_ECB)   # ECB for block encryption
    block_size = 16
    # Pad message with zeros (PKCS#7 style but simple zero padding)
    padded = message
    if len(padded) % block_size != 0:
        padded += b'\x00' * (block_size - len(padded) % block_size)
    # CBC-MAC: encrypt the first block, then XOR with next block, etc.
    prev = b'\x00' * block_size
    for i in range(0, len(padded), block_size):
        block = padded[i:i+block_size]
        # XOR with previous ciphertext
        xored = bytes(a ^ b for a, b in zip(block, prev))
        prev = cipher.encrypt(xored)
    return prev   # final block is the MAC

def verify_cbc_mac(key, message, mac):
    """Check if the MAC matches the message."""
    computed = cbc_mac(key, message)
    return computed == mac