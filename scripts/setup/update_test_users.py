#!/usr/bin/env python3
"""
Aggiorna le password hash degli utenti di test nel database
Esegui con: python update_test_users.py
"""

import psycopg
from psycopg.rows import dict_row
from werkzeug.security import generate_password_hash
import os

def get_database_url():
    """Ottiene l'URL del database dalle variabili d'ambiente"""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL non impostata nelle variabili d'ambiente")
    return dsn

def update_test_users():
    """Aggiorna le password hash degli utenti di test"""
    
    # Password per utenti di test
    test_password = "test123"
    admin_password = "admin123"
    
    # Genera hash
    test_hash = generate_password_hash(test_password)
    admin_hash = generate_password_hash(admin_password)
    
    try:
        # Connessione al database con dict_row
        conn = psycopg.connect(get_database_url(), row_factory=dict_row)
        cur = conn.cursor()
        
        # Aggiorna utenti di test (investor)
        cur.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE email LIKE 'test.%%@example.com' AND role = 'investor'
        """, (test_hash,))
        
        # Aggiorna admin
        cur.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE email LIKE 'test.%%@example.com' AND role = 'admin'
        """, (admin_hash,))
        
        # Commit delle modifiche
        conn.commit()
        
        # Verifica aggiornamenti
        cur.execute("SELECT email, role, password_hash FROM users WHERE email LIKE 'test.%%@example.com'")
        users = cur.fetchall()
        
        print("✅ Password hash aggiornate con successo!")
        print("=" * 50)
        print("Utenti di test:")
        for user in users:
            if user['role'] == 'admin':
                print(f"  {user['email']} (admin) - Password: {admin_password}")
            else:
                print(f"  {user['email']} (investor) - Password: {test_password}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    update_test_users()
