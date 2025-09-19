#!/bin/bash

# Script di hardening sicurezza per CIP Immobiliare
# Esegui come root: bash security_hardening.sh

set -e

echo "🛡️ Hardening sicurezza per CIP Immobiliare..."

# 1. Configurazione SSH
echo "🔐 Configurazione SSH..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

cat > /etc/ssh/sshd_config << EOF
# Configurazione SSH sicura
Port 22
Protocol 2
HostKey /etc/ssh/ssh_host_rsa_key
HostKey /etc/ssh/ssh_host_ecdsa_key
HostKey /etc/ssh/ssh_host_ed25519_key

# Autenticazione
LoginGraceTime 60
PermitRootLogin no
StrictModes yes
MaxAuthTries 3
MaxSessions 3

# Chiavi pubbliche
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys

# Password authentication (disabilita se usi solo chiavi SSH)
PasswordAuthentication no
PermitEmptyPasswords no
ChallengeResponseAuthentication no

# Configurazioni di sicurezza
X11Forwarding no
X11DisplayOffset 10
PrintMotd no
PrintLastLog yes
TCPKeepAlive yes
UsePrivilegeSeparation yes
Compression delayed
ClientAliveInterval 300
ClientAliveCountMax 2

# Logging
SyslogFacility AUTH
LogLevel INFO

# Banner
Banner /etc/ssh/banner

# Disabilita algoritmi deboli
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com,hmac-sha2-256,hmac-sha2-512
KexAlgorithms curve25519-sha256@libssh.org,ecdh-sha2-nistp256,ecdh-sha2-nistp384,ecdh-sha2-nistp521,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512
EOF

# Crea banner SSH
cat > /etc/ssh/banner << EOF
***************************************************************************
*                    CIP IMMOBILIARE SERVER                              *
*                                                                       *
*  Questo sistema è riservato ad uso autorizzato. Tutte le attività    *
*  sono monitorate e registrate. L'accesso non autorizzato è vietato.  *
*                                                                       *
***************************************************************************
EOF

# 2. Configurazione fail2ban avanzata
echo "🚫 Configurazione fail2ban avanzata..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log
maxretry = 3
bantime = 7200

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
EOF

# Crea filtro nginx per fail2ban
cat > /etc/fail2ban/filter.d/nginx-http-auth.conf << EOF
[Definition]
failregex = ^ \[error\] \d+#\d+: \*\d+ user "[^"]*":? (?:password mismatch|was not found in "[^"]*"), client: <HOST>, server: \S+, request: "\S+ \S+ HTTP/\d+\.\d+", host: "\S+"(?:, referrer: "\S+")?$
            ^ \[error\] \d+#\d+: \*\d+ no user/password was provided for basic authentication, client: <HOST>, server: \S+, request: "\S+ \S+ HTTP/\d+\.\d+", host: "\S+"(?:, referrer: "\S+")?$
ignoreregex =
EOF

cat > /etc/fail2ban/filter.d/nginx-limit-req.conf << EOF
[Definition]
failregex = limiting requests, excess: [\d.]+ by zone [\w]+, client: <HOST>
ignoreregex =
EOF

# 3. Configurazione kernel security
echo "🔧 Configurazione kernel security..."
cat >> /etc/sysctl.conf << EOF

# Security settings
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.secure_redirects = 0
net.ipv4.conf.default.secure_redirects = 0
net.ipv4.ip_forward = 0
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.tcp_timestamps = 0

# IPv6 security
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_ra = 0
net.ipv6.conf.default.accept_ra = 0
EOF

# 4. Configurazione logrotate
echo "📝 Configurazione logrotate..."
cat > /etc/logrotate.d/CIP << EOF
/var/log/cip_immobiliare/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 cipapp cipapp
    postrotate
        systemctl reload CIP
    endscript
}
EOF

# 5. Configurazione automatic security updates
echo "🔄 Configurazione aggiornamenti automatici..."
apt install -y unattended-upgrades

cat > /etc/apt/apt.conf.d/50unattended-upgrades << EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}";
    "\${distro_id}:\${distro_codename}-security";
    "\${distro_id}ESMApps:\${distro_codename}-apps-security";
    "\${distro_id}ESM:\${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Remove-New-Unused-Dependencies "true";
Unattended-Upgrade::Skip-Updates-On-Metered-Connections "true";
Unattended-Upgrade::Verbose "false";
EOF

cat > /etc/apt/apt.conf.d/20auto-upgrades << EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# 6. Configurazione file permissions
echo "🔒 Configurazione permessi file..."
chmod 600 /etc/ssh/sshd_config
chmod 644 /etc/ssh/banner
chmod 600 /etc/fail2ban/jail.local

# 7. Disabilita servizi non necessari
echo "🚫 Disabilitazione servizi non necessari..."
systemctl disable --now snapd
systemctl disable --now snapd.socket
systemctl disable --now snapd.seeded
systemctl disable --now snapd.autoimport
systemctl disable --now snapd.refresh
systemctl disable --now snapd.refresh.timer

# 8. Configurazione limits
echo "📊 Configurazione limits..."
cat >> /etc/security/limits.conf << EOF
# CIP Immobiliare limits
cipapp soft nofile 65536
cipapp hard nofile 65536
cipapp soft nproc 4096
cipapp hard nproc 4096
EOF

# 9. Riavvia servizi
echo "🔄 Riavvio servizi..."
systemctl restart sshd
systemctl restart fail2ban
systemctl enable fail2ban
sysctl -p

# 10. Verifica configurazione
echo "✅ Verifica configurazione sicurezza..."
echo "🔍 Stato fail2ban:"
fail2ban-client status

echo "🔍 Stato firewall:"
ufw status

echo "🔍 Configurazione SSH:"
sshd -t

echo "✅ Hardening sicurezza completato!"
echo "📋 Raccomandazioni aggiuntive:"
echo "1. Configura backup automatici"
echo "2. Monitora i log regolarmente"
echo "3. Aggiorna regolarmente il sistema"
echo "4. Considera l'uso di un WAF (Web Application Firewall)"
