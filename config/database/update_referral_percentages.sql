-- Script per aggiornare le percentuali di referral da 1% a 3% e implementare bonus VIP 5%
-- Data: $(date)
-- Descrizione: Aggiorna le funzioni SQL per riflettere le nuove percentuali di referral

-- =====================================================
-- AGGIORNAMENTO FUNZIONI REFERRAL
-- =====================================================

-- Aggiorna la funzione per calcolare commissione referral (1% -> 3%)
CREATE OR REPLACE FUNCTION calculate_referral_commission(investment_amount NUMERIC)
RETURNS NUMERIC AS $$
BEGIN
    RETURN investment_amount * 0.03; -- 3% (era 1%)
END;
$$ LANGUAGE plpgsql;

-- Aggiorna la funzione per calcolare commissione referral (versione DECIMAL)
CREATE OR REPLACE FUNCTION calculate_referral_commission(investment_amount DECIMAL)
RETURNS DECIMAL AS $$
BEGIN
    RETURN investment_amount * 0.03; -- 3% (era 1%)
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- AGGIORNAMENTO COMMENTI TABELLE
-- =====================================================

-- Aggiorna commenti per riflettere le nuove percentuali
COMMENT ON TABLE referrals IS 'Sistema referral con commissioni 3% (5% per VIP)';
COMMENT ON COLUMN referral_commissions.commission_amount IS '3% dell''investimento (5% per VIP)';
COMMENT ON COLUMN user_portfolios.referral_bonus IS '3% del profitto per chi ha invitato (5% per VIP)';

-- =====================================================
-- VERIFICA AGGIORNAMENTI
-- =====================================================

-- Test della funzione aggiornata
SELECT 'Test funzione aggiornata:' as test_name, calculate_referral_commission(1000) as commission_1000_eur;

-- Verifica che la funzione restituisca 30.00 per 1000€ (3%)
-- Risultato atteso: 30.00
