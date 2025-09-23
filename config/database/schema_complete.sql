-- =====================================================
-- SCHEMA COMPLETO DATABASE CIP IMMOBILIARE
-- Task 1.1: Database e Modelli Base
-- =====================================================

-- RESET SCHEMA (DROP in correct dependency order)
DROP VIEW IF EXISTS v_admin_metrics CASCADE;
DROP VIEW IF EXISTS v_user_bonus CASCADE;
DROP VIEW IF EXISTS v_user_invested CASCADE;
DROP VIEW IF EXISTS v_portfolio_summary CASCADE;
DROP VIEW IF EXISTS v_deposit_requests CASCADE;
DROP VIEW IF EXISTS v_withdrawal_requests CASCADE;
DROP VIEW IF EXISTS v_profit_distributions CASCADE;

DROP TABLE IF EXISTS profit_distributions CASCADE;
DROP TABLE IF EXISTS project_sales CASCADE;
DROP TABLE IF EXISTS withdrawal_requests CASCADE;
DROP TABLE IF EXISTS deposit_requests CASCADE;
DROP TABLE IF EXISTS iban_configurations CASCADE;
DROP TABLE IF EXISTS portfolio_transactions CASCADE;
DROP TABLE IF EXISTS user_portfolios CASCADE;
DROP TABLE IF EXISTS referral_commissions CASCADE;
DROP TABLE IF EXISTS referrals CASCADE;
DROP TABLE IF EXISTS referral_codes CASCADE;
DROP TABLE IF EXISTS investment_yields CASCADE;
DROP TABLE IF EXISTS investments CASCADE;
DROP TABLE IF EXISTS investment_requests CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS doc_categories CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ============================================================================
-- 1. SCHEMA KYC - Tabelle documenti e stati verifica
-- ============================================================================

-- Categorie documenti
CREATE TABLE IF NOT EXISTS doc_categories (
    id              SERIAL PRIMARY KEY,
    slug            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    is_kyc          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Documenti utente (KYC e altri)
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

-- ============================================================================
-- 2. SCHEMA PORTFOLIO - 4 sezioni capitali con relazioni
-- ============================================================================

-- Portafoglio utente con 4 sezioni distinte
CREATE TABLE IF NOT EXISTS user_portfolios (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    
    -- 1. Capitale Libero - Soldi non investiti, sempre prelevabili
    free_capital        NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 2. Capitale Investito - bloccato fino alla vendita dell'immobile
    invested_capital    NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 3. Bonus - 3% referral, sempre disponibili per prelievo/investimento
    referral_bonus      NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    -- 4. Profitti - Rendimenti accumulati, prelevabili o reinvestibili
    profits             NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Transazioni portafoglio
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

-- ============================================================================
-- 3. SCHEMA RICARICHE - Richieste, IBAN, chiavi univoche
-- ============================================================================

-- Configurazione IBAN per ricariche
CREATE TABLE IF NOT EXISTS iban_configurations (
    id                  SERIAL PRIMARY KEY,
    iban                TEXT NOT NULL UNIQUE,
    bank_name           TEXT NOT NULL,
    account_holder      TEXT NOT NULL,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Richieste ricarica
CREATE TABLE IF NOT EXISTS deposit_requests (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount >= 500.00),
    iban                TEXT NOT NULL,
    unique_key          TEXT NOT NULL UNIQUE, -- 6 caratteri alfanumerici
    payment_reference   TEXT NOT NULL UNIQUE, -- Chiave randomica per causale bonifico
    status              TEXT NOT NULL CHECK (status IN ('pending','completed','failed','cancelled')) DEFAULT 'pending',
    admin_notes         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at         TIMESTAMPTZ,
    approved_by         INT REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================================
-- 4. SCHEMA PRELIEVI - Richieste e stati approvazione
-- ============================================================================

-- Richieste prelievo
CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount >= 50.00),
    method              TEXT NOT NULL CHECK (method IN ('usdt', 'bank')),
    source_section      TEXT NOT NULL CHECK (source_section IN ('free_capital','referral_bonus','profits')),
    wallet_address      TEXT, -- Per prelievi USDT (BEP20)
    bank_details        JSONB, -- Per prelievi bancari (IBAN, intestatario, banca)
    unique_key          TEXT NOT NULL UNIQUE, -- 6 caratteri alfanumerici
    status              TEXT NOT NULL CHECK (status IN ('pending','completed','failed','cancelled')) DEFAULT 'pending',
    admin_notes         TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at         TIMESTAMPTZ,
    approved_by         INT REFERENCES users(id) ON DELETE SET NULL
);

-- ============================================================================
-- 5. SCHEMA RENDIMENTI - Calcoli profitti e referral
-- ============================================================================

-- Vendite progetti immobiliari
CREATE TABLE IF NOT EXISTS project_sales (
    id                  SERIAL PRIMARY KEY,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    sale_price          NUMERIC(15,2) NOT NULL CHECK (sale_price > 0),
    sale_date           DATE NOT NULL,
    admin_id            INT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Distribuzione profitti e referral
CREATE TABLE IF NOT EXISTS profit_distributions (
    id                  SERIAL PRIMARY KEY,
    project_sale_id     INT NOT NULL REFERENCES project_sales(id) ON DELETE CASCADE,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    original_investment NUMERIC(15,2) NOT NULL,
    profit_share        NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    referral_bonus      NUMERIC(15,2) NOT NULL DEFAULT 0.00, -- 3% del profitto per chi ha invitato
    total_payout        NUMERIC(15,2) NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('pending','completed','failed','cancelled')) DEFAULT 'pending',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at             TIMESTAMPTZ
);

-- ============================================================================
-- 6. SCHEMA BASE UTENTI E PROGETTI (aggiornato)
-- ============================================================================

-- Utenti con gestione KYC
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

-- Progetti immobiliari
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

-- Richieste investimento
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

-- Investimenti
CREATE TABLE IF NOT EXISTS investments (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    percentage          NUMERIC(6,3) NOT NULL CHECK (percentage > 0),
    status              TEXT NOT NULL CHECK (status IN ('pending','active','completed','cancelled')) DEFAULT 'pending',
    roi_earned          NUMERIC(15,2) NOT NULL DEFAULT 0.00,
    investment_date     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completion_date     TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Rendimenti investimenti
CREATE TABLE IF NOT EXISTS investment_yields (
    id                  SERIAL PRIMARY KEY,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    amount              NUMERIC(15,2) NOT NULL CHECK (amount >= 0),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 7. SCHEMA REFERRAL E NOTIFICHE
-- ============================================================================

-- Sistema referral
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

-- Commissioni referral
CREATE TABLE IF NOT EXISTS referral_commissions (
    id                  SERIAL PRIMARY KEY,
    referral_id         INT NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    referrer_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id    INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id       INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    project_id          INT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investment_amount   NUMERIC(15,2) NOT NULL,
    commission_amount   NUMERIC(15,2) NOT NULL, -- 3% dell'investimento
    status              TEXT NOT NULL CHECK (status IN ('pending','paid','cancelled')) DEFAULT 'pending',
    payout_date         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Codici referral
CREATE TABLE IF NOT EXISTS referral_codes (
    id                  SERIAL PRIMARY KEY,
    user_id             INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code                TEXT NOT NULL UNIQUE,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    max_uses            INTEGER, -- NULL = illimitato
    current_uses        INTEGER NOT NULL DEFAULT 0,
    expires_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- INDICI PER PERFORMANCE
-- ============================================================================

-- Indici KYC
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_category_id ON documents(category_id);
CREATE INDEX IF NOT EXISTS idx_documents_verified_by_admin ON documents(verified_by_admin);

-- Indici Portfolio
CREATE INDEX IF NOT EXISTS idx_user_portfolios_user_id ON user_portfolios(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user_id ON portfolio_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_type ON portfolio_transactions(type);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_status ON portfolio_transactions(status);

-- Indici Ricariche
CREATE INDEX IF NOT EXISTS idx_deposit_requests_user_id ON deposit_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_status ON deposit_requests(status);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_unique_key ON deposit_requests(unique_key);
CREATE INDEX IF NOT EXISTS idx_deposit_requests_payment_reference ON deposit_requests(payment_reference);

-- Indici Prelievi
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_user_id ON withdrawal_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_status ON withdrawal_requests(status);
CREATE INDEX IF NOT EXISTS idx_withdrawal_requests_source_section ON withdrawal_requests(source_section);

-- Indici Rendimenti
CREATE INDEX IF NOT EXISTS idx_project_sales_project_id ON project_sales(project_id);
CREATE INDEX IF NOT EXISTS idx_profit_distributions_project_sale_id ON profit_distributions(project_sale_id);
CREATE INDEX IF NOT EXISTS idx_profit_distributions_user_id ON profit_distributions(user_id);

-- Indici base
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(nome_telegram);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(telefono);
CREATE INDEX IF NOT EXISTS idx_users_kyc_status ON users(kyc_status);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type);
CREATE INDEX IF NOT EXISTS idx_investments_user_id ON investments(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_project_id ON investments(project_id);
CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status);
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred_user_id ON referrals(referred_user_id);

-- ============================================================================
-- TRIGGER PER AGGIORNAMENTO TIMESTAMP
-- ============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Applica trigger a tutte le tabelle con updated_at
CREATE TRIGGER update_user_portfolios_updated_at BEFORE UPDATE ON user_portfolios FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_investments_updated_at BEFORE UPDATE ON investments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referrals_updated_at BEFORE UPDATE ON referrals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_commissions_updated_at BEFORE UPDATE ON referral_commissions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_codes_updated_at BEFORE UPDATE ON referral_codes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_iban_configurations_updated_at BEFORE UPDATE ON iban_configurations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- VISTE UTILI
-- ============================================================================

-- Vista riepilogo portfolio utente
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

-- Vista richieste ricarica
CREATE OR REPLACE VIEW v_deposit_requests AS
SELECT 
    dr.*,
    u.email,
    u.nome,
    u.cognome,
    u.kyc_status,
    ic.bank_name,
    ic.account_holder
FROM deposit_requests dr
JOIN users u ON dr.user_id = u.id
JOIN iban_configurations ic ON dr.iban = ic.iban;

-- Vista richieste prelievo
CREATE OR REPLACE VIEW v_withdrawal_requests AS
SELECT 
    wr.*,
    u.email,
    u.nome,
    u.cognome,
    u.kyc_status,
    up.free_capital,
    up.referral_bonus,
    up.profits
FROM withdrawal_requests wr
JOIN users u ON wr.user_id = u.id
JOIN user_portfolios up ON wr.user_id = up.user_id;

-- Vista distribuzione profitti
CREATE OR REPLACE VIEW v_profit_distributions AS
SELECT 
    pd.*,
    u.email,
    u.nome,
    u.cognome,
    p.name as project_name,
    ps.sale_price,
    ps.sale_date
FROM profit_distributions pd
JOIN users u ON pd.user_id = u.id
JOIN projects p ON pd.investment_id IN (SELECT id FROM investments WHERE project_id = p.id)
JOIN project_sales ps ON pd.project_sale_id = ps.id;

-- Vista metriche admin
CREATE OR REPLACE VIEW v_admin_metrics AS
SELECT 
    (SELECT COUNT(*) FROM users) AS users_total,
    (SELECT COUNT(*) FROM users WHERE kyc_status = 'verified') AS users_verified,
    (SELECT COUNT(*) FROM users WHERE kyc_status = 'pending') AS users_pending_kyc,
    (SELECT COUNT(*) FROM projects WHERE status IN ('active','funding')) AS projects_active,
    (SELECT COALESCE(SUM(amount),0) FROM investments WHERE status = 'active') AS investments_total,
    (SELECT COUNT(*) FROM deposit_requests WHERE status = 'pending') AS deposits_pending,
    (SELECT COUNT(*) FROM withdrawal_requests WHERE status = 'pending') AS withdrawals_pending,
    (SELECT COALESCE(SUM(amount),0) FROM deposit_requests WHERE status = 'completed') AS deposits_total,
    (SELECT COALESCE(SUM(amount),0) FROM withdrawal_requests WHERE status = 'completed') AS withdrawals_total;

-- ============================================================================
-- FUNZIONI UTILITY
-- ============================================================================

-- Funzione per calcolare commissione referral (3%)
CREATE OR REPLACE FUNCTION calculate_referral_commission(investment_amount NUMERIC)
RETURNS NUMERIC AS $$
BEGIN
    RETURN investment_amount * 0.03; -- 3%
END;
$$ LANGUAGE plpgsql;

-- Funzione per aggiornare balance portfolio
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

-- Funzione per generare chiave univoca 6 caratteri
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

-- ============================================================================
-- SEED DATA INIZIALE
-- ============================================================================

-- Categorie documenti
INSERT INTO doc_categories (slug, name, is_kyc) VALUES
('id_card', 'Documento identità', TRUE),
('residence', 'Patente di Guida', TRUE),
('passport', 'Passaporto', TRUE),
('contract', 'Contratto', FALSE),
('other', 'Altro', FALSE)
ON CONFLICT DO NOTHING;

-- Configurazione IBAN default
INSERT INTO iban_configurations (iban, bank_name, account_holder, is_active) VALUES
('IT60X0542811101000000123456', 'Banca Example', 'CIP Immobiliare SRL', TRUE)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- COMMENTI TABELLE
-- ============================================================================

COMMENT ON TABLE users IS 'Utenti sistema con gestione KYC';
COMMENT ON TABLE user_portfolios IS 'Portafoglio utente con 4 sezioni capitali distinte';
COMMENT ON TABLE portfolio_transactions IS 'Transazioni portafoglio per audit trail';
COMMENT ON TABLE deposit_requests IS 'Richieste ricarica con chiavi univoche';
COMMENT ON TABLE withdrawal_requests IS 'Richieste prelievo da sezioni specifiche';
COMMENT ON TABLE project_sales IS 'Vendite progetti per calcolo rendimenti';
COMMENT ON TABLE profit_distributions IS 'Distribuzione profitti e bonus referral';
COMMENT ON TABLE documents IS 'Documenti KYC e altri file utente';
COMMENT ON TABLE projects IS 'Progetti immobiliari investibili';
COMMENT ON TABLE investments IS 'Investimenti utenti nei progetti';
COMMENT ON TABLE referrals IS 'Sistema referral con commissioni 3%';
