# Credenziali di Test

Questo documento contiene le credenziali per gli utenti di test dell'applicazione C.I.P.

## Utenti Disponibili

### Utenti Investor
- **Email**: `test.user1@example.com`
- **Password**: `test123`
- **Ruolo**: `investor`

- **Email**: `test.user2@example.com`
- **Password**: `test123`
- **Ruolo**: `investor`

- **Email**: `test.investor@example.com`
- **Password**: `test123`
- **Ruolo**: `investor`

### Utente Admin
- **Email**: `test.admin@example.com`
- **Password**: `admin123`
- **Ruolo**: `admin`

## Come Aggiornare le Password

Se hai bisogno di aggiornare le password hash degli utenti di test, usa lo script:

```bash
cd scripts/setup
python3 update_test_users.py
```

**Nota**: Assicurati di avere le variabili d'ambiente caricate e l'ambiente virtuale attivato.

## Risoluzione Problemi

### Errore di Login
Se incontri errori di login:

1. Verifica che il database sia in esecuzione
2. Controlla che le variabili d'ambiente siano caricate
3. Verifica che le password hash siano aggiornate nel database
4. Controlla i log dell'applicazione per errori specifici

### Aggiornamento Password Hash
Le password hash vengono generate usando `werkzeug.security.generate_password_hash()` e verificate con `werkzeug.security.check_password_hash()`.
