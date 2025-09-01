-- =====================================================
-- SCHEMA KYC - Sistema di verifica identità
-- =====================================================

-- Tabella categorie documenti
CREATE TABLE IF NOT EXISTS doc_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    is_kyc BOOLEAN DEFAULT FALSE,
    is_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella documenti
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_id INTEGER NOT NULL REFERENCES doc_categories(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes BIGINT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verified_by_admin BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,
    verified_by INTEGER REFERENCES users(id),
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inserisci categorie KYC predefinite
INSERT INTO doc_categories (name, slug, description, is_kyc, is_required) VALUES
('Carta d''Identità', 'id_card', 'Documento di identità italiano (fronte e retro)', TRUE, TRUE),
('Patente di Guida', 'drivers_license', 'Patente di guida italiana (fronte e retro)', TRUE, FALSE),
('Passaporto', 'passport', 'Passaporto italiano (pagina principale)', TRUE, FALSE)
ON CONFLICT (slug) DO NOTHING;

-- Aggiungi colonne KYC alla tabella users se non esistono
DO $$ 
BEGIN
    -- Aggiungi kyc_status se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_status') THEN
        ALTER TABLE users ADD COLUMN kyc_status VARCHAR(20) DEFAULT 'unverified';
    END IF;
    
    -- Aggiungi kyc_verified_at se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_verified_at') THEN
        ALTER TABLE users ADD COLUMN kyc_verified_at TIMESTAMP;
    END IF;
    
    -- Aggiungi kyc_verified_by se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_verified_by') THEN
        ALTER TABLE users ADD COLUMN kyc_verified_by INTEGER REFERENCES users(id);
    END IF;
    
    -- Aggiungi kyc_rejected_at se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_rejected_at') THEN
        ALTER TABLE users ADD COLUMN kyc_rejected_at TIMESTAMP;
    END IF;
    
    -- Aggiungi kyc_rejected_by se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_rejected_by') THEN
        ALTER TABLE users ADD COLUMN kyc_rejected_by INTEGER REFERENCES users(id);
    END IF;
    
    -- Aggiungi kyc_notes se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'kyc_notes') THEN
        ALTER TABLE users ADD COLUMN kyc_notes TEXT;
    END IF;
END $$;

-- Crea indici per performance
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_documents_category_id ON documents(category_id);
CREATE INDEX IF NOT EXISTS idx_documents_uploaded_at ON documents(uploaded_at);
CREATE INDEX IF NOT EXISTS idx_users_kyc_status ON users(kyc_status);
