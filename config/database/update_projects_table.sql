-- Script di aggiornamento per la tabella projects
-- Aggiunge i campi necessari per i progetti immobiliari

-- Aggiungi nuovi campi se non esistono
DO $$ 
BEGIN
    -- Aggiungi campo address se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'address') THEN
        ALTER TABLE projects ADD COLUMN address TEXT;
    END IF;
    
    -- Aggiungi campo min_investment se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'min_investment') THEN
        ALTER TABLE projects ADD COLUMN min_investment NUMERIC(14,2) DEFAULT 1000;
    END IF;
    
    -- Aggiungi campo photo_filename se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'photo_filename') THEN
        ALTER TABLE projects ADD COLUMN photo_filename TEXT;
    END IF;
    
    -- Aggiungi campo documents_filename se non esiste
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'documents_filename') THEN
        ALTER TABLE projects ADD COLUMN documents_filename TEXT;
    END IF;
    
    -- Rinomina title in name se esiste title ma non name
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'title') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'name') THEN
        ALTER TABLE projects RENAME COLUMN title TO name;
    END IF;
    
    -- Rinomina target_amount in total_amount se esiste target_amount ma non total_amount
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'target_amount') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'total_amount') THEN
        ALTER TABLE projects RENAME COLUMN target_amount TO total_amount;
    END IF;
    
    -- Rinomina raised_amount in funded_amount se esiste raised_amount ma non funded_amount
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'raised_amount') 
       AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'projects' AND column_name = 'funded_amount') THEN
        ALTER TABLE projects RENAME COLUMN raised_amount TO funded_amount;
    END IF;
    
END $$;

-- Crea indice su address se non esiste
CREATE INDEX IF NOT EXISTS idx_projects_address ON projects(address);

-- Aggiorna i valori esistenti se necessario
UPDATE projects SET 
    min_investment = COALESCE(min_investment, 1000),
    address = COALESCE(address, 'Indirizzo non specificato')
WHERE min_investment IS NULL OR address IS NULL;

-- Verifica la struttura finale
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'projects' 
ORDER BY ordinal_position;
