# C.I.P. Immobiliare - App Portfolio Investimenti

## 🎯 **Progetto Semplificato per Mobile-First**

**C.I.P. Immobiliare** è un'applicazione web per la gestione di portafogli di investimenti immobiliari, ottimizzata per dispositivi mobili.

## ✨ **Caratteristiche Principali**

### **5 Sezioni Utente Principali**
1. **📊 Dashboard** - Vista generale del portfolio e statistiche
2. **💼 Portfolio** - Dettaglio investimenti e rendimenti  
3. **🏗️ Progetti** - Lista e dettagli dei progetti disponibili
4. **🔗 Referral** - Sistema di referral e bonus
5. **👤 Profilo** - Gestione account utente

### **🎨 Design Mobile-First**
- **Responsive design** ottimizzato per mobile
- **Navigation bar** fissa in basso per mobile
- **Touch interactions** ottimizzate (44px+ targets)
- **CSS mobile** specifico per performance

## 🚀 **Tecnologie Utilizzate**

- **Backend**: Flask (Python)
- **Frontend**: HTML5 + Tailwind CSS
- **Database**: PostgreSQL
- **Template Engine**: Jinja2
- **Architettura**: MVC con Blueprint

## 📁 **Struttura Progetto**

```
C.I.P./
├── backend/                 # Logica backend Flask
│   ├── user/               # Rotte utente
│   ├── admin/              # Rotte admin
│   ├── auth/               # Autenticazione
│   ├── portfolio/          # API portfolio
│   └── shared/             # Moduli condivisi
├── frontend/               # Template e assets
│   ├── templates/          # Template Jinja2
│   │   ├── user/          # Template utente (5 sezioni)
│   │   ├── includes/      # Componenti riutilizzabili
│   │   └── layouts/       # Layout base
│   └── assets/            # CSS, JS, immagini
├── config/                 # Configurazione
├── docs/                   # Documentazione
└── main.py                 # Entry point Flask
```

## 🔧 **Installazione e Setup**

### **Prerequisiti**
- Python 3.8+
- PostgreSQL 12+
- pip

### **Installazione**
```bash
# Clone repository
git clone <repository-url>
cd C.I.P.

# Installa dipendenze
pip install -r requirements.txt

# Configura database
cp config/env/.env.example config/env/.env
# Modifica .env con credenziali database

# Esegui migrazioni
python scripts/setup/setup.sh

# Avvia applicazione
python main.py
```

## 📱 **Design Mobile-First**

### **Breakpoints**
- **Mobile**: ≤ 768px (default)
- **Tablet**: 768px - 1024px
- **Desktop**: ≥ 1024px

### **Caratteristiche Mobile**
- **Touch targets** minimi 44px
- **Font size** minimo 16px (previene zoom iOS)
- **Navigation bar** fissa in basso
- **Scroll ottimizzato** per touch
- **Meta viewport** ottimizzato

## 🧪 **Testing**

### **Test Coerenza**
```bash
python3 test_routes_coherence.py
```

### **Test Database e HTTP**
```bash
python3 test_database_http.py
```

### **Test Finale Completo**
```bash
python3 test_finale_completo.py
```

## 🚀 **Deployment**

### **Produzione**
```bash
# Build CSS
npm run build:css:prod

# Avvia con Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 main:app
```

### **Docker**
```bash
docker-compose up -d
```

## 📚 **API Endpoints**

### **Utente (Autenticato)**
- `GET /user/dashboard` - Dashboard principale
- `GET /user/portfolio` - Portfolio investimenti
- `GET /user/projects` - Lista progetti
- `GET /user/referral` - Dashboard referral
- `GET /user/profile` - Profilo utente

### **Portfolio API**
- `GET /portfolio/overview` - Overview portfolio
- `GET /portfolio/investments` - Lista investimenti
- `GET /portfolio/referral/overview` - Statistiche referral

## 🔒 **Sicurezza**

- **Autenticazione** richiesta per rotte utente
- **Decoratori** `@login_required` e `@admin_required`
- **Session management** sicuro
- **Input validation** su tutti i form

## 📊 **Database Schema**

### **Tabelle Principali**
- `users` - Utenti e referral
- `projects` - Progetti immobiliari
- `investments` - Investimenti utenti
- `investment_yields` - Rendimenti investimenti
- `referral_bonuses` - Bonus referral

## 🎨 **Customizzazione**

### **CSS Personalizzato**
- **Colori brand**: Variabili CSS personalizzabili
- **Componenti**: Card, bottoni, form ottimizzati
- **Utilities**: Classi helper per mobile

### **Template**
- **Layout base** con navigation mobile
- **Componenti** riutilizzabili
- **Responsive** per tutti i dispositivi

## 🤝 **Contribuire**

1. Fork del repository
2. Crea branch per feature (`git checkout -b feature/nuova-feature`)
3. Commit delle modifiche (`git commit -am 'Aggiunge nuova feature'`)
4. Push del branch (`git push origin feature/nuova-feature`)
5. Crea Pull Request

## 📄 **Licenza**

Questo progetto è sotto licenza MIT. Vedi `LICENSE` per dettagli.

## 📞 **Supporto**

Per supporto e domande:
- **Email**: support@cipimmobiliare.com
- **Documentazione**: `/docs` directory
- **Issues**: GitHub Issues

---

**C.I.P. Immobiliare** - Investimenti immobiliari semplificati 📱✨
