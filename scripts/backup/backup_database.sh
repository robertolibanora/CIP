#!/bin/bash

# Script di backup automatico per CIP Immobiliare
# Esegui questo script con cron per backup regolari

# Configurazione
BACKUP_DIR="/var/backups/cip_immobiliare"
DB_NAME="cip_immobiliare_prod"
DB_USER="cip_app_user"
BACKUP_RETENTION_DAYS=30

# Crea directory backup se non esiste
mkdir -p "$BACKUP_DIR"

# Nome file backup con timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/cip_immobiliare_$TIMESTAMP.sql"

# Esegui backup
echo "🔄 Backup database $DB_NAME..."
pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "$BACKUP_FILE"

# Comprimi backup
gzip "$BACKUP_FILE"
BACKUP_FILE_COMPRESSED="$BACKUP_FILE.gz"

# Verifica backup
if [ -f "$BACKUP_FILE_COMPRESSED" ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE_COMPRESSED" | cut -f1)
    echo "✅ Backup completato: $BACKUP_FILE_COMPRESSED ($BACKUP_SIZE)"
    
    # Rimuovi backup vecchi
    find "$BACKUP_DIR" -name "cip_immobiliare_*.sql.gz" -mtime +$BACKUP_RETENTION_DAYS -delete
    echo "🧹 Rimossi backup più vecchi di $BACKUP_RETENTION_DAYS giorni"
    
    # Log del backup
    echo "$(date): Backup completato - $BACKUP_FILE_COMPRESSED ($BACKUP_SIZE)" >> "$BACKUP_DIR/backup.log"
else
    echo "❌ Errore durante il backup"
    exit 1
fi
