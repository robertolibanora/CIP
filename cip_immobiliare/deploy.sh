#!/bin/bash

echo "🚀 Deployment CIP Immobiliare - Produzione"

# Verifica variabili ambiente
if [ -z "$CIP_ENV" ]; then
    echo "❌ CIP_ENV non impostata. Usa: export CIP_ENV=production"
    exit 1
fi

if [ "$CIP_ENV" != "production" ]; then
    echo "❌ CIP_ENV deve essere 'production' per il deployment"
    exit 1
fi

echo "✅ Ambiente: $CIP_ENV"

# Backup database
echo "💾 Backup database..."
pg_dump $DATABASE_URL > "backup_$(date +%Y%m%d_%H%M%S).sql"

# Pull ultime modifiche
echo "📥 Pull ultime modifiche..."
git pull origin main

# Attiva ambiente virtuale
echo "🔧 Attivazione ambiente virtuale..."
source .venv/bin/activate

# Aggiorna dipendenze
echo "📚 Aggiornamento dipendenze..."
pip install -r requirements.txt

# Migrazioni database (se necessario)
echo "🗄️  Verifica database..."
python database.py

# Riavvia servizi
echo "🔄 Riavvio servizi..."
if command -v systemctl &> /dev/null; then
    sudo systemctl restart cip_app
    sudo systemctl restart nginx
else
    echo "⚠️  systemctl non disponibile, riavvia manualmente i servizi"
fi

# Health check
echo "🏥 Health check..."
sleep 5
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Applicazione funzionante"
else
    echo "❌ Problemi con l'applicazione"
    exit 1
fi

echo "🎉 Deployment completato!"
echo "🌐 Applicazione disponibile su: http://localhost"
