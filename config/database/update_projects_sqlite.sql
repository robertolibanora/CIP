-- Aggiornamento schema progetti per SQLite - supportare stato "venduto" e campi di vendita

-- 1. Aggiungi i nuovi campi per gestire le vendite
ALTER TABLE projects ADD COLUMN sale_price REAL DEFAULT NULL;
ALTER TABLE projects ADD COLUMN sale_date DATE DEFAULT NULL;
ALTER TABLE projects ADD COLUMN profit_percentage REAL DEFAULT NULL;
ALTER TABLE projects ADD COLUMN sold_by_admin_id INTEGER DEFAULT NULL;

-- 2. Crea indice per performance su status
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- 3. Crea indice per performance su sale_date
CREATE INDEX IF NOT EXISTS idx_projects_sale_date ON projects(sale_date);

-- 4. Aggiorna alcuni progetti di esempio per testare la funzionalità
-- (Questo è opzionale e può essere rimosso in produzione)

-- Esempio: aggiorna un progetto esistente a "completato" se non ce ne sono
UPDATE projects 
SET status = 'completed' 
WHERE status = 'active' 
AND id = (SELECT id FROM projects WHERE status = 'active' LIMIT 1);

-- Esempio: aggiorna un progetto esistente a "venduto" se non ce ne sono
UPDATE projects 
SET status = 'sold',
    sale_price = total_amount * 1.15, -- 15% di profitto
    sale_date = DATE('now', '-30 days'),
    sold_by_admin_id = 1
WHERE status = 'completed' 
AND id = (SELECT id FROM projects WHERE status = 'completed' LIMIT 1);
