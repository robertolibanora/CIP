# Guida Configurazione SSL - CIP Immobiliare

## Situazione Attuale

✅ **Server funzionante**: Il tuo server è configurato correttamente e funziona su:
- HTTP: `http://31.97.47.158` (redirect a HTTPS)
- HTTPS: `https://31.97.47.158` (certificato self-signed)
- Health check: `https://31.97.47.158/health` ✅

✅ **Certificato SSL**: Certificato self-signed migliorato installato e funzionante

⚠️ **Problema identificato**: Il dominio `ciprealestate.eu` punta a due IP:
- `82.25.113.16` (proxy LiteSpeed del provider)
- `31.97.47.158` (il tuo server)

Le richieste vanno al proxy invece che al tuo server.

## Soluzioni

### Opzione 1: Disabilitare Proxy nel Pannello di Controllo (RACCOMANDATO)

1. **Accedi al pannello di controllo del tuo provider** (Hostinger)
2. **Vai alla sezione Domini/DNS**
3. **Trova il dominio `ciprealestate.eu`**
4. **Disabilita il proxy/LiteSpeed** per questo dominio
5. **Configura il DNS** per puntare direttamente a `31.97.47.158`

### Opzione 2: Configurare DNS A Record

Se hai accesso al DNS del dominio:
```
A    ciprealestate.eu       31.97.47.158
A    www.ciprealestate.eu   31.97.47.158
```

### Opzione 3: Usare un Sottodominio

Crea un sottodominio che punta direttamente al tuo server:
```
A    app.ciprealestate.eu   31.97.47.158
```

## Una Volta Risolto il DNS

Esegui questo comando per ottenere un certificato Let's Encrypt valido:

```bash
ssh root@31.97.47.158 "cd /var/www/CIP && bash deploy/setup_ssl.sh"
```

## Test Attuali

### ✅ Funzionanti
- `https://31.97.47.158/health` - Health check
- `https://31.97.47.158/` - Homepage (403 è normale se non configurata)

### ❌ Non funzionanti (per il proxy)
- `https://ciprealestate.eu` - Bloccato dal proxy LiteSpeed
- `http://ciprealestate.eu` - Bloccato dal proxy LiteSpeed

## File di Configurazione

- **Nginx**: `/etc/nginx/sites-available/CIP`
- **Certificato SSL**: `/etc/ssl/cip_immobiliare/`
- **Script SSL**: `deploy/setup_ssl.sh`
- **Servizio**: `cip-immobiliare.service`

## Comandi Utili

```bash
# Verifica stato servizi
systemctl status cip-immobiliare
systemctl status nginx

# Test locale
curl -k https://31.97.47.158/health

# Logs
journalctl -u cip-immobiliare -f
tail -f /var/log/nginx/cip_immobiliare_error.log

# Riavvia servizi
systemctl restart cip-immobiliare
systemctl restart nginx
```

## Prossimi Passi

1. **Risolvi il problema del proxy** (Opzione 1 raccomandata)
2. **Esegui lo script SSL** per ottenere certificato Let's Encrypt
3. **Testa il dominio** per verificare che funzioni
4. **Configura la homepage** dell'applicazione

Il tuo server è pronto e funzionante! Il problema è solo nel routing del DNS.
