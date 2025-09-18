#!/bin/bash

# Script di configurazione database per CIP Immobiliare
# Esegui come utente cipapp: bash setup_database.sh

set -e

echo "🗄️ Configurazione database CIP Immobiliare..."

# Attiva ambiente virtuale
source /var/www/cip_immobiliare/.venv/bin/activate

# Vai nella directory dell'applicazione
cd /var/www/cip_immobiliare

# Crea le tabelle del database
echo "📋 Creazione tabelle database..."
python -c "
import os
import sys
sys.path.append('/var/www/cip_immobiliare')

# Imposta variabili ambiente
os.environ['FLASK_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://cipuser:cip_secure_password_2024@localhost:5432/cip_immobiliare_prod'

from backend.shared.database import get_connection
from config.database import create_tables

try:
    # Crea connessione
    conn = get_connection()
    cursor = conn.cursor()
    
    # Esegui script di creazione tabelle
    with open('config/database/schema_complete.sql', 'r') as f:
        schema_sql = f.read()
    
    cursor.execute(schema_sql)
    conn.commit()
    
    print('✅ Tabelle create con successo')
    
    # Inserisci dati iniziali
    print('📊 Inserimento dati iniziali...')
    
    # Inserisci categorie KYC
    with open('config/database/insert_kyc_categories.sql', 'r') as f:
        kyc_categories = f.read()
    
    cursor.execute(kyc_categories)
    conn.commit()
    
    print('✅ Categorie KYC inserite')
    
    # Crea utente admin
    print('👤 Creazione utente admin...')
    from backend.shared.models import User
    from werkzeug.security import generate_password_hash
    
    admin_password = os.environ.get('ADMIN_PASSWORD', 'your-secure-admin-password')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@cipimmobiliare.it')
    
    # Verifica se admin esiste già
    cursor.execute('SELECT id FROM users WHERE email = %s', (admin_email,))
    if cursor.fetchone():
        print('⚠️ Utente admin già esistente')
    else:
        # Crea admin
        cursor.execute('''
            INSERT INTO users (email, password_hash, nome, cognome, telefono, telegram, 
                             ruolo, is_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ''', (
            admin_email,
            generate_password_hash(admin_password),
            os.environ.get('ADMIN_NOME', 'Admin'),
            os.environ.get('ADMIN_COGNOME', 'CIP'),
            os.environ.get('ADMIN_TELEFONO', '+39000000000'),
            os.environ.get('ADMIN_TELEGRAM', 'admin_cip'),
            'admin',
            True
        ))
        conn.commit()
        print('✅ Utente admin creato')
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f'❌ Errore durante la configurazione database: {e}')
    sys.exit(1)
"

# Verifica connessione database
echo "🔍 Verifica connessione database..."
python -c "
import os
import sys
sys.path.append('/var/www/cip_immobiliare')
os.environ['FLASK_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://cipuser:cip_secure_password_2024@localhost:5432/cip_immobiliare_prod'

from backend.shared.database import get_connection

try:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    print(f'✅ Database connesso - {user_count} utenti trovati')
    cursor.close()
    conn.close()
except Exception as e:
    print(f'❌ Errore connessione database: {e}')
    sys.exit(1)
"

echo "✅ Configurazione database completata!"
