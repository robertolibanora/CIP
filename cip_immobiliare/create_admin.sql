-- Script per creare un utente admin iniziale
-- Esegui dopo aver creato le tabelle con schema.sql

-- Crea utente admin (password: admin123)
INSERT INTO users (email, password_hash, full_name, role, kyc_status) 
VALUES (
    'admin@cip.com', 
    'pbkdf2:sha256:600000$YOUR_SALT_HERE$YOUR_HASH_HERE',  -- Sostituisci con hash reale
    'Administrator',
    'admin',
    'verified'
) ON CONFLICT (email) DO NOTHING;

-- Crea alcuni progetti di esempio
INSERT INTO projects (code, title, description, status, target_amount, start_date, end_date) VALUES
('PROJ001', 'Residenza Milano Centro', 'Appartamenti di lusso nel cuore di Milano', 'active', 500000.00, '2024-01-01', '2024-12-31'),
('PROJ002', 'Uffici Roma EUR', 'Spazi commerciali moderni', 'draft', 750000.00, '2024-06-01', '2025-06-01'),
('PROJ003', 'Hotel Venezia', 'Ristrutturazione hotel storico', 'active', 1200000.00, '2024-03-01', '2025-03-01')
ON CONFLICT (code) DO NOTHING;

-- Crea alcune categorie documento aggiuntive
INSERT INTO doc_categories (slug, name, is_kyc) VALUES
('income_proof', 'Certificato redditi', TRUE),
('bank_statement', 'Estratto conto bancario', TRUE),
('tax_return', 'Dichiarazione dei redditi', FALSE)
ON CONFLICT (slug) DO NOTHING;

-- Nota: Per generare un hash password reale, usa Python:
-- from werkzeug.security import generate_password_hash
-- print(generate_password_hash('admin123'))
