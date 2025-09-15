-- Tabelle per configurazioni sistema (SQLite)
-- Esegui questo script per creare le tabelle necessarie

-- Tabella per configurazioni bancarie (bonifici)
CREATE TABLE IF NOT EXISTS bank_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank_name VARCHAR(255) NOT NULL,
    account_holder VARCHAR(255) NOT NULL,
    iban VARCHAR(34) NOT NULL,
    bic_swift VARCHAR(11),
    bank_address TEXT,
    notes TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Tabella per configurazioni wallet USDT BEP20
CREATE TABLE IF NOT EXISTS wallet_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_name VARCHAR(255) NOT NULL,
    wallet_address VARCHAR(255) NOT NULL,
    network VARCHAR(50) DEFAULT 'BEP20',
    qr_code_url VARCHAR(500),
    notes TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Tabella per configurazioni generali sistema
CREATE TABLE IF NOT EXISTS system_configurations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type VARCHAR(20) DEFAULT 'string',
    description TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER REFERENCES users(id) ON DELETE SET NULL
);

-- Inserisci configurazioni di default
INSERT OR IGNORE INTO system_configurations (config_key, config_value, config_type, description) VALUES
('min_deposit_amount', '100', 'number', 'Importo minimo per deposito'),
('max_deposit_amount', '10000', 'number', 'Importo massimo per deposito'),
('deposit_fee_percentage', '0', 'number', 'Commissione deposito in percentuale'),
('withdrawal_fee_fixed', '5', 'number', 'Commissione fissa per prelievo'),
('kyc_required_amount', '1000', 'number', 'Soglia oltre la quale è richiesto KYC'),
('platform_name', 'CIP Real Estate', 'string', 'Nome della piattaforma'),
('platform_email', 'info@ciprealestate.com', 'string', 'Email di contatto'),
('platform_phone', '+39 02 1234567', 'string', 'Telefono di contatto');

-- Indici per performance
CREATE INDEX IF NOT EXISTS idx_bank_configs_active ON bank_configurations(is_active);
CREATE INDEX IF NOT EXISTS idx_wallet_configs_active ON wallet_configurations(is_active);
CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configurations(config_key);
CREATE INDEX IF NOT EXISTS idx_system_configs_active ON system_configurations(is_active);
