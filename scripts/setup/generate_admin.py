#!/usr/bin/env python3
"""
Genera hash password per utente admin
Esegui con: python generate_admin.py
"""

from werkzeug.security import generate_password_hash

def main():
    password = "admin123"
    hashed = generate_password_hash(password)
    
    print("🔐 Generazione hash password admin")
    print("=" * 40)
    print(f"Password: {password}")
    print(f"Hash: {hashed}")
    print()
    print("📝 Copia questo hash nel file create_admin.sql")
    print("   Sostituisci la riga:")
    print("   'pbkdf2:sha256:600000$YOUR_SALT_HERE$YOUR_HASH_HERE'")
    print("   con:")
    print(f"   '{hashed}'")
    print()
    print("💡 Poi esegui: psql -d cip -f create_admin.sql")

if __name__ == "__main__":
    main()
