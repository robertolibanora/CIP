#!/bin/bash

# Script di configurazione SSL per CIP Immobiliare
# Esegui come root: bash setup_ssl.sh

set -e

echo "🔒 Configurazione SSL per CIP Immobiliare..."

# Verifica che il dominio punti al server
echo "🌐 Verifica configurazione DNS..."
echo "Assicurati che il dominio cipimmobiliare.it punti all'IP di questo server:"
curl -s ifconfig.me
echo ""

read -p "Il dominio è configurato correttamente? (y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Configura prima il DNS e riprova"
    exit 1
fi

# Installa certificato SSL con Let's Encrypt
echo "📜 Richiesta certificato SSL..."
certbot --nginx -d cipimmobiliare.it -d www.cipimmobiliare.it --non-interactive --agree-tos --email admin@cipimmobiliare.it

# Configura rinnovo automatico
echo "🔄 Configurazione rinnovo automatico..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

# Test configurazione SSL
echo "🧪 Test configurazione SSL..."
nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configurazione SSL completata!"
    echo "🔗 Il sito è disponibile su: https://cipimmobiliare.it"
else
    echo "❌ Errore nella configurazione SSL"
    exit 1
fi

# Mostra informazioni certificato
echo "📋 Informazioni certificato:"
certbot certificates
