-- Aggiunge la colonna sold_at alla tabella projects
-- per tracciare quando un progetto è stato venduto

-- Aggiungi la colonna sold_at se non esiste
ALTER TABLE projects 
ADD COLUMN IF NOT EXISTS sold_at TIMESTAMPTZ DEFAULT NULL;

-- Aggiungi commento alla colonna
COMMENT ON COLUMN projects.sold_at IS 'Data e ora di vendita del progetto';

-- Aggiorna il constraint di status per includere 'sold'
ALTER TABLE projects 
DROP CONSTRAINT IF EXISTS projects_status_check;

ALTER TABLE projects 
ADD CONSTRAINT projects_status_check 
CHECK (status IN ('draft','funding','active','completed','cancelled','sold'));

-- Aggiungi indice per performance
CREATE INDEX IF NOT EXISTS idx_projects_sold_at ON projects(sold_at);
CREATE INDEX IF NOT EXISTS idx_projects_status_sold ON projects(status) WHERE status = 'sold';
