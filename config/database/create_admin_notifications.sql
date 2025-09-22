-- Tabella per notifiche admin
CREATE TABLE IF NOT EXISTS admin_notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL CHECK (type IN ('kyc', 'deposit', 'withdrawal')),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    read_at TIMESTAMP WITH TIME ZONE,
    read_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_admin_notifications_type ON admin_notifications(type);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_user_id ON admin_notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_is_read ON admin_notifications(is_read);
CREATE INDEX IF NOT EXISTS idx_admin_notifications_created_at ON admin_notifications(created_at DESC);

-- Commenti per documentazione
COMMENT ON TABLE admin_notifications IS 'Notifiche per amministratori su eventi utenti';
COMMENT ON COLUMN admin_notifications.type IS 'Tipo di notifica: kyc, deposit, withdrawal';
COMMENT ON COLUMN admin_notifications.user_id IS 'ID utente che ha generato la notifica';
COMMENT ON COLUMN admin_notifications.metadata IS 'Dati aggiuntivi in formato JSON';
COMMENT ON COLUMN admin_notifications.read_by IS 'ID admin che ha letto la notifica';