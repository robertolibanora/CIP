# 📚 Documentazione API CIP Immobiliare

## 🌐 Base URL
```
http://localhost:5000
```

## 🔐 Autenticazione

### Registrazione Utente
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "full_name": "Nome Utente"
}
```

**Risposta:**
```json
{
  "id": 1
}
```

### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}
```

**Risposta:**
```json
{
  "ok": true
}
```

### Verifica Sessione
```http
GET /auth/me
```

**Risposta:**
```json
{
  "user_id": 1,
  "role": "investor"
}
```

### Logout
```http
GET /auth/logout
```

## 👤 Endpoint Utente

### Dashboard
```http
GET /
```

**Risposta:**
```json
{
  "total_invested": 50000.00,
  "active_investments": 3,
  "total_yields": 2500.00,
  "referral_bonus": 500.00
}
```

### Portafoglio
```http
GET /portfolio?tab=attivi
```

**Parametri:**
- `tab`: "attivi" | "completati"

**Risposta:**
```json
{
  "tab": "attivi",
  "items": [
    {
      "id": 1,
      "title": "Residenza Milano",
      "amount": 25000.00,
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### Dettaglio Investimento
```http
GET /portfolio/1
```

**Risposta:**
```json
{
  "investment": {
    "id": 1,
    "amount": 25000.00,
    "status": "active",
    "project_title": "Residenza Milano"
  },
  "yields": [
    {
      "id": 1,
      "amount": 500.00,
      "period_start": "2024-01-01",
      "period_end": "2024-01-31"
    }
  ]
}
```

### Richieste Investimento
```http
GET /requests
```

**Risposta:**
```json
[
  {
    "id": 1,
    "project": "Residenza Milano",
    "amount": 25000.00,
    "state": "in_review",
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

### Nuova Richiesta
```http
POST /requests/new
Content-Type: multipart/form-data

project_id: 1
amount: 25000.00
cro: [file]
```

**Risposta:**
```json
{
  "request_id": 1,
  "state": "in_review"
}
```

### Documenti
```http
GET /documents
```

**Risposta:**
```json
[
  {
    "id": 1,
    "title": "Documento identità",
    "slug": "id_card",
    "name": "Documento identità",
    "uploaded_at": "2024-01-15T10:30:00Z"
  }
]
```

### Upload Documento
```http
POST /documents
Content-Type: multipart/form-data

category_id: 1
title: "Documento identità"
file: [file]
```

**Risposta:**
```json
{
  "id": 1,
  "file_path": "/uploads/uuid-filename.pdf"
}
```

### Categorie Documenti
```http
GET /documents/categories
```

**Risposta:**
```json
[
  {
    "id": 1,
    "slug": "id_card",
    "name": "Documento identità",
    "is_kyc": true
  }
]
```

### Bonus Referral
```http
GET /bonuses
```

**Risposta:**
```json
{
  "items": [
    {
      "id": 1,
      "amount": 500.00,
      "level": 1,
      "month_ref": "2024-01-01"
    }
  ],
  "monthly": [
    {
      "month": "2024-01-01T00:00:00Z",
      "total": 500.00
    }
  ]
}
```

### Rete Referral
```http
GET /network
```

**Risposta:**
```json
[
  {
    "id": 2,
    "referred_by": 1,
    "level": 1
  }
]
```

### Statistiche Rete
```http
GET /network/stats
```

**Risposta:**
```json
[
  {
    "level": 1,
    "count": 5
  }
]
```

### Notifiche
```http
GET /notifications?priority=high&is_read=false
```

**Parametri:**
- `priority`: "low" | "medium" | "high" | "urgent"
- `is_read`: true | false

**Risposta:**
```json
[
  {
    "id": 1,
    "title": "Nuovo investimento approvato",
    "body": "Il tuo investimento è stato approvato",
    "priority": "high",
    "is_read": false,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

### Gestione Notifiche
```http
POST /notifications/bulk
Content-Type: application/json

{
  "ids": [1, 2, 3],
  "action": "mark_read"
}
```

**Azioni:**
- `mark_read`: Segna come lette
- `mark_unread`: Segna come non lette

### Preferenze
```http
GET /preferences
```

**Risposta:**
```json
{
  "full_name": "Nome Utente",
  "email": "user@example.com",
  "phone": "+393331234567",
  "address": "Via Roma 123, Milano",
  "currency_code": "EUR"
}
```

### Aggiorna Preferenze
```http
POST /preferences
Content-Type: application/json

{
  "phone": "+393331234567",
  "address": "Via Roma 123, Milano"
}
```

## 👑 Endpoint Admin

### Dashboard Admin
```http
GET /admin/
```

**Risposta:**
```json
{
  "users_total": 150,
  "projects_active": 8,
  "investments_total": 2500000.00,
  "requests_pending": 12
}
```

### Metriche
```http
GET /admin/metrics
```

### Gestione Progetti

#### Lista Progetti
```http
GET /admin/projects?status=active
```

**Parametri:**
- `status`: "draft" | "active" | "funded" | "in_progress" | "completed" | "cancelled"

#### Nuovo Progetto
```http
POST /admin/projects/new
Content-Type: application/json

{
  "code": "PROJ001",
  "title": "Residenza Milano",
  "description": "Appartamenti di lusso",
  "target_amount": 500000.00,
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

#### Modifica Progetto
```http
POST /admin/projects/1/edit
Content-Type: application/json

{
  "status": "active",
  "target_amount": 600000.00
}
```

### Gestione Utenti

#### Lista Utenti
```http
GET /admin/users?q=email@example.com
```

**Parametri:**
- `q`: Ricerca per email o nome

#### Dettaglio Utente
```http
GET /admin/users/1
```

**Risposta:**
```json
{
  "user": {
    "id": 1,
    "email": "user@example.com",
    "full_name": "Nome Utente",
    "kyc_status": "verified"
  },
  "investments": [...],
  "bonus_total": 500.00,
  "network": [...]
}
```

#### Cambia Referrer
```http
POST /admin/users/1/referrer
Content-Type: application/json

{
  "referred_by": 2
}
```

#### Gestione Bonus
```http
POST /admin/users/1/bonuses
Content-Type: application/json

{
  "amount": 500.00,
  "level": 1,
  "month_ref": "2024-01-01",
  "source_user_id": 2
}
```

### Gestione Investimenti

#### Lista Investimenti
```http
GET /admin/investments?status=active&user_id=1
```

#### Dettaglio Investimento
```http
GET /admin/investments/1
```

#### Conferma Bonifico
```http
POST /admin/investments/1/confirm_wire
```

#### Aggiungi Rendimento
```http
POST /admin/investments/1/yield
Content-Type: application/json

{
  "amount": 500.00,
  "period_start": "2024-01-01",
  "period_end": "2024-01-31"
}
```

### Gestione Richieste

#### Coda Richieste
```http
GET /admin/requests
```

#### Approva Richiesta
```http
POST /admin/requests/1/approve
```

#### Rifiuta Richiesta
```http
POST /admin/requests/1/reject
```

### Gestione KYC

#### Verifica KYC
```http
POST /admin/kyc/1/verify
```

#### Rifiuta KYC
```http
POST /admin/kyc/1/reject
```

### Gestione Documenti

#### Lista Documenti
```http
GET /admin/documents?user_id=1&visibility=private
```

#### Upload Documento
```http
POST /admin/documents/upload
Content-Type: multipart/form-data

user_id: 1
category_id: 1
title: "Documento amministrativo"
file: [file]
visibility: admin
```

#### Cambia Visibilità
```http
POST /admin/documents/1/visibility
Content-Type: application/json

{
  "visibility": "public",
  "verified_by_admin": true
}
```

```

### Analytics

#### Metriche Mensili
```http
GET /admin/analytics
```

**Risposta:**
```json
{
  "investments": [
    {
      "month": "2024-01-01T00:00:00Z",
      "invested": 500000.00
    }
  ],
  "users": [
    {
      "month": "2024-01-01T00:00:00Z",
      "new_users": 25
    }
  ],
  "bonuses": [
    {
      "month": "2024-01-01T00:00:00Z",
      "bonuses": 5000.00
    }
  ]
}
```

## 📁 Gestione File

### Download File
```http
GET /uploads/filename.pdf
```

**Nota:** Richiede autenticazione

## 🏥 Health Check

### Status Applicazione
```http
GET /health
```

**Risposta:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "database": "connected"
}
```

### Metriche Sistema
```http
GET /metrics/system
```

### Metriche Database
```http
GET /metrics/database
```

### Metriche Complete
```http
GET /metrics
```

## 🔒 Codici di Stato HTTP

- `200` - Successo
- `201` - Creato
- `400` - Richiesta non valida
- `401` - Non autorizzato
- `403` - Accesso negato
- `404` - Non trovato
- `500` - Errore interno server

## 📝 Note

1. **Autenticazione**: Tutti gli endpoint (tranne `/auth/*`) richiedono autenticazione
2. **Autorizzazione**: Gli endpoint `/admin/*` richiedono ruolo admin
3. **Formato Date**: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)
4. **Valute**: Supportate: EUR, USD, GBP, CHF
5. **File Upload**: Massimo 16MB, estensioni: PDF, JPG, PNG, DOC, DOCX
6. **Rate Limiting**: Non implementato (da configurare in produzione)
7. **CORS**: Non configurato (da configurare per frontend esterno)
