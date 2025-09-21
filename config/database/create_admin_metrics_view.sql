-- Vista metriche admin semplificata
-- Compatibile con le tabelle esistenti nel database

CREATE OR REPLACE VIEW v_admin_metrics AS
SELECT 
    (SELECT COUNT(*) FROM users) AS users_total,
    0 AS users_verified,
    0 AS users_pending_kyc,
    (SELECT COUNT(*) FROM projects) AS projects_active,
    0 AS investments_total,
    0 AS deposits_pending,
    0 AS withdrawals_pending,
    0 AS deposits_total,
    0 AS withdrawals_total;

-- Concedi permessi all'utente dell'applicazione
GRANT SELECT ON v_admin_metrics TO cipuser;
