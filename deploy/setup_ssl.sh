#!/bin/bash

# Script per configurazione SSL con Let's Encrypt
# File: deploy/setup_ssl.sh

set -e

echo "🔐 Configurazione SSL per CIP Immobiliare..."

# Verifica che il dominio punti al server
echo "📋 Verifica configurazione DNS..."
DOMAIN_IP=$(dig +short ciprealestate.eu | head -1)
SERVER_IP=$(curl -s ifconfig.me)

echo "IP del dominio: $DOMAIN_IP"
echo "IP del server: $SERVER_IP"

if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    echo "⚠️  ATTENZIONE: Il dominio non punta al server corrente"
    echo "   Devi configurare il DNS per puntare a $SERVER_IP"
    echo "   Oppure disabilitare il proxy nel pannello di controllo"
    exit 1
fi

# Crea directory per challenge
mkdir -p /var/www/html/.well-known/acme-challenge

# Configura Nginx temporaneamente per la verifica
cat > /etc/nginx/sites-available/CIP-temp << 'EOF'
server {
    listen 80;
    server_name ciprealestate.eu www.ciprealestate.eu;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}
EOF

ln -sf /etc/nginx/sites-available/CIP-temp /etc/nginx/sites-enabled/CIP-temp
systemctl reload nginx

# Ottieni certificato Let's Encrypt
echo "📋 Richiesta certificato Let's Encrypt..."
certbot certonly \
    --webroot \
    -w /var/www/html \
    -d ciprealestate.eu \
    -d www.ciprealestate.eu \
    --non-interactive \
    --agree-tos \
    --email cipnetworksrl@gmail.com \
    --expand

# Rimuovi configurazione temporanea
rm -f /etc/nginx/sites-enabled/CIP-temp
rm -f /etc/nginx/sites-available/CIP-temp

# Aggiorna configurazione Nginx con certificato Let's Encrypt
echo "📋 Aggiornamento configurazione Nginx..."
sed -i 's|ssl_certificate /etc/ssl/cip_immobiliare/certificate.crt;|ssl_certificate /etc/letsencrypt/live/ciprealestate.eu/fullchain.pem;|' /etc/nginx/sites-available/CIP
sed -i 's|ssl_certificate_key /etc/ssl/cip_immobiliare/private.key;|ssl_certificate_key /etc/letsencrypt/live/ciprealestate.eu/privkey.pem;|' /etc/nginx/sites-available/CIP

# Riavvia Nginx
systemctl reload nginx

echo "✅ SSL configurato con successo!"
echo "🌐 Il sito è ora disponibile su https://ciprealestate.eu"

# Configura rinnovo automatico
echo "📋 Configurazione rinnovo automatico..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -

echo "✅ Configurazione SSL completata!"