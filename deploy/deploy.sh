#!/bin/bash

# Script principale di deploy per CIP Immobiliare su DigitalOcean
# Esegui questo script sul server dopo aver clonato il repository

set -e

echo "🚀 Deploy CIP Immobiliare su DigitalOcean"
echo "=========================================="

# Verifica che sia eseguito come root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Questo script deve essere eseguito come root"
    echo "Usa: sudo bash deploy.sh"
    exit 1
fi

# Verifica che il repository sia clonato
if [ ! -f "/var/www/cip_immobiliare/main.py" ]; then
    echo "❌ Repository non trovato in /var/www/cip_immobiliare"
    echo "Clona prima il repository:"
    echo "git clone <your-repo-url> /var/www/cip_immobiliare"
    exit 1
fi

# 1. Configurazione server base
echo "📋 FASE 1: Configurazione server base..."
bash /var/www/cip_immobiliare/deploy/setup_server.sh

# 2. Clona e configura applicazione
echo "📋 FASE 2: Configurazione applicazione..."
cd /var/www/cip_immobiliare

# Crea ambiente virtuale
echo "🐍 Creazione ambiente virtuale Python..."
sudo -u cipapp python3 -m venv .venv
sudo -u cipapp .venv/bin/pip install --upgrade pip

# Installa dipendenze
echo "📦 Installazione dipendenze Python..."
sudo -u cipapp .venv/bin/pip install -r requirements.txt

# 3. Configurazione database
echo "📋 FASE 3: Configurazione database..."
bash /var/www/cip_immobiliare/deploy/setup_database.sh

# 4. Configurazione Nginx
echo "📋 FASE 4: Configurazione Nginx..."
cp /var/www/cip_immobiliare/deploy/nginx_cip_immobiliare.conf /etc/nginx/sites-available/cip_immobiliare
ln -sf /etc/nginx/sites-available/cip_immobiliare /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test configurazione Nginx
nginx -t
if [ $? -ne 0 ]; then
    echo "❌ Errore nella configurazione Nginx"
    exit 1
fi

# 5. Configurazione servizio systemd
echo "📋 FASE 5: Configurazione servizio systemd..."
cp /var/www/cip_immobiliare/deploy/cip-immobiliare.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable cip-immobiliare

# 6. Configurazione SSL (opzionale)
echo "📋 FASE 6: Configurazione SSL..."
echo "Vuoi configurare SSL con Let's Encrypt? (y/n)"
read -p "Risposta: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    bash /var/www/cip_immobiliare/deploy/setup_ssl.sh
else
    echo "⚠️ SSL non configurato. Configura manualmente quando necessario."
fi

# 7. Hardening sicurezza
echo "📋 FASE 7: Hardening sicurezza..."
bash /var/www/cip_immobiliare/deploy/security_hardening.sh

# 8. Avvio servizi
echo "📋 FASE 8: Avvio servizi..."
systemctl restart nginx
systemctl start cip-immobiliare

# Verifica stato servizi
echo "🔍 Verifica stato servizi..."
systemctl status cip-immobiliare --no-pager
systemctl status nginx --no-pager

# Test applicazione
echo "🧪 Test applicazione..."
sleep 5
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo "✅ Applicazione funzionante"
else
    echo "❌ Errore nel test applicazione"
    echo "Controlla i log: journalctl -u cip-immobiliare -f"
fi

# 9. Informazioni finali
echo ""
echo "🎉 DEPLOY COMPLETATO!"
echo "===================="
echo "🌐 URL applicazione: http://$(curl -s ifconfig.me)"
echo "🔧 Configurazione:"
echo "   - Database: PostgreSQL su localhost:5432"
echo "   - Applicazione: Gunicorn su 127.0.0.1:8090"
echo "   - Web server: Nginx su porta 80/443"
echo "   - Log: /var/log/cip_immobiliare/"
echo ""
echo "📋 Comandi utili:"
echo "   - Stato app: systemctl status cip-immobiliare"
echo "   - Log app: journalctl -u cip-immobiliare -f"
echo "   - Riavvia app: systemctl restart cip-immobiliare"
echo "   - Log Nginx: tail -f /var/log/nginx/cip_immobiliare_error.log"
echo ""
echo "🔐 Credenziali admin:"
echo "   - Email: admin@cipimmobiliare.it"
echo "   - Password: your-secure-admin-password"
echo "   ⚠️ CAMBIA LA PASSWORD ADMIN PRIMA DI ANDARE IN PRODUZIONE!"
echo ""
echo "📚 Prossimi passi:"
echo "1. Configura il dominio DNS per puntare a questo server"
echo "2. Cambia la password admin"
echo "3. Configura backup automatici"
echo "4. Monitora i log per errori"
echo "5. Testa tutte le funzionalità dell'applicazione"
