#!/usr/bin/env python3
"""
Script per aggiornare/creare utenti di test CIP Immobiliare
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from werkzeug.security import generate_password_hash
from backend.shared.database import get_connection

def update_test_users():
    """Aggiorna o crea gli utenti di test"""
    
    print("🔐 Aggiornamento utenti di test CIP Immobiliare")
    print("=" * 50)
    
    try:
        # Connessione al database
        conn = get_connection()
        cursor = conn.cursor()
        
        # Password per tutti gli utenti di test
        test_password = "test123"
        password_hash = generate_password_hash(test_password, method='scrypt')
        
        print(f"🔑 Password generata per tutti gli utenti: {test_password}")
        print(f"📝 Hash: {password_hash}")
        
        # Lista utenti da creare/aggiornare
        test_users = [
            {
                'email': 'admin@cipimmobiliare.it',
                'full_name': 'Admin CIP',
                'role': 'admin'
            },
            {
                'email': 'test@cipimmobiliare.it',
                'full_name': 'Test User',
                'role': 'investor'
            },
            {
                'email': 'demo@cipimmobiliare.it',
                'full_name': 'Demo User',
                'role': 'investor'
            }
        ]
        
        # Inserisci o aggiorna ogni utente
        for user in test_users:
            cursor.execute("""
                INSERT INTO users (email, password_hash, full_name, role, kyc_status, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (email) DO UPDATE SET
                    password_hash = EXCLUDED.password_hash,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    kyc_status = EXCLUDED.kyc_status
            """, (
                user['email'],
                password_hash,
                user['full_name'],
                user['role'],
                'verified'  # KYC verificato per utenti di test
            ))
            
            print(f"✅ Utente {user['email']} aggiornato/creato")
        
        # Commit delle modifiche
        conn.commit()
        
        # Verifica inserimento
        print("\n📊 Verifica utenti creati:")
        print("-" * 30)
        
        for user in test_users:
            cursor.execute("""
                SELECT email, full_name, role, kyc_status, created_at
                FROM users WHERE email = %s
            """, (user['email'],))
            
            result = cursor.fetchone()
            if result:
                print(f"✅ {result['email']} - {result['full_name']} ({result['role']}) - KYC: {result['kyc_status']}")
            else:
                print(f"❌ {user['email']} - NON TROVATO!")
        
        print(f"\n🎉 {len(test_users)} utenti di test aggiornati con successo!")
        print(f"🔑 Password per tutti: {test_password}")
        
        # Chiudi connessione
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Errore durante l'aggiornamento: {e}")
        sys.exit(1)

if __name__ == "__main__":
    update_test_users()
