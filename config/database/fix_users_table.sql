-- Script per correggere la tabella users
-- Elimina e ricrea la tabella con la struttura corretta

-- Elimina la tabella users esistente (cascade per eliminare anche le foreign key)
DROP TABLE IF EXISTS users CASCADE;

-- Ricrea la tabella users con la struttura corretta
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    full_name       TEXT,
    nome            TEXT NOT NULL,
    cognome         TEXT NOT NULL,
    nome_telegram   TEXT UNIQUE NOT NULL,
    telefono        TEXT NOT NULL,
    address         TEXT,
    role            TEXT NOT NULL CHECK (role IN ('admin','investor')) DEFAULT 'investor',
    kyc_status      TEXT NOT NULL CHECK (kyc_status IN ('unverified','pending','verified','rejected')) DEFAULT 'unverified',
    currency_code   CHAR(3) NOT NULL DEFAULT 'EUR',
    referral_code   TEXT UNIQUE,
    referral_link   TEXT,
    referred_by     INT REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Crea gli indici necessari
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(nome_telegram);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(telefono);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Utente admin creato automaticamente dal codice Python all'avvio dell'applicazione
-- Non è più necessario inserirlo manualmente tramite SQL

-- Commit delle modifiche
COMMIT;
