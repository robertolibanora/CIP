# 🏠 CIP Immobiliare - Piattaforma di Investimenti Immobiliari

## 📱 **App Mobile-First con Bottom Navigation**

CIP Immobiliare è un'applicazione web moderna e responsive per investimenti immobiliari, progettata con un approccio mobile-first e una bottom navigation bar ispirata alle migliori app mobile.

### ✨ **Caratteristiche Principali**

- **Design Mobile-First**: Ottimizzato per dispositivi mobili con layout responsive
- **Bottom Navigation**: Barra di navigazione inferiore visibile solo su mobile (md:hidden)
- **Tailwind CSS**: Styling moderno e consistente
- **Flask Backend**: API robuste e sicure
- **PostgreSQL**: Database performante per gestione investimenti

## 🔧 **Installazione e Setup**

### **Prerequisiti**
- Python 3.8+
- PostgreSQL 12+
- Node.js 16+ (per Tailwind CSS)

### **Installazione**

```bash
# Clona il repository
git clone <repository-url>
cd C.I.P.

# Installa dipendenze
pip install -r requirements.txt

# Configura database
# (vedi config/database/ per schema)

# Avvia l'applicazione
python main.py
```

## 🧭 **Bottom Navigation - Configurazione**

### **Struttura Tab**
La bottom navigation include 5 tab principali:

1. **Dashboard** (`user.dashboard`) - Home principale
2. **Search** (`user.search`) - Ricerca progetti
3. **New** (`user.new_project`) - Nuovo investimento
4. **Portfolio** (`user.portfolio`) - Gestione investimenti
5. **Profile** (`user.profile`) - Profilo utente

### **Configurazione current_page**

Per attivare correttamente le tab, ogni route deve passare la variabile `current_page`:

```python
# In backend/user/routes.py
@user_bp.get("/dashboard")
def dashboard():
    return render_template("user/dashboard.html", 
                         user=user_data,
                         current_page="dashboard"  # ← Attiva tab Dashboard
                         )

@user_bp.get("/search")
def search():
    return render_template("user/search.html", 
                         projects=projects,
                         current_page="search"     # ← Attiva tab Search
                         )

@user_bp.get("/new-project")
def new_project():
    return render_template("user/new_project.html", 
                         projects=projects,
                         current_page="new_project" # ← Attiva tab New
                         )

@user_bp.get("/portfolio")
def portfolio():
    return render_template("user/portfolio.html", 
                         investments=rows,
                         current_page="portfolio"   # ← Attiva tab Portfolio
                         )

@user_bp.get("/profile")
def profile():
    return render_template("user/profile.html", 
                         user=user_data,
                         current_page="profile"     # ← Attiva tab Profile
                         )
```

### **Valori current_page Supportati**
- `"dashboard"` - Attiva tab Dashboard
- `"search"` - Attiva tab Search  
- `"new_project"` - Attiva tab New
- `"portfolio"` - Attiva tab Portfolio
- `"profile"` - Attiva tab Profile

### **Template Requirements**
Ogni template deve:
1. **Estendere `layouts/base.html`**
2. **Avere `<main class="pt-16 pb-24">`** per lo spacing corretto
3. **Ricevere `current_page`** dalla route

```html
<!-- Template esempio -->
{% extends "layouts/base.html" %}

{% block content %}
<div class="min-h-screen bg-white">
    <!-- Contenuto della pagina -->
    <!-- La bottom nav è automaticamente inclusa da base.html -->
</div>
{% endblock %}
```

## 🎨 **Design System**

### **Colori Brand**
- **Primary**: Blue-600 (#2563eb)
- **Secondary**: Gray-600 (#4b5563)
- **Accent**: Green-600 (#16a34a)

### **Componenti**
- **Tabbar**: `.tabbar`, `.tabbar-item`, `.tabbar-item--active`
- **Spacing**: `.tabbar-spacer` per evitare sovrapposizioni
- **Responsive**: `md:hidden` per nascondere su desktop

## 🚀 **Deployment**

```bash
# Script di deployment
./deploy.sh

# O manualmente
python main.py --host 0.0.0.0 --port 8090
```

## 📱 **Mobile-First Features**

- **Safe Area Support**: `env(safe-area-inset-bottom)` per iOS
- **Touch Optimized**: Target touch minimo 44px
- **Responsive Breakpoints**: Mobile-first con `md:` prefix
- **Performance**: CSS ottimizzato per dispositivi mobili

## 🔍 **Troubleshooting**

### **Tab non attiva?**
1. Verifica che la route passi `current_page`
2. Controlla che il template estenda `base.html`
3. Verifica che `request.endpoint` corrisponda al valore atteso

### **Bottom nav non visibile?**
1. Controlla che `partials/bottom_nav.html` sia incluso in `base.html`
2. Verifica che il CSS sia caricato correttamente
3. Testa su dispositivo mobile o con viewport mobile

### **Layout sovrapposto?**
1. Assicurati che il `<main>` abbia `pb-24`
2. Verifica che `.tabbar-spacer` sia presente
3. Controlla che non ci siano CSS conflittuali

## 📚 **Documentazione Aggiuntiva**

- [API Documentation](docs/api/API_DOCS.md)
- [Deployment Guide](docs/deployment/)
- [Project Structure](docs/project/README.md)

---

**CIP Immobiliare** - Investimenti immobiliari semplificati 🏗️✨
