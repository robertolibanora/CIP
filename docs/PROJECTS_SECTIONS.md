# Sezioni Progetti - Documentazione

## Panoramica

Il sistema di gestione progetti è stato aggiornato per supportare tre sezioni distinte che riflettono il ciclo di vita di un progetto immobiliare:

1. **Attivi** - Progetti in corso dove gli utenti possono investire
2. **Completati** - Progetti finiti ma non ancora venduti (non si può più investire)
3. **Venduti** - Progetti venduti con informazioni sui profitti

## Stati dei Progetti

### 1. Attivi (`active`)
- **Descrizione**: Progetti in corso di finanziamento
- **Investimenti**: ✅ Possibili (solo se KYC verificato)
- **Caratteristiche**:
  - Barra di progresso del finanziamento
  - Pulsante "Investi Ora" attivo
  - ROI atteso visibile
  - Investimento minimo richiesto

### 2. Completati (`completed`)
- **Descrizione**: Progetti completamente finanziati, in attesa di vendita
- **Investimenti**: ❌ Non possibili
- **Caratteristiche**:
  - Messaggio "In attesa di vendita"
  - Pulsante "Investimento Chiuso" disabilitato
  - Totale investito mostrato
  - Stato giallo per indicare attesa

### 3. Venduti (`sold`)
- **Descrizione**: Progetti venduti con profitti calcolati
- **Investimenti**: ❌ Non possibili
- **Caratteristiche**:
  - Prezzo di vendita mostrato
  - Percentuale di profitto calcolata
  - Data di vendita
  - Profitto totale in euro
  - Stato verde per indicare successo

## Modifiche al Database

### Nuove Colonne nella Tabella `projects`

```sql
-- Prezzo di vendita finale
sale_price REAL DEFAULT NULL

-- Data di vendita
sale_date DATE DEFAULT NULL

-- Percentuale di profitto calcolata automaticamente
profit_percentage REAL DEFAULT NULL

-- ID dell'admin che ha registrato la vendita
sold_by_admin_id INTEGER DEFAULT NULL

-- Importo finanziato (per calcolare il progresso)
funded_amount REAL DEFAULT 0.0
```

### Indici per Performance

```sql
-- Indice per filtrare per stato
CREATE INDEX idx_projects_status ON projects(status);

-- Indice per ordinare per data di vendita
CREATE INDEX idx_projects_sale_date ON projects(sale_date);
```

## Modifiche al Backend

### Route Aggiornate

Il file `backend/user/projects.py` è stato aggiornato per:

1. **Query separate** per ogni sezione:
   - `active_projects`: `WHERE status = 'active'`
   - `completed_projects`: `WHERE status = 'completed'`
   - `sold_projects`: `WHERE status = 'sold'`

2. **Elaborazione dati**:
   - Calcolo percentuale completamento
   - Calcolo profitti per progetti venduti
   - Gestione campi mancanti per compatibilità

### Modelli Aggiornati

Il file `backend/shared/models.py` include:

1. **Nuovo stato**: `ProjectStatus.SOLD = "sold"`
2. **Nuovi campi** nel modello `Project`:
   - `sale_price: Optional[Decimal]`
   - `sale_date: Optional[datetime]`
   - `profit_percentage: Optional[Decimal]`
   - `sold_by_admin_id: Optional[int]`

3. **Nuovi metodi**:
   - `can_invest()`: Verifica se si può investire
   - `is_completed()`: Verifica se è completato
   - `is_sold()`: Verifica se è venduto
   - `get_profit_info()`: Restituisce info profitti

## Modifiche al Frontend

### Template Aggiornato

Il file `frontend/templates/user/projects.html` include:

1. **Navigazione a tab**:
   - Tab "Attivi" (con contatore)
   - Tab "Completati" (con contatore)
   - Tab "Venduti" (con contatore)

2. **Sezioni separate**:
   - `#section-active`: Progetti attivi
   - `#section-completed`: Progetti completati
   - `#section-sold`: Progetti venduti

3. **JavaScript per navigazione**:
   - Funzione `showSection(sectionName)`
   - Gestione stati attivi dei tab
   - Nascondere/mostrare sezioni

### Stili Differenziati

- **Attivi**: Colori blu/verde per indicare disponibilità
- **Completati**: Colori gialli per indicare attesa
- **Venduti**: Colori verdi per indicare successo

## Logica di Investimento

### Controlli di Sicurezza

1. **Stato KYC**: Solo utenti verificati possono investire
2. **Stato Progetto**: Solo progetti `active` accettano investimenti
3. **Pulsanti Disabilitati**: Progetti `completed` e `sold` mostrano pulsanti disabilitati

### Messaggi Utente

- **KYC Non Verificato**: "KYC Richiesto"
- **Progetto Completato**: "Investimento Chiuso"
- **Progetto Venduto**: "Investimento Chiuso"

## Esempi di Utilizzo

### Per Utenti

1. **Visualizzare progetti attivi**: Cliccare su tab "Attivi"
2. **Investire**: Solo su progetti attivi con KYC verificato
3. **Monitorare completati**: Tab "Completati" per progetti in attesa
4. **Vedere profitti**: Tab "Venduti" per progetti venduti

### Per Amministratori

1. **Aggiornare stato progetto**:
   ```sql
   UPDATE projects SET status = 'completed' WHERE id = ?;
   ```

2. **Registrare vendita**:
   ```sql
   UPDATE projects 
   SET status = 'sold', 
       sale_price = ?, 
       sale_date = ?, 
       profit_percentage = ?,
       sold_by_admin_id = ?
   WHERE id = ?;
   ```

## Test e Validazione

### Dati di Test

Sono stati creati progetti di esempio per testare tutte e tre le sezioni:

- **2 Progetti Attivi**: Con finanziamento parziale
- **1 Progetto Completato**: 100% finanziato, in attesa vendita
- **1 Progetto Venduto**: Con profitto del 15%

### Verifica Funzionalità

1. ✅ Navigazione tra sezioni
2. ✅ Pulsanti investimento disabilitati per completati/venduti
3. ✅ Calcolo profitti per progetti venduti
4. ✅ Contatori progetti per tab
5. ✅ Stili differenziati per stato

## Note Tecniche

### Compatibilità

- **Database**: SQLite (con supporto per PostgreSQL in futuro)
- **Backend**: Flask con psycopg2/sqlite3
- **Frontend**: HTML5 + Tailwind CSS + JavaScript vanilla

### Performance

- Indici creati per query efficienti
- Query separate per evitare JOIN complessi
- Caching lato client per navigazione fluida

### Sicurezza

- Validazione stato progetto lato server
- Controlli KYC obbligatori
- Sanitizzazione input utente
