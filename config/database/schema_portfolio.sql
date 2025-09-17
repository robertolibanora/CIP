-- =====================================================
-- SCHEMA DATABASE PORTFOLIO CIP IMMOBILIARE
-- =====================================================

-- Tabella Portfolio (saldo e investimenti utente)
CREATE TABLE IF NOT EXISTS user_portfolio (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance DECIMAL(15,2) DEFAULT 0.00,
    total_invested DECIMAL(15,2) DEFAULT 0.00,
    total_earned DECIMAL(15,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id)
);

-- Tabella Investimenti
CREATE TABLE IF NOT EXISTS investments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    amount DECIMAL(15,2) NOT NULL,
    percentage DECIMAL(5,2) NOT NULL, -- Percentuale del progetto
    status VARCHAR(20) DEFAULT 'active', -- active, completed, cancelled
    roi_earned DECIMAL(15,2) DEFAULT 0.00,
    investment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completion_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella Transazioni Portfolio
CREATE TABLE IF NOT EXISTS portfolio_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL, -- deposit, withdrawal, investment, roi, referral
    amount DECIMAL(15,2) NOT NULL,
    balance_before DECIMAL(15,2) NOT NULL,
    balance_after DECIMAL(15,2) NOT NULL,
    description TEXT,
    reference_id INTEGER NULL, -- ID dell'investimento o referral
    reference_type VARCHAR(20) NULL, -- investment, referral, project
    status VARCHAR(20) DEFAULT 'completed', -- pending, completed, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella Sistema Referral
CREATE TABLE IF NOT EXISTS referrals (
    id SERIAL PRIMARY KEY,
    referrer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referral_code VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, inactive, banned
    first_investment_date TIMESTAMP NULL,
    total_invested DECIMAL(15,2) DEFAULT 0.00,
    commission_earned DECIMAL(15,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(referred_user_id),
    UNIQUE(referral_code)
);

-- Tabella Commissioni Referral
CREATE TABLE IF NOT EXISTS referral_commissions (
    id SERIAL PRIMARY KEY,
    referral_id INTEGER NOT NULL REFERENCES referrals(id) ON DELETE CASCADE,
    referrer_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    referred_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id INTEGER NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    investment_amount DECIMAL(15,2) NOT NULL,
    commission_amount DECIMAL(15,2) NOT NULL, -- 3% dell'investimento
    status VARCHAR(20) DEFAULT 'pending', -- pending, paid, cancelled
    payout_date TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella Codici Referral
CREATE TABLE IF NOT EXISTS referral_codes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL UNIQUE,
    is_active BOOLEAN DEFAULT TRUE,
    max_uses INTEGER NULL, -- NULL = illimitato
    current_uses INTEGER DEFAULT 0,
    expires_at TIMESTAMP NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella Progetti Immobiliari
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- residential, commercial, industrial
    total_amount DECIMAL(15,2) NOT NULL,
    funded_amount DECIMAL(15,2) DEFAULT 0.00,
    min_investment DECIMAL(15,2) NOT NULL,
    roi DECIMAL(5,2) NOT NULL, -- ROI atteso in percentuale
    duration INTEGER NOT NULL, -- Durata in mesi
    status VARCHAR(20) DEFAULT 'funding', -- funding, active, completed, cancelled
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    image_url VARCHAR(500) NULL,
    documents JSONB NULL, -- Array di documenti
    gallery JSONB NULL, -- Array di immagini
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella Attività Portfolio
CREATE TABLE IF NOT EXISTS portfolio_activities (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(20) NOT NULL, -- investment, referral, roi, deposit, withdrawal
    description TEXT NOT NULL,
    amount DECIMAL(15,2) NULL,
    reference_id INTEGER NULL,
    reference_type VARCHAR(20) NULL,
    metadata JSONB NULL, -- Dati aggiuntivi specifici per tipo
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- INDICI PER PERFORMANCE
-- =====================================================

-- Indici Portfolio
CREATE INDEX IF NOT EXISTS idx_user_portfolio_user_id ON user_portfolio(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_user_id ON investments(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_project_id ON investments(project_id);
CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status);
CREATE INDEX IF NOT EXISTS idx_investments_date ON investments(investment_date);

-- Indici Transazioni
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_user_id ON portfolio_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_type ON portfolio_transactions(type);
CREATE INDEX IF NOT EXISTS idx_portfolio_transactions_date ON portfolio_transactions(created_at);

-- Indici Referral
CREATE INDEX IF NOT EXISTS idx_referrals_referrer_id ON referrals(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referrals_referred_user_id ON referrals(referred_user_id);
CREATE INDEX IF NOT EXISTS idx_referrals_code ON referrals(referral_code);
CREATE INDEX IF NOT EXISTS idx_referral_commissions_referrer_id ON referral_commissions(referrer_id);
CREATE INDEX IF NOT EXISTS idx_referral_commissions_status ON referral_commissions(status);

-- Indici Progetti
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_type ON projects(type);
CREATE INDEX IF NOT EXISTS idx_projects_location ON projects(location);

-- Indici Attività
CREATE INDEX IF NOT EXISTS idx_portfolio_activities_user_id ON portfolio_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_activities_type ON portfolio_activities(type);
CREATE INDEX IF NOT EXISTS idx_portfolio_activities_date ON portfolio_activities(created_at);

-- =====================================================
-- TRIGGER PER AGGIORNAMENTO TIMESTAMP
-- =====================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Applica trigger a tutte le tabelle con updated_at
CREATE TRIGGER update_user_portfolio_updated_at BEFORE UPDATE ON user_portfolio FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_investments_updated_at BEFORE UPDATE ON investments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_portfolio_transactions_updated_at BEFORE UPDATE ON portfolio_transactions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referrals_updated_at BEFORE UPDATE ON referrals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_commissions_updated_at BEFORE UPDATE ON referral_commissions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_referral_codes_updated_at BEFORE UPDATE ON referral_codes FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- VISTE UTILI
-- =====================================================

-- Vista Portfolio Utente Completo
CREATE OR REPLACE VIEW user_portfolio_view AS
SELECT 
    up.id,
    up.user_id,
    u.username,
    u.first_name,
    u.last_name,
    up.balance,
    up.total_invested,
    up.total_earned,
    COUNT(i.id) as active_investments,
    COUNT(r.id) as total_referrals,
    COALESCE(SUM(rc.commission_amount), 0) as total_referral_commission,
    up.created_at,
    up.updated_at
FROM user_portfolio up
JOIN users u ON up.user_id = u.id
LEFT JOIN investments i ON up.user_id = i.user_id AND i.status = 'active'
LEFT JOIN referrals r ON up.user_id = r.referrer_id
LEFT JOIN referral_commissions rc ON up.user_id = rc.referrer_id
GROUP BY up.id, up.user_id, u.username, u.first_name, u.last_name, up.balance, up.total_invested, up.total_earned, up.created_at, up.updated_at;

-- Vista Progetti con Statistiche
CREATE OR REPLACE VIEW projects_stats_view AS
SELECT 
    p.*,
    COUNT(i.id) as total_investors,
    COALESCE(SUM(i.amount), 0) as total_funded,
    CASE 
        WHEN p.total_amount > 0 THEN (COALESCE(SUM(i.amount), 0) / p.total_amount) * 100
        ELSE 0 
    END as funding_progress,
    AVG(i.roi_earned) as avg_roi_earned
FROM projects p
LEFT JOIN investments i ON p.id = i.project_id AND i.status = 'active'
GROUP BY p.id;

-- Vista Commissioni Referral Dettagliate
CREATE OR REPLACE VIEW referral_commissions_view AS
SELECT 
    rc.*,
    u1.username as referrer_username,
    u1.first_name as referrer_first_name,
    u1.last_name as referrer_last_name,
    u2.username as referred_username,
    u2.first_name as referred_first_name,
    u2.last_name as referred_last_name,
    p.name as project_name,
    p.type as project_type,
    i.amount as investment_amount,
    i.investment_date
FROM referral_commissions rc
JOIN users u1 ON rc.referrer_id = u1.id
JOIN users u2 ON rc.referred_user_id = u2.id
JOIN projects p ON rc.project_id = p.id
JOIN investments i ON rc.investment_id = i.id;

-- =====================================================
-- FUNZIONI UTILITY
-- =====================================================

-- Funzione per calcolare commissione referral (3%)
CREATE OR REPLACE FUNCTION calculate_referral_commission(investment_amount DECIMAL)
RETURNS DECIMAL AS $$
BEGIN
    RETURN investment_amount * 0.03; -- 3%
END;
$$ LANGUAGE plpgsql;

-- Funzione per aggiornare balance portfolio
CREATE OR REPLACE FUNCTION update_portfolio_balance(
    p_user_id INTEGER,
    p_amount DECIMAL,
    p_type VARCHAR
)
RETURNS VOID AS $$
BEGIN
    UPDATE user_portfolio 
    SET 
        balance = CASE 
            WHEN p_type IN ('deposit', 'roi', 'referral') THEN balance + p_amount
            WHEN p_type IN ('withdrawal', 'investment') THEN balance - p_amount
            ELSE balance
        END,
        total_invested = CASE 
            WHEN p_type = 'investment' THEN total_invested + p_amount
            ELSE total_invested
        END,
        total_earned = CASE 
            WHEN p_type IN ('roi', 'referral') THEN total_earned + p_amount
            ELSE total_earned
        END
    WHERE user_id = p_user_id;
END;
$$ LANGUAGE plpgsql;
