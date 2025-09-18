#!/bin/bash

# Script di configurazione server Ubuntu 24.04 per CIP Immobiliare
# Esegui come root: bash setup_server.sh

set -e

echo "🚀 Configurazione server Ubuntu 24.04 per CIP Immobiliare..."

# Aggiorna sistema
echo "📦 Aggiornamento sistema..."
apt update && apt upgrade -y

# Installa dipendenze base
echo "🔧 Installazione dipendenze base..."
apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    postgresql \
    postgresql-contrib \
    nginx \
    git \
    curl \
    wget \
    unzip \
    htop \
    ufw \
    fail2ban \
    certbot \
    python3-certbot-nginx \
    supervisor \
    build-essential \
    libpq-dev

# Crea utente per l'applicazione
echo "👤 Creazione utente applicazione..."
useradd -m -s /bin/bash cipapp
usermod -aG sudo cipapp

# Crea directory per l'applicazione
echo "📁 Creazione directory..."
mkdir -p /var/www/cip_immobiliare
mkdir -p /var/log/cip_immobiliare
mkdir -p /var/www/cip_immobiliare/uploads
mkdir -p /var/www/cip_immobiliare/instance/uploads/kyc

# Imposta permessi
chown -R cipapp:cipapp /var/www/cip_immobiliare
chown -R cipapp:cipapp /var/log/cip_immobiliare

# Configura PostgreSQL
echo "🗄️ Configurazione PostgreSQL..."
sudo -u postgres psql -c "CREATE DATABASE cip_immobiliare_prod;"
sudo -u postgres psql -c "CREATE USER cipuser WITH PASSWORD 'cip_secure_password_2024';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE cip_immobiliare_prod TO cipuser;"
sudo -u postgres psql -c "ALTER USER cipuser CREATEDB;"

# Configura firewall
echo "🔥 Configurazione firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Configura fail2ban
echo "🛡️ Configurazione fail2ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
EOF

systemctl enable fail2ban
systemctl start fail2ban

# Configura timezone
echo "🕐 Configurazione timezone..."
timedatectl set-timezone Europe/Rome

# Ottimizzazioni sistema
echo "⚡ Ottimizzazioni sistema..."
cat >> /etc/sysctl.conf << EOF
# Ottimizzazioni per applicazione web
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 10
EOF

sysctl -p

echo "✅ Configurazione server completata!"
echo "📋 Prossimi passi:"
echo "1. Clona il repository: git clone <repo-url> /var/www/cip_immobiliare"
echo "2. Configura le variabili ambiente"
echo "3. Installa dipendenze Python"
echo "4. Configura Nginx"
echo "5. Avvia l'applicazione"
