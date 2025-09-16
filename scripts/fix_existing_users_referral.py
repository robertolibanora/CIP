#!/usr/bin/env python3
"""
Script per assegnare gli utenti esistenti senza referral a Marco Trapella
"""

import sqlite3
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_existing_users_referral():
    """Assegna gli utenti esistenti senza referral a Marco Trapella"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cip_immobiliare.db')
    
    if not os.path.exists(db_path):
        print(f"Database non trovato: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Trova Marco Trapella
        cur.execute("SELECT id FROM users WHERE referral_code = 'MARCO001'")
        marco = cur.fetchone()
        
        if not marco:
            print("❌ Marco Trapella non trovato nel database!")
            return False
        
        marco_id = marco[0]
        print(f"✅ Marco Trapella trovato con ID: {marco_id}")
        
        # Trova utenti senza referral (escludendo Marco stesso)
        cur.execute("""
            SELECT id, nome, cognome, email 
            FROM users 
            WHERE referred_by IS NULL AND id != ? 
            ORDER BY created_at ASC
        """, (marco_id,))
        
        users_to_fix = cur.fetchall()
        
        if not users_to_fix:
            print("✅ Nessun utente da correggere.")
            return True
        
        print(f"🔧 Trovati {len(users_to_fix)} utenti da assegnare a Marco Trapella:")
        
        # Assegna ogni utente a Marco Trapella
        for user in users_to_fix:
            user_id, nome, cognome, email = user
            print(f"  - Assegnando {nome} {cognome} ({email}) a Marco Trapella...")
            
            cur.execute("UPDATE users SET referred_by = ? WHERE id = ?", (marco_id, user_id))
        
        # Commit delle modifiche
        conn.commit()
        
        # Verifica il risultato
        cur.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (marco_id,))
        final_count = cur.fetchone()[0]
        
        print(f"\n✅ Completato! {len(users_to_fix)} utenti assegnati a Marco Trapella.")
        print(f"📊 Totale utenti sotto Marco Trapella: {final_count}")
        
        # Mostra il risultato finale
        cur.execute("""
            SELECT id, nome, cognome, email, created_at 
            FROM users 
            WHERE referred_by = ? 
            ORDER BY created_at ASC
        """, (marco_id,))
        
        final_users = cur.fetchall()
        print("\n👥 Utenti ora sotto Marco Trapella:")
        for user in final_users:
            print(f"  - ID: {user[0]}, Nome: {user[1]} {user[2]}, Email: {user[3]}, Data: {user[4]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Errore durante la correzione: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Correzione utenti esistenti senza referral...")
    success = fix_existing_users_referral()
    if success:
        print("\n✅ Correzione completata con successo!")
    else:
        print("\n❌ Errore durante la correzione.")
        sys.exit(1)
