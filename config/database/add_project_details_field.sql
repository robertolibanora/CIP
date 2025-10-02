-- Aggiunge campo per informazioni dettagliate del progetto
-- Questo campo conterrà le informazioni aggiuntive che l'admin può modificare

-- Aggiungi il campo project_details alla tabella projects se non esiste
DO $$ 
BEGIN
    -- Verifica se la colonna esiste già
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'projects' 
        AND column_name = 'project_details'
        AND table_schema = 'public'
    ) THEN
        -- Aggiungi la colonna
        ALTER TABLE projects 
        ADD COLUMN project_details TEXT;
        
        -- Aggiungi un commento per documentare il campo
        COMMENT ON COLUMN projects.project_details IS 'Informazioni dettagliate del progetto modificabili dall admin';
    END IF;
END $$;

-- Verifica che la colonna gallery esista e sia di tipo JSONB
DO $$
BEGIN
    -- Se la colonna gallery non esiste, creala
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'projects' 
        AND column_name = 'gallery'
        AND table_schema = 'public'
    ) THEN
        ALTER TABLE projects 
        ADD COLUMN gallery JSONB;
    END IF;
    
    -- Se esiste ma non è JSONB, convertila
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'projects' 
        AND column_name = 'gallery'
        AND data_type != 'jsonb'
        AND table_schema = 'public'
    ) THEN
        -- Converti in JSONB se non lo è già
        ALTER TABLE projects 
        ALTER COLUMN gallery TYPE JSONB USING gallery::JSONB;
    END IF;
END $$;

-- Crea un indice per migliorare le performance delle query sulla galleria
CREATE INDEX IF NOT EXISTS idx_projects_gallery ON projects USING GIN (gallery);

-- Aggiorna i progetti esistenti per inizializzare la galleria se vuota
UPDATE projects 
SET gallery = '[]'::jsonb 
WHERE gallery IS NULL;

-- Aggiungi un trigger per aggiornare updated_at quando project_details cambia
CREATE OR REPLACE FUNCTION update_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crea il trigger se non esiste
DROP TRIGGER IF EXISTS trigger_update_projects_updated_at ON projects;
CREATE TRIGGER trigger_update_projects_updated_at
    BEFORE UPDATE ON projects
    FOR EACH ROW
    EXECUTE FUNCTION update_projects_updated_at();
