-- RESET SCHEMA (DROP in correct dependency order)
DROP VIEW IF EXISTS v_admin_metrics;
DROP VIEW IF EXISTS v_user_bonus;
DROP VIEW IF EXISTS v_user_invested;

DROP TABLE IF EXISTS referral_bonuses CASCADE;
DROP TABLE IF EXISTS notifications CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS doc_categories CASCADE;
DROP TABLE IF EXISTS investment_yields CASCADE;
DROP TABLE IF EXISTS investments CASCADE;
DROP TABLE IF EXISTS investment_requests CASCADE;
DROP TABLE IF EXISTS projects CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- USERS & AUTH
CREATE TABLE IF NOT EXISTS users (
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
CREATE INDEX IF NOT EXISTS idx_users_referred_by ON users(referred_by);
CREATE INDEX IF NOT EXISTS idx_users_telegram ON users(nome_telegram);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(telefono);

-- PROJECTS
CREATE TABLE IF NOT EXISTS projects (
    id              SERIAL PRIMARY KEY,
    code            TEXT UNIQUE NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    status          TEXT NOT NULL CHECK (status IN ('draft','active','funded','in_progress','completed','cancelled')) DEFAULT 'draft',
    total_amount    NUMERIC(14,2),
    funded_amount   NUMERIC(14,2) NOT NULL DEFAULT 0,
    start_date      DATE,
    end_date        DATE,
    address         TEXT,
    min_investment  NUMERIC(14,2) DEFAULT 1000,
    photo_filename  TEXT,
    documents_filename TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_address ON projects(address);

-- INVESTMENT REQUESTS (wizard + CRO)
CREATE TABLE IF NOT EXISTS investment_requests (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    amount          NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    cro_file_path   TEXT,
    state           TEXT NOT NULL CHECK (state IN ('in_review','approved','rejected','cancelled')) DEFAULT 'in_review',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invreq_state ON investment_requests(state);

-- INVESTMENTS
CREATE TABLE IF NOT EXISTS investments (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id      INT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    amount          NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    status          TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','active','completed','cancelled')) DEFAULT 'pending',
    expected_yield_pct NUMERIC(6,3),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at    TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_investments_user ON investments(user_id);
CREATE INDEX IF NOT EXISTS idx_investments_project ON investments(project_id);
CREATE INDEX IF NOT EXISTS idx_investments_status ON investments(status);

-- INVESTMENT YIELDS
CREATE TABLE IF NOT EXISTS investment_yields (
    id              SERIAL PRIMARY KEY,
    investment_id   INT NOT NULL REFERENCES investments(id) ON DELETE CASCADE,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    amount          NUMERIC(14,2) NOT NULL CHECK (amount >= 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_yields_investment ON investment_yields(investment_id);

-- DOCUMENTS & KYC
CREATE TABLE IF NOT EXISTS doc_categories (
    id          SERIAL PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    is_kyc      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS documents (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id     INT NOT NULL REFERENCES doc_categories(id) ON DELETE RESTRICT,
    title           TEXT,
    file_path       TEXT NOT NULL,
    mime_type       TEXT,
    size_bytes      BIGINT,
    visibility      TEXT NOT NULL CHECK (visibility IN ('private','admin','public')) DEFAULT 'private',
    verified_by_admin BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);

-- NOTIFICATIONS
CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    user_id         INT REFERENCES users(id) ON DELETE CASCADE, -- NULL => broadcast
    priority        TEXT NOT NULL CHECK (priority IN ('low','medium','high','urgent')) DEFAULT 'low',
    kind            TEXT NOT NULL DEFAULT 'system',
    title           TEXT NOT NULL,
    body            TEXT,
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read ON notifications(is_read);

-- REFERRAL BONUSES
CREATE TABLE IF NOT EXISTS referral_bonuses (
    id               SERIAL PRIMARY KEY,
    receiver_user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source_user_id   INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    investment_id    INT REFERENCES investments(id) ON DELETE SET NULL,
    level            INT NOT NULL CHECK (level >= 1) DEFAULT 1,
    amount           NUMERIC(14,2) NOT NULL CHECK (amount >= 0) DEFAULT 0,
    month_ref        DATE NOT NULL DEFAULT DATE_TRUNC('month', NOW())::date,
    status           TEXT NOT NULL CHECK (status IN ('accrued','paid','cancelled')) DEFAULT 'accrued',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    paid_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_referral_receiver ON referral_bonuses(receiver_user_id);
CREATE INDEX IF NOT EXISTS idx_referral_month ON referral_bonuses(month_ref);

-- VIEWS
CREATE OR REPLACE VIEW v_user_invested AS
SELECT u.id AS user_id,
       COALESCE(SUM(CASE WHEN i.status IN ('active','completed') THEN i.amount ELSE 0 END),0) AS total_invested,
       COUNT(*) FILTER (WHERE i.status IN ('active')) AS active_count
FROM users u
LEFT JOIN investments i ON i.user_id = u.id
GROUP BY u.id;

CREATE OR REPLACE VIEW v_user_bonus AS
SELECT rb.receiver_user_id AS user_id,
       COALESCE(SUM(rb.amount),0) AS bonus_total
FROM referral_bonuses rb
GROUP BY rb.receiver_user_id;

CREATE OR REPLACE VIEW v_admin_metrics AS
SELECT (SELECT COUNT(*) FROM users) AS users_total,
       (SELECT COUNT(*) FROM projects WHERE status IN ('active','in_progress')) AS projects_active,
       (SELECT COALESCE(SUM(amount),0) FROM investments) AS investments_total,
       (SELECT COUNT(*) FROM investment_requests WHERE state='in_review') AS requests_pending;

-- SEED (facoltativo)
INSERT INTO doc_categories (slug,name,is_kyc) VALUES
('id_card','Documento identità', TRUE),
('residence','Patente di guida, Passaporto', TRUE),
('contract','Contratto', FALSE),
('other','Altro', FALSE)
ON CONFLICT DO NOTHING;
