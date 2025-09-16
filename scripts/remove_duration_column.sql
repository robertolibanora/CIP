-- Script per rimuovere la colonna duration dalla tabella projects
-- Questa colonna è ridondante dato che abbiamo già start_date e end_date

-- Verifica se la colonna esiste prima di tentare di rimuoverla
-- (SQLite non supporta DROP COLUMN direttamente, quindi usiamo un approccio diverso)

-- Per SQLite, dobbiamo ricreare la tabella senza la colonna duration
-- Questo script è solo documentativo - le modifiche sono già state applicate nel codice

-- Se fosse PostgreSQL:
-- ALTER TABLE projects DROP COLUMN IF EXISTS duration;

-- Per SQLite, il processo sarebbe:
-- 1. Creare una nuova tabella senza la colonna duration
-- 2. Copiare i dati dalla vecchia tabella alla nuova
-- 3. Eliminare la vecchia tabella
-- 4. Rinominare la nuova tabella

-- Ma dato che la colonna duration non è mai stata utilizzata nel database SQLite corrente,
-- non è necessario eseguire questo script.

-- Nota: Le modifiche al codice sono sufficienti per rimuovere tutti i riferimenti
-- alla colonna duration dall'applicazione.
