-- Aggiornamento schema progetti per supportare stato "venduto" e campi di vendita
-- Questo script aggiunge il nuovo stato e i campi necessari per gestire le vendite

-- 1. Aggiungi il nuovo stato "sold" alla tabella projects
ALTER TABLE projects 
DROP CONSTRAINT IF EXISTS projects_status_check;

ALTER TABLE projects 
ADD CONSTRAINT projects_status_check 
CHECK (status IN ('draft','funding','active','completed','cancelled','sold'));

-- 2. Aggiungi campi per gestire le vendite
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS sale_price NUMERIC(15,2) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS sale_date DATE DEFAULT NULL,
ADD COLUMN IF NOT EXISTS profit_percentage NUMERIC(6,3) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS sold_by_admin_id INTEGER DEFAULT NULL;

-- 3. Aggiungi commenti per chiarezza
COMMENT ON COLUMN projects.sale_price IS 'Prezzo di vendita finale dell\'immobile';
COMMENT ON COLUMN projects.sale_date IS 'Data di vendita dell\'immobile';
COMMENT ON COLUMN projects.profit_percentage IS 'Percentuale di profitto calcolata sulla vendita';
COMMENT ON COLUMN projects.sold_by_admin_id IS 'ID dell\'admin che ha registrato la vendita';

-- 4. Crea indice per performance su status
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- 5. Crea indice per performance su sale_date
CREATE INDEX IF NOT EXISTS idx_projects_sale_date ON projects(sale_date);

-- 6. Funzione per calcolare automaticamente la percentuale di profitto
CREATE OR REPLACE FUNCTION calculate_profit_percentage()
RETURNS TRIGGER AS $$
BEGIN
    -- Calcola la percentuale di profitto solo se abbiamo sia sale_price che total_amount
    IF NEW.sale_price IS NOT NULL AND NEW.total_amount IS NOT NULL AND NEW.total_amount > 0 THEN
        NEW.profit_percentage = ROUND(((NEW.sale_price - NEW.total_amount) / NEW.total_amount * 100)::NUMERIC, 3);
    ELSE
        NEW.profit_percentage = NULL;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 7. Trigger per calcolare automaticamente la percentuale di profitto
DROP TRIGGER IF EXISTS trigger_calculate_profit_percentage ON projects;
CREATE TRIGGER trigger_calculate_profit_percentage
    BEFORE INSERT OR UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION calculate_profit_percentage();

-- 8. Aggiorna alcuni progetti di esempio per testare la funzionalità
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
    sale_date = CURRENT_DATE - INTERVAL '30 days',
    sold_by_admin_id = 1
WHERE status = 'completed' 
AND id = (SELECT id FROM projects WHERE status = 'completed' LIMIT 1);
