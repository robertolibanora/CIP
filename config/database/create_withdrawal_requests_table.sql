-- Creazione tabella withdrawal_requests per i prelievi
CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount DECIMAL(10,2) NOT NULL,
    method TEXT CHECK (method IN ('usdt', 'bank')),
    source_section TEXT CHECK (source_section IN ('free_capital','referral_bonus','profits')),
    wallet_address TEXT,
    network TEXT DEFAULT 'BEP20',
    bank_details JSONB,
    unique_key TEXT UNIQUE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'cancelled')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    approved_at TIMESTAMP,
    approved_by INTEGER REFERENCES users(id),
    admin_notes TEXT
);

-- Aggiungi indici per performance
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_user_id ON withdrawal_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status ON withdrawal_requests(status);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_created_at ON withdrawal_requests(created_at);
