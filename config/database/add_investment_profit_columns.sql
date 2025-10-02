-- Aggiunge le colonne per tracciare i profitti degli investimenti
-- quando un progetto viene venduto

-- Aggiungi le colonne se non esistono
ALTER TABLE investments 
ADD COLUMN IF NOT EXISTS profit_earned NUMERIC(15,2) DEFAULT 0.00;

ALTER TABLE investments 
ADD COLUMN IF NOT EXISTS total_return NUMERIC(15,2) DEFAULT 0.00;

ALTER TABLE investments 
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ DEFAULT NULL;

-- Aggiungi commenti alle colonne
COMMENT ON COLUMN investments.profit_earned IS 'Profitto guadagnato da questo investimento';
COMMENT ON COLUMN investments.total_return IS 'Ritorno totale (investimento + profitto)';
COMMENT ON COLUMN investments.completed_at IS 'Data e ora di completamento dell''investimento';

-- Aggiungi constraint per assicurarsi che i valori siano positivi
ALTER TABLE investments 
ADD CONSTRAINT investments_profit_earned_check 
CHECK (profit_earned >= 0);

ALTER TABLE investments 
ADD CONSTRAINT investments_total_return_check 
CHECK (total_return >= 0);

-- Aggiungi indice per performance
CREATE INDEX IF NOT EXISTS idx_investments_completed_at ON investments(completed_at);
CREATE INDEX IF NOT EXISTS idx_investments_profit_earned ON investments(profit_earned) WHERE profit_earned > 0;
