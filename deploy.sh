#!/bin/bash

# Script di Deploy per CIP Immobiliare - Produzione
echo "🚀 Avvio deploy CIP Immobiliare..."

# Verifica ambiente
if [ "$FLASK_ENV" != "production" ]; then
    echo "❌ Errore: FLASK_ENV deve essere 'production'"
    exit 1
fi

# Verifica dipendenze
echo "📦 Verifica dipendenze..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 non trovato"
    exit 1
fi

# Attiva ambiente virtuale
echo "🔧 Attivazione ambiente virtuale..."
source .venv/bin/activate

# Installa/aggiorna dipendenze
echo "📥 Installazione dipendenze..."
pip install -r requirements.txt

# Verifica struttura file
echo "📁 Verifica struttura file..."
if [ ! -f "main.py" ]; then
    echo "❌ main.py non trovato"
    exit 1
fi

if [ ! -d "frontend/assets/css" ]; then
    echo "❌ CSS non trovati"
    exit 1
fi

if [ ! -d "frontend/templates" ]; then
    echo "❌ Template non trovati"
    exit 1
fi

# Verifica database
echo "🗄️ Verifica connessione database..."
python -c "
from config.database.database import get_connection
try:
    conn = get_connection()
    print('✅ Database connesso')
    conn.close()
except Exception as e:
    print(f'❌ Errore database: {e}')
    exit(1)
"

# Test applicazione
echo "🧪 Test applicazione..."
python -c "
from main import app
with app.test_client() as client:
    response = client.get('/')
    if response.status_code in [200, 302]:
        print('✅ Applicazione funzionante')
    else:
        print(f'❌ Errore applicazione: {response.status_code}')
        exit(1)
"

# Avvio produzione
echo "🚀 Avvio applicazione in produzione..."
echo "📍 URL: http://0.0.0.0:8090"
echo "🔒 Modalità: Produzione"
echo "📝 Log: /var/log/cip_immobiliare/app.log"

# Avvia con gunicorn per produzione
gunicorn --bind 0.0.0.0:8090 --workers 4 --timeout 120 --access-logfile /var/log/cip_immobiliare/access.log --error-logfile /var/log/cip_immobiliare/error.log main:app
