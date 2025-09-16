#!/usr/bin/env python3
"""
Script per correggere auto-referral nel database
Rimuove i riferimenti where referred_by = id (auto-referral)
"""

import sqlite3
import sys
import os

# Aggiungi il path del progetto
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_self_referrals():
    """Corregge gli auto-referral nel database"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cip_immobiliare.db')
    
    if not os.path.exists(db_path):
        print(f"Database non trovato: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Trova utenti con auto-referral
        cur.execute("SELECT id, full_name, email FROM users WHERE id = referred_by")
        self_referrals = cur.fetchall()
        
        if not self_referrals:
            print("Nessun auto-referral trovato nel database.")
            return True
        
        print(f"Trovati {len(self_referrals)} utenti con auto-referral:")
        for user_id, name, email in self_referrals:
            print(f"  - ID: {user_id}, Nome: {name}, Email: {email}")
        
        # Rimuovi gli auto-referral
        cur.execute("UPDATE users SET referred_by = NULL WHERE id = referred_by")
        affected_rows = cur.rowcount
        
        conn.commit()
        print(f"Corretti {affected_rows} auto-referral.")
        
        # Verifica che non ci siano più auto-referral
        cur.execute("SELECT COUNT(*) FROM users WHERE id = referred_by")
        remaining = cur.fetchone()[0]
        
        if remaining == 0:
            print("✅ Tutti gli auto-referral sono stati corretti.")
        else:
            print(f"⚠️  Rimangono {remaining} auto-referral.")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Errore durante la correzione: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Correzione auto-referral nel database...")
    success = fix_self_referrals()
    if success:
        print("✅ Correzione completata con successo!")
    else:
        print("❌ Errore durante la correzione.")
        sys.exit(1)
