# run this once to generate admin keys and save to .env
from crypto import rsa, ecc

# RSA admin key pair
admin_rsa_pub, admin_rsa_priv = rsa.generate_rsa_keys(2048)
# ECC admin key pair
admin_ecc_priv, admin_ecc_pub = ecc.generate_ecc_keypair()

# Save to .env file (or a secure file)
with open('.env', 'a') as f:
    f.write(f"\nADMIN_RSA_PUB={admin_rsa_pub[0]}:{admin_rsa_pub[1]}\n")
    f.write(f"ADMIN_RSA_PRIV={admin_rsa_priv[0]}:{admin_rsa_priv[1]}\n")
    f.write(f"ADMIN_ECC_PUB={admin_ecc_pub[0]}:{admin_ecc_pub[1]}\n")
    f.write(f"ADMIN_ECC_PRIV={admin_ecc_priv}\n")
print("Admin keys saved to .env")