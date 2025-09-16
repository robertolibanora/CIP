-- Aggiunge il campo is_vip alla tabella users
-- Eseguito il: $(date)

-- Aggiungi il campo is_vip se non esiste
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT FALSE;

-- Aggiorna tutti gli utenti esistenti per avere is_vip = false (già il default)
UPDATE users SET is_vip = FALSE WHERE is_vip IS NULL;

-- Crea un indice per migliorare le performance delle query VIP
CREATE INDEX IF NOT EXISTS idx_users_is_vip ON users(is_vip);

-- Verifica che il campo sia stato aggiunto correttamente
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'users' AND column_name = 'is_vip';
