-- Script per inserire utenti di test nel database
-- Esegui questo script dopo aver creato le tabelle

-- Inserisci utente admin di test
INSERT INTO users (
    email, 
    password_hash, 
    nome, 
    cognome, 
    nome_telegram, 
    telefono, 
    role, 
    referral_code, 
    created_at
) VALUES (
    'marktrapella06@gmail.com',
    'admin123',  -- Password in chiaro per test (in produzione usare hash)
    'Admin',
    'Test',
    '@admin_test',
    '+39 123 456 7890',
    'admin',
    'ADMIN001',
    NOW()
) ON CONFLICT (email) DO NOTHING;

-- Inserisci alcuni utenti di test normali
INSERT INTO users (
    email, 
    password_hash, 
    nome, 
    cognome, 
    nome_telegram, 
    telefono, 
    role, 
    referral_code, 
    created_at
) VALUES 
    ('test1@example.com', 'password123', 'Mario', 'Rossi', '@mariorossi', '+39 111 111 1111', 'investor', 'TEST001', NOW()),
    ('test2@example.com', 'password123', 'Giulia', 'Bianchi', '@giuliabianchi', '+39 222 222 2222', 'investor', 'TEST002', NOW()),
    ('test3@example.com', 'password123', 'Luca', 'Verdi', '@lucaverdi', '+39 333 333 3333', 'investor', 'TEST003', NOW())
ON CONFLICT (email) DO NOTHING;

-- Verifica inserimento
SELECT id, email, nome, cognome, role, created_at FROM users ORDER BY created_at;
