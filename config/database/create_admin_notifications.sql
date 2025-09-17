-- Tabella per notifiche admin
-- Sistema di notifiche per KYC, depositi e prelievi

CREATE TABLE IF NOT EXISTS admin_notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL CHECK (type IN ('kyc', 'deposit', 'withdrawal')),
    user_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    read_by INT,
    metadata JSONB, -- Dati aggiuntivi specifici per tipo
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (read_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_admin_notifications_type ON admin_notifications(type);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_is_read ON admin_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_created_at ON admin_notifications(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_user_id ON admin_notifications(user_id);

-- Commenti
COMMENT ON TABLE admin_notifications IS 'Notifiche per admin su azioni utenti (KYC, depositi, prelievi)';
COMMENT ON COLUMN admin_notifications.type IS 'Tipo notifica: kyc, deposit, withdrawal';
COMMENT ON COLUMN admin_notifications.user_id IS 'ID utente che ha generato la notifica';
COMMENT ON COLUMN admin_notifications.title IS 'Titolo della notifica';
COMMENT ON COLUMN admin_notifications.message IS 'Messaggio dettagliato della notifica';
COMMENT ON COLUMN admin_notifications.is_read IS 'Se la notifica è stata letta dall admin';
COMMENT ON COLUMN admin_notifications.metadata IS 'Dati aggiuntivi specifici per tipo (es. amount per depositi)';
