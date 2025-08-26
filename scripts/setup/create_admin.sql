-- Script per creare l'utente admin CIP Immobiliare
-- Esegui: psql -d cip -f create_admin.sql

-- Inserisci utente admin
INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, created_at, updated_at)
VALUES (
    'admin@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Admin',
    'CIP',
    'admin',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    updated_at = NOW();

-- Inserisci utente di test
INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, created_at, updated_at)
VALUES (
    'test@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Test',
    'User',
    'user',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    updated_at = NOW();

-- Inserisci utente demo
INSERT INTO users (email, password_hash, first_name, last_name, role, is_active, created_at, updated_at)
VALUES (
    'demo@cipimmobiliare.it',
    'scrypt:32768:8:1$wsyRutMWPrLE2dm4$be5991e5e38feb005964643f4e076f45f5d3647963b26d97f277f0d4655d8ae4c6282daff5b0e4ceff11bb2cf026f846a8d175c8c46f1aaa4b195a1118563ea1',
    'Demo',
    'User',
    'user',
    true,
    NOW(),
    NOW()
) ON CONFLICT (email) DO UPDATE SET
    password_hash = EXCLUDED.password_hash,
    updated_at = NOW();

-- Verifica inserimento
SELECT email, first_name, last_name, role, is_active FROM users WHERE email IN (
    'admin@cipimmobiliare.it',
    'test@cipimmobiliare.it',
    'demo@cipimmobiliare.it'
);
