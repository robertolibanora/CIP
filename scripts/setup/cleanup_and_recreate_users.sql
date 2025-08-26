-- Script per pulire dati di test e ricreare utenti CIP Immobiliare
-- Esegui: psql -d cip -f cleanup_and_recreate_users.sql

-- =====================================================
-- CLEANUP DATI ESISTENTI (mantiene le tabelle)
-- =====================================================

-- Disabilita temporaneamente i foreign key constraints
SET session_replication_role = replica;

-- Pulisci tutte le tabelle in ordine corretto (dalle dipendenze)
DELETE FROM investment_yields;
DELETE FROM investments;
DELETE FROM investment_requests;
DELETE FROM documents;
DELETE FROM notifications;
DELETE FROM projects;
DELETE FROM users;

-- Riabilita i foreign key constraints
SET session_replication_role = DEFAULT;

-- Reset delle sequenze (auto-increment)
ALTER SEQUENCE users_id_seq RESTART WITH 1;
ALTER SEQUENCE projects_id_seq RESTART WITH 1;
ALTER SEQUENCE investments_id_seq RESTART WITH 1;
ALTER SEQUENCE investment_requests_id_seq RESTART WITH 1;
ALTER SEQUENCE investment_yields_id_seq RESTART WITH 1;
ALTER SEQUENCE documents_id_seq RESTART WITH 1;
ALTER SEQUENCE notifications_id_seq RESTART WITH 1;

-- =====================================================
-- RICREAZIONE UTENTI DI TEST
-- =====================================================

-- Inserisci utente admin
INSERT INTO users (email, password_hash, full_name, role, kyc_status, referral_code, created_at)
VALUES (
    'admin@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Admin CIP',
    'admin',
    'verified',
    'ADMIN001',
    NOW()
);

-- Inserisci utente di test
INSERT INTO users (email, password_hash, full_name, role, kyc_status, referral_code, created_at)
VALUES (
    'test@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Test User',
    'investor',
    'verified',
    'TEST001',
    NOW()
);

-- Inserisci utente demo
INSERT INTO users (email, password_hash, full_name, role, kyc_status, referral_code, created_at)
VALUES (
    'demo@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Demo User',
    'investor',
    'verified',
    'DEMO001',
    NOW()
);

-- Inserisci utente referral (riferito da test)
INSERT INTO users (email, password_hash, full_name, role, kyc_status, referral_code, referred_by, created_at)
VALUES (
    'referral@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Referral User',
    'investor',
    'verified',
    'REF001',
    2, -- ID dell'utente test
    NOW()
);

-- =====================================================
-- RICREAZIONE PROGETTI DI TEST
-- =====================================================

-- Progetto 1: Appartamento Milano
INSERT INTO projects (code, title, description, status, target_amount, raised_amount, start_date, end_date, created_at)
VALUES (
    'MIL-001',
    'Appartamento Milano Centro',
    'Appartamento di lusso nel cuore di Milano, zona Brera. Investimento sicuro con rendimento annuo del 8-12%.',
    'active',
    250000.00,
    180000.00,
    '2024-01-15',
    '2024-12-31',
    NOW()
);

-- Progetto 2: Uffici Roma
INSERT INTO projects (code, title, description, status, target_amount, raised_amount, start_date, end_date, created_at)
VALUES (
    'ROM-001',
    'Uffici Roma EUR',
    'Spazi ufficio moderni nel quartiere EUR di Roma. Affitti garantiti da aziende certificate.',
    'active',
    500000.00,
    320000.00,
    '2024-02-01',
    '2025-06-30',
    NOW()
);

-- Progetto 3: Hotel Firenze
INSERT INTO projects (code, title, description, status, target_amount, raised_amount, start_date, end_date, created_at)
VALUES (
    'FIR-001',
    'Hotel Firenze Centro',
    'Hotel boutique nel centro storico di Firenze. Alto tasso di occupazione tutto l\'anno.',
    'active',
    800000.00,
    450000.00,
    '2024-03-01',
    '2025-12-31',
    NOW()
);

-- =====================================================
-- RICREAZIONE INVESTIMENTI DI TEST
-- =====================================================

-- Investimento 1: Test user in progetto Milano
INSERT INTO investments (user_id, project_id, amount, status, expected_yield_pct, created_at)
VALUES (
    2, -- test@cipimmobiliare.it
    1, -- MIL-001
    25000.00,
    'active',
    10.5,
    NOW()
);

-- Investimento 2: Demo user in progetto Roma
INSERT INTO investments (user_id, project_id, amount, status, expected_yield_pct, created_at)
VALUES (
    3, -- demo@cipimmobiliare.it
    2, -- ROM-001
    50000.00,
    'active',
    9.8,
    NOW()
);

-- Investimento 3: Test user in progetto Firenze
INSERT INTO investments (user_id, project_id, amount, status, expected_yield_pct, created_at)
VALUES (
    2, -- test@cipimmobiliare.it
    3, -- FIR-001
    35000.00,
    'pending',
    11.2,
    NOW()
);

-- =====================================================
-- VERIFICA INSERIMENTI
-- =====================================================

-- Mostra utenti creati
SELECT 
    'USERS' as table_name,
    COUNT(*) as count
FROM users
UNION ALL
SELECT 
    'PROJECTS' as table_name,
    COUNT(*) as count
FROM projects
UNION ALL
SELECT 
    'INVESTMENTS' as table_name,
    COUNT(*) as count
FROM investments;

-- Mostra dettagli utenti
SELECT 
    id,
    email,
    full_name,
    role,
    kyc_status,
    referral_code,
    created_at
FROM users
ORDER BY id;

-- Mostra dettagli progetti
SELECT 
    id,
    code,
    title,
    status,
    target_amount,
    raised_amount,
    (raised_amount / target_amount * 100)::numeric(5,2) as completion_percentage
FROM projects
ORDER BY id;

-- Mostra dettagli investimenti
SELECT 
    i.id,
    u.email,
    p.code as project_code,
    i.amount,
    i.status,
    i.expected_yield_pct
FROM investments i
JOIN users u ON i.user_id = u.id
JOIN projects p ON i.project_id = p.id
ORDER BY i.id;

-- =====================================================
-- MESSAGGIO DI COMPLETAMENTO
-- =====================================================

DO $$
BEGIN
    RAISE NOTICE '🎉 DATI DI TEST RICREATI CON SUCCESSO!';
    RAISE NOTICE '🔑 Password per tutti gli utenti: test123';
    RAISE NOTICE '📧 Admin: admin@cipimmobiliare.it';
    RAISE NOTICE '📧 Test: test@cipimmobiliare.it';
    RAISE NOTICE '📧 Demo: demo@cipimmobiliare.it';
    RAISE NOTICE '📧 Referral: referral@cipimmobiliare.it';
END $$;
