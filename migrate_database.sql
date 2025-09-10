-- Migrazione database SQLite per CIP Immobiliare
-- Aggiorna la struttura del database alla versione corretta

-- Prima salva i dati esistenti
CREATE TABLE users_backup AS SELECT * FROM users;

-- Elimina la tabella users esistente
DROP TABLE users;

-- Ricrea la tabella users con la struttura corretta per SQLite
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
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
    currency_code   TEXT NOT NULL DEFAULT 'EUR',
    referral_code   TEXT UNIQUE,
    referral_link   TEXT,
    referred_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Crea gli indici necessari
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(nome_telegram);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(telefono);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Migra i dati esistenti (se presenti)
INSERT INTO users (
    id, email, password_hash, full_name, nome, cognome, 
    nome_telegram, telefono, role, kyc_status, created_at
)
SELECT 
    id, 
    email, 
    password_hash, 
    full_name,
    COALESCE(full_name, 'Admin') as nome,
    'CIP' as cognome,
    'admin_cip' as nome_telegram,
    '+39000000000' as telefono,
    'admin' as role,
    'verified' as kyc_status,
    created_at
FROM users_backup;

-- Crea le tabelle mancanti per il funzionamento dell'app

-- Categorie documenti
CREATE TABLE IF NOT EXISTS doc_categories (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    is_kyc          BOOLEAN NOT NULL DEFAULT FALSE,
    is_required     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Documenti utente (KYC e altri)
CREATE TABLE IF NOT EXISTS documents (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id         INTEGER NOT NULL REFERENCES doc_categories(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    file_path           TEXT NOT NULL,
    mime_type           TEXT,
    size_bytes          INTEGER,
    uploaded_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified_by_admin   BOOLEAN NOT NULL DEFAULT FALSE,
    admin_notes         TEXT
);

-- Portfolio utenti
CREATE TABLE IF NOT EXISTS user_portfolios (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total_invested  DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    total_profits   DECIMAL(15,2) NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Transazioni portfolio
CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('deposit', 'withdrawal', 'investment', 'profit', 'bonus')),
    amount          DECIMAL(15,2) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Inserisci categorie documenti KYC
INSERT INTO doc_categories (slug, name, description, is_kyc, is_required) VALUES
('id_card', 'Carta d''Identità', 'Documento di identità italiano (fronte e retro)', 1, 1),
('drivers_license', 'Patente di Guida', 'Patente di guida italiana (fronte e retro)', 1, 0),
('passport', 'Passaporto', 'Passaporto italiano (pagina principale)', 1, 0);

-- Pulisci la tabella di backup
DROP TABLE users_backup;
