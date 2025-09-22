#!/bin/bash

# Script di configurazione database per CIP Immobiliare
# Esegui come root: bash setup_database.sh

set -e

echo "🗄️ Configurazione database CIP Immobiliare..."

# Configura i permessi del database per l'utente cipapp
echo "🔐 Configurazione permessi database..."
sudo -u postgres psql -c "GRANT ALL ON SCHEMA public TO cipapp;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO cipapp;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cipapp;"
sudo -u postgres psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO cipapp;"
sudo -u postgres psql -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO cipapp;"

# Riavvia PostgreSQL per applicare i permessi
systemctl restart postgresql
sleep 2

# Attiva ambiente virtuale
source /var/www/CIP/.venv/bin/activate

# Vai nella directory dell'applicazione
cd /var/www/CIP

# Crea le tabelle del database
echo "📋 Creazione tabelle database..."
sudo -u cipapp python -c "
import os
import sys
sys.path.append('/var/www/CIP')

# Imposta variabili ambiente
os.environ['FLASK_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://cipapp:cipapp_password@localhost:5432/cip_immobiliare_prod'

try:
    import psycopg
    
    # Connessione al database
    conn = psycopg.connect(os.environ['DATABASE_URL'])
    cursor = conn.cursor()
    
    # Crea tabelle base se non esistono
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            nome VARCHAR(100),
            cognome VARCHAR(100),
            telefono VARCHAR(20),
            telegram VARCHAR(50),
            role VARCHAR(50) DEFAULT 'user',
            is_verified BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            price DECIMAL(10,2),
            status VARCHAR(50) DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kyc_requests (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            category VARCHAR(100) NOT NULL,
            status VARCHAR(50) DEFAULT 'pending',
            document_path VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    conn.commit()
    print('✅ Tabelle create con successo')
    
    # Crea utente admin se non esiste
    print('👤 Creazione utente admin...')
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
                             role, is_verified, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ''', (
            admin_email,
            generate_password_hash(admin_password),
            'Admin',
            'CIP',
            '+39000000000',
            'admin_cip',
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
sudo -u cipapp python -c "
import os
import sys
sys.path.append('/var/www/CIP')
os.environ['FLASK_ENV'] = 'production'
os.environ['DATABASE_URL'] = 'postgresql://cipapp:cipapp_password@localhost:5432/cip_immobiliare_prod'

try:
    import psycopg
    conn = psycopg.connect(os.environ['DATABASE_URL'])
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
