#!/bin/bash

# Script di aggiornamento per CIP Immobiliare su Hostinger
# Esegui questo script per aggiornare l'applicazione con le ultime modifiche

set -e

echo "🔄 Aggiornamento CIP Immobiliare"
echo "==============================="

# Verifica che sia eseguito come root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Questo script deve essere eseguito come root"
    echo "Usa: sudo bash update.sh"
    exit 1
fi

# Vai alla directory dell'applicazione
cd /var/www/CIP

echo "📥 Aggiornamento codice dal repository..."
sudo -u cipapp git pull origin main

echo "📦 Aggiornamento dipendenze Python..."
sudo -u cipapp .venv/bin/pip install -r requirements.txt

echo "🔄 Riavvio servizio applicazione..."
systemctl restart cip-immobiliare

echo "🔍 Verifica stato servizio..."
sleep 3
systemctl status cip-immobiliare --no-pager

echo "🧪 Test applicazione..."
sleep 5
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Aggiornamento completato con successo!"
    echo "🌐 Applicazione disponibile su: https://ciprealestate.eu"
else
    echo "❌ Errore nel test applicazione"
    echo "Controlla i log: journalctl -u cip-immobiliare -f"
    exit 1
fi

echo ""
echo "🎉 AGGIORNAMENTO COMPLETATO!"
echo "============================"
echo "📋 Comandi utili:"
echo "   - Stato app: systemctl status cip-immobiliare"
echo "   - Log app: journalctl -u cip-immobiliare -f"
echo "   - Riavvia app: systemctl restart cip-immobiliare"
