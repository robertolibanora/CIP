# 📊 Dashboard Transazioni Admin

## Panoramica

La dashboard transazioni admin fornisce una vista completa e in tempo reale di tutte le attività finanziarie della piattaforma CIP Immobiliare.

## Funzionalità Principali

### 📈 Report Finanziari
- **Depositi Totali**: Somma di tutti i depositi completati
- **Prelievi Totali**: Somma di tutti i prelievi completati  
- **Guadagni da Vendite**: Profitti generati dalle vendite di immobili
- **Capitale Totale**: Somma di tutti i portafogli utenti

### 📊 Grafici Interattivi
- **Capitale Disponibile**: Grafico a linee degli ultimi 12 mesi
- **Profitti Annuali**: Grafico a barre dei profitti per anno
- **Distribuzione Investimenti**: Grafico a torta della distribuzione del capitale

### 🔍 Dettagli Transazioni
- **Vista Dettagliata**: Informazioni complete per ogni transazione
- **Transazioni Correlate**: Transazioni dello stesso utente nello stesso giorno
- **Bilanci**: Confronto prima/dopo la transazione
- **Portfolio Utente**: Stato attuale del portfolio

## Struttura Database

### Tabelle Utilizzate
- `portfolio_transactions`: Transazioni principali
- `deposit_requests`: Richieste di deposito
- `withdrawal_requests`: Richieste di prelievo
- `user_portfolios`: Portafogli utenti
- `project_sales`: Vendite progetti

### Tipi di Transazioni
- `deposit`: Depositi
- `withdrawal`: Prelievi
- `investment`: Investimenti
- `roi`: Rendimenti
- `referral`: Bonus referral

## API Endpoints

### GET /admin/transactions
Dashboard principale con tutti i report e grafici.

### GET /admin/transactions/{id}
Dettaglio di una transazione specifica.

### GET /admin/api/transactions/data
API per dati in tempo reale:
- `?type=capital`: Dati capitale disponibile
- `?type=profits`: Dati profitti annuali
- `?type=distribution`: Distribuzione investimenti

## Grafici e Visualizzazioni

### 1. Grafico Capitale Disponibile
- **Tipo**: Linea
- **Periodo**: Ultimi 12 mesi
- **Dati**: Transazioni mensili totali
- **Aggiornamento**: Ogni 30 secondi

### 2. Grafico Profitti Annuali
- **Tipo**: Barre
- **Periodo**: Ultimi 5 anni
- **Dati**: Profitti per anno
- **Colore**: Verde (#10b981)

### 3. Grafico Distribuzione Investimenti
- **Tipo**: Torta
- **Dati**: Percentuali di distribuzione
- **Categorie**:
  - Immobili Dubai: 10%
  - Portafogli Utenti: 80%
  - Casa Milano: 10%

## Metriche Disponibili

### Statistiche Depositi
- Totale depositi completati
- Importo totale depositato
- Numero di depositi in sospeso

### Statistiche Prelievi
- Totale prelievi completati
- Importo totale prelevato
- Numero di prelievi in sospeso

### Statistiche Portfolio
- Transazioni totali
- Importo totale movimentato
- Breakdown per tipo di transazione

### Statistiche Vendite
- Numero totale di vendite
- Importo totale vendite
- Profitti totali generati

## Design e UX

### Colori e Stili
- **Metriche Principali**: Gradienti colorati
- **Transazioni**: Codifica colore per tipo
- **Grafici**: Palette coerente
- **Responsive**: Ottimizzato per mobile

### Animazioni
- **Hover Effects**: Effetti di transizione
- **Loading States**: Skeleton loading
- **Chart Animations**: Fade-in progressivo

## Sicurezza

### Autorizzazioni
- Solo utenti admin possono accedere
- Decorator `@admin_required` su tutte le route
- Logging di tutte le azioni admin

### Dati Sensibili
- Nessun dato sensibile esposto
- Email utenti mascherate se necessario
- Logging delle query per audit

## Performance

### Ottimizzazioni
- Query ottimizzate con indici
- Caching dei dati grafici
- Paginazione per transazioni recenti
- Aggiornamento asincrono

### Monitoraggio
- Logging degli errori
- Metriche di performance
- Alert per query lente

## Manutenzione

### Aggiornamenti Dati
- Aggiornamento automatico ogni 30 secondi
- Refresh manuale disponibile
- Cache invalidation intelligente

### Backup e Recovery
- Backup automatico dei dati
- Point-in-time recovery
- Export dati per analisi

## Troubleshooting

### Problemi Comuni
1. **Grafici non si caricano**: Verificare connessione CDN Chart.js
2. **Dati non aggiornati**: Controllare connessione database
3. **Errori di autorizzazione**: Verificare ruolo admin utente

### Log e Debug
- Log completi in `app.log`
- Debug mode per sviluppo
- Error tracking integrato

## Roadmap Future

### Funzionalità Pianificate
- [ ] Export dati in Excel/PDF
- [ ] Filtri avanzati per transazioni
- [ ] Notifiche real-time
- [ ] Dashboard personalizzabile
- [ ] Report automatici via email
- [ ] Integrazione con sistemi contabili

### Miglioramenti Tecnici
- [ ] Caching Redis
- [ ] WebSocket per aggiornamenti real-time
- [ ] API GraphQL
- [ ] Microservizi per analytics
