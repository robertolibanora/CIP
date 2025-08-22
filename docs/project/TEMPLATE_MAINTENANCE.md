# 🎯 MANUTENZIONE TEMPLATE E STATIC FILES

## 📁 Struttura Corretta dei Percorsi

### 1. App Factory (src/admin/admin.py)
```python
app = Flask(__name__, 
           static_folder=os.path.join(os.getcwd(), 'static'),
           template_folder=os.path.join(os.getcwd(), 'assets', 'templates'))
```

**IMPORTANTE:** Mantieni sempre questa configurazione:
- `static_folder`: punta a `./static` (cartella root)
- `template_folder`: punta a `./assets/templates` (cartella root)

### 2. Blueprint (NON specificare template_folder)
```python
# ✅ CORRETTO - Usa percorsi relativi alla root
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# ❌ SBAGLIATO - Non specificare template_folder
auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="auth")
```

### 3. Percorsi Template nei Blueprint
```python
# ✅ CORRETTO - Percorso relativo alla root template_folder
@auth_bp.route("/login")
def login():
    return render_template("auth/login.html")  # assets/templates/auth/login.html

# ❌ SBAGLIATO - Percorso assoluto
return render_template("/auth/login.html")
```

## 🔧 Verifica Configurazione

### Script di Diagnostica
```bash
# Attiva ambiente virtuale
source venv/bin/activate

# Esegui diagnostica
python scripts/test/test_template_debug.py
```

**Output atteso:**
- Template folder: `./assets/templates`
- Static folder: `./static`
- Template disponibili: `auth/login.html`, `auth/base_auth.html`, etc.

### Test cURL
```bash
# Test rendering template
./scripts/test/test_curl.sh

# Test manuale
curl -s http://127.0.0.1:8080/auth/login | head -n 30
```

## 🚨 Problemi Comuni e Soluzioni

### 1. Template non trovato
**Sintomi:** Errore 500, "Template not found"
**Cause:** Percorso template errato o template_folder non allineato
**Soluzione:** Verifica che il template sia in `assets/templates/` e usa percorsi relativi

### 2. CSS non caricato
**Sintomi:** Pagina senza stili, solo HTML grezzo
**Cause:** Static folder non configurato correttamente
**Soluzione:** Verifica `static_folder="./static"` nell'app factory

### 3. Blueprint non registrato
**Sintomi:** Route 404, blueprint non visibili
**Cause:** Blueprint non registrato in main.py
**Soluzione:** Verifica `app.register_blueprint(auth_bp)` in main.py

## 📋 Checklist Manutenzione

### Prima di ogni deploy:
- [ ] Verifica `template_folder` punta a `./assets/templates`
- [ ] Verifica `static_folder` punta a `./static`
- [ ] Esegui script diagnostica: `python scripts/test/test_template_debug.py`
- [ ] Test cURL: `./scripts/test/test_curl.sh`
- [ ] Verifica che tutti i template usino percorsi relativi

### Quando aggiungi nuovi template:
- [ ] Posiziona in `assets/templates/[blueprint_name]/`
- [ ] Usa `render_template("[blueprint_name]/template.html")`
- [ ] Estendi template base con `{% extends "base.html" %}` o `{% extends "[blueprint_name]/base.html" %}`

### Quando aggiungi nuovi static files:
- [ ] Posiziona in `static/[category]/`
- [ ] Usa `url_for('static', filename='[category]/file.ext')`

## 🎯 Best Practices

1. **UNA SOLA ROOT:** Mantieni sempre una sola root per template e static
2. **PERCORSI RELATIVI:** Usa sempre percorsi relativi nei blueprint
3. **NON DUPLICARE:** Non specificare `template_folder` nei blueprint
4. **TEST AUTOMATICI:** Usa sempre gli script di diagnostica
5. **DOCUMENTAZIONE:** Aggiorna questo file quando cambi la struttura

## 🔍 Debug Rapido

```python
# In Python shell o script
from main import app
print("Template folder:", app.template_folder)
print("Static folder:", app.static_folder)
print("Templates:", list(app.jinja_env.list_templates())[:10])
print("Blueprints:", list(app.blueprints.keys()))
```

## 📞 Supporto

Se incontri problemi:
1. Esegui `python scripts/test/test_template_debug.py`
2. Controlla i log del server Flask
3. Verifica la struttura delle cartelle
4. Controlla questo documento per le best practices
