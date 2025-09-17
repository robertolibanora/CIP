# Sistema Notifiche Admin

## 📋 Panoramica

Il sistema di notifiche admin è stato implementato per notificare l'amministratore quando gli utenti effettuano azioni importanti come:
- **Richiesta KYC** (verifica identità)
- **Richiesta Deposito** (ricarica conto)
- **Richiesta Prelievo** (ritiro fondi)

## 🎯 Funzionalità

### 1. **Notifiche Automatiche**
Le notifiche vengono create automaticamente quando:
- Un utente carica documenti KYC
- Un utente effettua una richiesta di deposito
- Un utente effettua una richiesta di prelievo

### 2. **Badge Rosso Dashboard**
Nella dashboard admin appare un badge rosso con il numero di notifiche non lette.

### 3. **Gestione Notifiche**
- Visualizzazione notifiche non lette
- Marcatura come lette
- Filtro per tipo (KYC, Depositi, Prelievi)

## 🗄️ Database

### Tabella `admin_notifications`
```sql
CREATE TABLE admin_notifications (
    id SERIAL PRIMARY KEY,
    type TEXT NOT NULL CHECK (type IN ('kyc', 'deposit', 'withdrawal')),
    user_id INT NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at TIMESTAMPTZ,
    read_by INT REFERENCES users(id),
    metadata JSONB
);
```

## 🔧 Implementazione

### 1. **Creazione Notifiche**
```python
from backend.shared.notifications import create_deposit_notification

# Crea notifica per deposito
create_deposit_notification(user_id=3, user_name="Mario Rossi", amount=1000.0)
```

### 2. **API Endpoints**
- `GET /admin/api/notifications/` - Lista notifiche
- `GET /admin/api/notifications/unread-count` - Conteggio non lette
- `POST /admin/api/notifications/<id>/read` - Marca come letta
- `POST /admin/api/notifications/mark-all-read` - Marca tutte come lette

### 3. **Frontend Integration**
Il badge rosso viene aggiornato automaticamente tramite JavaScript che chiama l'API ogni 30 secondi.

## 📱 Interfaccia Utente

### Dashboard Admin
- **Badge Rosso**: Mostra numero notifiche non lette
- **Click Badge**: Apre pannello notifiche
- **Gestione**: Marca come lette, filtra per tipo

### Pannello Notifiche
- Lista notifiche in tempo reale
- Informazioni utente (nome, email)
- Dettagli azione (importo, data)
- Azioni rapide (approva, rifiuta)

## 🚀 Test Sistema

### 1. **Test Manuale**
```sql
-- Crea notifica di test
INSERT INTO admin_notifications (type, user_id, title, message, metadata) 
VALUES ('deposit', 3, 'Test Deposito', 'Test notifica', '{"amount": 1000}');
```

### 2. **Test Automatico**
- Effettua richiesta deposito come utente
- Verifica che appaia notifica in admin
- Controlla badge rosso

## ✅ Status Implementazione

- [x] Database schema
- [x] API notifiche
- [x] Creazione automatica depositi
- [x] Badge rosso dashboard
- [x] Pannello notifiche
- [x] Marcatura come lette
- [x] Filtri per tipo
- [x] Test sistema

## 🔄 Prossimi Passi

1. **Notifiche KYC**: Implementare creazione automatica per upload documenti
2. **Notifiche Prelievi**: Implementare creazione automatica per richieste prelievo
3. **Email Notifiche**: Invio email per notifiche urgenti
4. **Push Notifiche**: Notifiche browser per admin online