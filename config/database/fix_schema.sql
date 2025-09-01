-- =====================================================
-- FIX SCHEMA - Ricrea database con ordine corretto
-- =====================================================

-- Elimina tutto
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- 1. Prima le tabelle base senza dipendenze
CREATE TABLE IF NOT EXISTS users (
    id                  SERIAL PRIMARY KEY,
    email               TEXT UNIQUE NOT NULL,
    password_hash       TEXT NOT NULL,
    full_name           TEXT,
    nome                TEXT NOT NULL,
    cognome             TEXT NOT NULL,
    nome_telegram       TEXT UNIQUE NOT NULL,
    telefono            TEXT NOT NULL,
    address             TEXT,
    role                TEXT NOT NULL CHECK (role IN ('admin','investor')) DEFAULT 'investor',
    kyc_status          TEXT NOT NULL CHECK (kyc_status IN ('unverified','pending','verified','rejected')) DEFAULT 'unverified',
    currency_code       CHAR(3) NOT NULL DEFAULT 'EUR',
    referral_code       TEXT UNIQUE,
    referral_link       TEXT,
    referred_by         INT REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS doc_categories (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    is_kyc          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS projects (
    id                  SERIAL PRIMARY KEY,
    code                TEXT UNIQUE NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    location            TEXT NOT NULL,
    type                TEXT NOT NULL CHECK (type IN ('residential','commercial','industrial')),
    total_amount        NUMERIC(15,2) NOT NULL CHECK (total_amount > 0),
    funded_amount       NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    min_investment      NUMERIC(15,2) NOT NULL CHECK (min_investment > 0),
    roi                 NUMERIC(6,3) NOT NULL CHECK (roi > 0),
    duration            INTEGER NOT NULL CHECK (duration > 0),
    status              TEXT NOT NULL CHECK (status IN ('draft','funding','active','completed','cancelled')) DEFAULT 'draft',
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    image_url           TEXT,
    documents           JSONB,
    gallery             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Tabelle che dipendono da users
CREATE TABLE IF NOT EXISTS documents (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id         INT NOT NULL REFERENCES doc_categories(id) ON DELETE RESTRICT,
    title               TEXT,
    file_path           TEXT NOT NULL,
    mime_type           TEXT,
    size_bytes          BIGINT,
    visibility          TEXT NOT NULL CHECK (visibility IN ('private','admin','public')) DEFAULT 'private',
    verified_by_admin   BOOLEAN NOT NULL DEFAULT FALSE,
    admin_notes         TEXT,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    verified_at         TIMESTAMPTZ,
    verified_by         INT REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS user_portfolios (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- 1. Capitale Libero - Soldi non investiti, sempre prelevabili
    free_capital        NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 2. Capitale Investito - Bloccato fino alla vendita dell'immobile
    invested_capital    NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 3. Bonus - 1% referral, sempre disponibili per prelievo/investimento
    referral_bonus      NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 4. Profitti - Rendimenti accumulati, prelevabili o reinvestibili
    profits             NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investment_requests (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    cro_file_path       TEXT,
    state               TEXT NOT NULL CHECK (state IN ('in_review','approved','rejected','cancelled')) DEFAULT 'in_review',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS investments (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    status              TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','active','completed','cancelled')) DEFAULT 'pending',
    expected_yield_pct  NUMERIC(6,3),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at        TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS referral_codes (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code                TEXT NOT NULL UNIQUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    max_uses            INT,
    current_uses        INT NOT NULL DEFAULT 0,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referrals (
    id                  SERIAL PRIMARY KEY,
    referrer_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referral_code       TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('active','inactive','banned')) DEFAULT 'active',
    first_investment_date TIMESTAMPTZ,
    total_invested      NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    commission_earned   NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(referred_user_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id                  SERIAL PRIMARY KEY,
    user_id             INT REFERENCES users(id) ON DELETE CASCADE,
    priority            TEXT NOT NULL CHECK (priority IN ('low','medium','high','urgent')) DEFAULT 'low',
    kind                TEXT NOT NULL DEFAULT 'system',
    title               TEXT NOT NULL,
    body                TEXT,
    is_read             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Tabelle che dipendono da investments
CREATE TABLE IF NOT EXISTS investment_yields (
    id                  SERIAL PRIMARY KEY,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS referral_commissions (
    id                  SERIAL PRIMARY KEY,
    referral_id         INT NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    referrer_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investment_amount   NUMERIC(15,2) NOT NULL,
    commission_amount   NUMERIC(15,2) NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('pending','paid','cancelled')) DEFAULT 'pending',
    payout_date         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Tabelle di sistema
CREATE TABLE IF NOT EXISTS iban_configurations (
    id                  SERIAL PRIMARY KEY,
    iban                TEXT NOT NULL UNIQUE,
    bank_name           TEXT NOT NULL,
    account_holder      TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                TEXT NOT NULL CHECK (type IN ('deposit','withdrawal','investment','roi','referral')),
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    balance_before      NUMERIC(15,2) NOT NULL,
    balance_after       NUMERIC(15,2) NOT NULL,
    description         TEXT NOT NULL,
    reference_id        INT,
    reference_type      TEXT,
    status              TEXT NOT NULL CHECK (status IN ('pending','completed','failed','cancelled')) DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deposit_requests (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    iban                TEXT NOT NULL,
    unique_key          TEXT NOT NULL UNIQUE,
    status              TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','cancelled')) DEFAULT 'pending',
    admin_notes         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    iban                TEXT NOT NULL,
    section             TEXT NOT NULL CHECK (section IN ('free_capital','referral_bonus','profits')),
    status              TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','cancelled')) DEFAULT 'pending',
    admin_notes         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS project_sales (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    sale_amount         NUMERIC(15,2) NOT NULL CHECK (sale_amount > 0),
    sale_date           DATE NOT NULL,
    roi_distributed     NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS profit_distributions (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    project_sale_id     INT NOT NULL REFERENCES project_sales(id) ON DELETE CASCADE,
    roi_amount          NUMERIC(15,2) NOT NULL CHECK (roi_amount >= 0),
    referral_bonus      NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    total_distributed   NUMERIC(15,2) NOT NULL,
    distribution_date   DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indici
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(nome_telegram);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(telefono);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_kyc_status ON users(kyc_status);

CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(category_id);

CREATE INDEX IF NOT EXISTS idx_user_portfolios_user ON user_portfolios(user_id);

CREATE INDEX IF NOT EXISTS idx_investment_requests_user ON investment_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_investment_requests_project ON investment_requests(project_id);
CREATE INDEX IF NOT EXISTS idx_investment_requests_state ON investment_requests(state);

CREATE INDEX IF NOT EXISTS idx_investments_user ON investments(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_project ON investments(project_id);
CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status);

CREATE INDEX IF NOT EXISTS idx_investment_yields_investment ON investment_yields(investment_id);

CREATE INDEX IF NOT EXISTS idx_referral_codes_user ON referral_codes(user_id);
CREATE INDEX IF NOT EXISTS idx_referral_codes_code ON referral_codes(code);

CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred ON referrals(referred_user_id);

CREATE INDEX IF NOT EXISTS idx_referral_commissions_referral ON referral_commissions(referral_id);
CREATE INDEX IF NOT EXISTS idx_referral_commissions_referrer ON referral_commissions(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_commissions_investment ON referral_commissions(investment_id);

CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);

CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user ON portfolio_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_type ON portfolio_transactions(type);

CREATE INDEX IF NOT EXISTS idx_deposit_requests_user ON deposit_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_status ON deposit_requests(status);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_unique_key ON deposit_requests(unique_key);

CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_user ON withdrawal_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status ON withdrawal_requests(status);

CREATE INDEX IF NOT EXISTS idx_project_sales_project ON project_sales(project_id);

CREATE INDEX IF NOT EXISTS idx_profit_distributions_user ON profit_distributions(user_id);
CREATE INDEX IF NOT EXISTS idx_profit_distributions_investment ON profit_distributions(investment_id);

-- Trigger per aggiornamento timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_portfolios_updated_at BEFORE UPDATE ON user_portfolios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_investments_updated_at BEFORE UPDATE ON investments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referrals_updated_at BEFORE UPDATE ON referrals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_commissions_updated_at BEFORE UPDATE ON referral_commissions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_codes_updated_at BEFORE UPDATE ON referral_codes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_iban_configurations_updated_at BEFORE UPDATE ON iban_configurations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Viste
CREATE OR REPLACE VIEW v_portfolio_summary AS
SELECT 
    up.id,
    up.user_id,
    u.email,
    u.nome,
    u.cognome,
    u.kyc_status,
    up.free_capital,
    up.invested_capital,
    up.referral_bonus,
    up.profits,
    (up.free_capital + up.referral_bonus + up.profits) as total_available,
    up.created_at,
    up.updated_at
FROM user_portfolios up
JOIN users u ON up.user_id = u.id;

-- Funzioni
CREATE OR REPLACE FUNCTION calculate_referral_commission(investment_amount NUMERIC)
RETURNS NUMERIC AS $$
BEGIN
    RETURN investment_amount * 0.01;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION update_portfolio_balance(
    p_user_id INTEGER,
    p_amount NUMERIC,
    p_type TEXT,
    p_section TEXT DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    UPDATE user_portfolios 
    SET 
        free_capital = CASE 
            WHEN p_type = 'deposit' THEN free_capital + p_amount
            WHEN p_type = 'withdrawal' AND p_section = 'free_capital' THEN free_capital - p_amount
            WHEN p_type = 'investment' THEN free_capital - p_amount
            ELSE free_capital
        END,
        referral_bonus = CASE 
            WHEN p_type = 'referral' THEN referral_bonus + p_amount
            WHEN p_type = 'withdrawal' AND p_section = 'referral_bonus' THEN referral_bonus - p_amount
            WHEN p_type = 'investment' AND p_section = 'referral_bonus' THEN referral_bonus - p_amount
            ELSE referral_bonus
        END,
        profits = CASE 
            WHEN p_type = 'roi' THEN profits + p_amount
            WHEN p_type = 'withdrawal' AND p_section = 'profits' THEN profits - p_amount
            ELSE profits
        END,
        invested_capital = CASE 
            WHEN p_type = 'investment' THEN invested_capital + p_amount
            WHEN p_type = 'sale_completed' THEN invested_capital - p_amount
            ELSE invested_capital
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generate_unique_key()
RETURNS TEXT AS $$
DECLARE
    chars TEXT := 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    result TEXT := '';
    i INTEGER;
BEGIN
    FOR i IN 1..6 LOOP
        result := result || substr(chars, floor(random() * length(chars))::integer + 1, 1);
    END LOOP;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Seed data
INSERT INTO doc_categories (slug, name, is_kyc) VALUES
('id_card', 'Documento identità', TRUE),
('residence', 'Patente di Guida', TRUE),
('passport', 'Passaporto', TRUE),
('contract', 'Contratto', FALSE),
('other', 'Altro', FALSE)
ON CONFLICT DO NOTHING;

INSERT INTO iban_configurations (iban, bank_name, account_holder, is_active) VALUES
('IT60X0542811101000000123456', 'Banca Example', 'CIP Immobiliare SRL', TRUE)
ON CONFLICT DO NOTHING;

COMMIT;
