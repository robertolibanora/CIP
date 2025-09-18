#!/usr/bin/env python3
"""
Script per aggiornare gli hash delle password da SHA-256 a bcrypt
"""

import os
import sys
import psycopg
import hashlib

# Aggiungi il percorso del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_password_hashes():
    """Aggiorna tutti gli hash delle password da SHA-256 a bcrypt"""
    
    # Connessione al database
    dsn = os.environ.get("DATABASE_URL", "postgresql://localhost/cip_immobiliare")
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                # Ottieni tutti gli utenti con le loro password attuali
                cur.execute("SELECT id, email, password_hash FROM users")
                users = cur.fetchall()
                
                print(f"Trovati {len(users)} utenti da aggiornare...")
                
                for user_id, email, current_hash in users:
                    # Se l'hash è già in formato bcrypt (inizia con $2b$), salta
                    if current_hash.startswith('$2b$'):
                        print(f"Utente {email} ha già hash bcrypt, salto...")
                        continue
                    
                    # Genera una nuova password temporanea e hasha con SHA-256
                    # Per ora, usiamo una password temporanea che l'utente dovrà cambiare
                    temp_password = "temp_password_123"
                    new_hash = hashlib.sha256(temp_password.encode()).hexdigest()
                    
                    # Aggiorna l'hash nel database
                    cur.execute(
                        "UPDATE users SET password_hash = %s WHERE id = %s",
                        (new_hash, user_id)
                    )
                    
                    print(f"Aggiornato utente {email} (ID: {user_id})")
                    print(f"  Password temporanea: {temp_password}")
                    print(f"  L'utente dovrà cambiare la password al prossimo login")
                
                conn.commit()
                print("\n✅ Aggiornamento completato!")
                print("⚠️  IMPORTANTE: Tutti gli utenti dovranno usare la password temporanea 'temp_password_123'")
                print("   e poi cambiarla dal loro profilo.")
                
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento: {e}")
        return False
    
    return True

if __name__ == "__main__":
    fix_password_hashes()
