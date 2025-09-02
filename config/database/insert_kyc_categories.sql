-- Inserisci categorie KYC se non esistono
INSERT INTO doc_categories (name, slug, description, is_kyc, is_required) VALUES
('Carta d''Identità', 'id_card', 'Documento di identità italiano (fronte e retro)', TRUE, TRUE),
('Patente di Guida', 'drivers_license', 'Patente di guida italiana (fronte e retro)', TRUE, FALSE),
('Passaporto', 'passport', 'Passaporto italiano (pagina principale)', TRUE, FALSE)
ON CONFLICT (slug) DO NOTHING;



