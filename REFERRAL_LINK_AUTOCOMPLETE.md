# Funzionalità Link Referral con Precompilazione Automatica

## 📋 Descrizione

È stata implementata la funzionalità per cui quando un utente clicca su un link referral, il campo "Codice Referral" nella pagina di registrazione si compila automaticamente con il codice dell'utente che ha condiviso il link.

## 🔗 Formato Link Referral

I link referral ora funzionano nel seguente formato:
```
http://127.0.0.1:12345/auth/register?ref=CODICE_REFERRAL
```

Dove `CODICE_REFERRAL` è il codice univoco dell'utente che ha condiviso il link.

## 🔧 Implementazione Tecnica

### Backend (`backend/auth/routes.py`)

1. **Gestione parametro URL**: La route `/register` ora legge il parametro `ref` dall'URL
2. **Precompilazione campo**: Il codice referral viene passato al template
3. **Fallback intelligente**: Se l'utente non inserisce un codice nel form, viene usato quello dall'URL

```python
@auth_bp.route("/register", methods=["GET", "POST"])
@guest_only
def register():
    # Gestisci parametro referral dall'URL
    referral_code_from_url = request.args.get('ref', '').strip()
    
    if request.method == "POST":
        # Usa il codice dal form o dall'URL come fallback
        referral_link = request.form.get("referral_link") or referral_code_from_url
        # ... resto della logica
```

### Frontend (`frontend/templates/auth/register.html`)

1. **Precompilazione server-side**: Il campo viene precompilato con il valore dal server
2. **Precompilazione client-side**: JavaScript aggiuntivo per gestire casi edge
3. **Validazione automatica**: Il codice viene validato automaticamente quando precompilato

```html
<!-- Campo precompilato dal server -->
<input
  type="text"
  name="referral_link"
  id="referral_link"
  value="{{ referral_code_from_url or '' }}"
  placeholder="Inserisci il codice referral"
/>
```

```javascript
// Precompilazione client-side per casi edge
const urlParams = new URLSearchParams(window.location.search);
const refFromUrl = urlParams.get('ref');
if (refFromUrl && !referralInput.value.trim()) {
  referralInput.value = refFromUrl;
  validateReferral(refFromUrl);
}
```

## 🎯 Funzionalità

### Per l'Utente che Condivide
1. Copia il link referral dalla dashboard
2. Condivide il link (es. `http://127.0.0.1:12345/auth/register?ref=REF000123`)
3. Il destinatario vedrà il campo precompilato automaticamente

### Per l'Utente che si Registra
1. Clicca sul link referral ricevuto
2. Vede il campo "Codice Referral" già compilato
3. Può modificare il codice se necessario
4. La validazione avviene automaticamente

## ✅ Vantaggi

1. **User Experience migliorata**: L'utente non deve copiare/incollare manualmente il codice
2. **Riduzione errori**: Meno possibilità di errori di digitazione
3. **Conversione maggiore**: Più facile per gli utenti completare la registrazione
4. **Retrocompatibilità**: Funziona anche senza il parametro URL

## 🔄 Flusso Completo

1. **Utente A** (referrer) copia il suo link referral
2. **Utente A** condivide il link con **Utente B**
3. **Utente B** clicca sul link
4. **Utente B** arriva su `/auth/register?ref=CODICE_A`
5. Il campo referral è già compilato con `CODICE_A`
6. **Utente B** completa la registrazione
7. **Utente A** riceve il bonus referral

## 🧪 Test

Per testare la funzionalità:

1. **Test con link valido**:
   - Vai su `http://127.0.0.1:12345/auth/register?ref=REF000001`
   - Verifica che il campo sia precompilato
   - Verifica che la validazione mostri "Codice valido"

2. **Test con link non valido**:
   - Vai su `http://127.0.0.1:12345/auth/register?ref=INVALID`
   - Verifica che il campo sia precompilato
   - Verifica che la validazione mostri "Codice referral non valido"

3. **Test senza parametro**:
   - Vai su `http://127.0.0.1:12345/auth/register`
   - Verifica che il campo sia vuoto
   - Verifica che funzioni la registrazione normale

## 📝 Note Tecniche

- La validazione avviene in tempo reale via API
- Il sistema è robusto e gestisce casi edge
- Non ci sono modifiche al database
- La funzionalità è completamente retrocompatibile
