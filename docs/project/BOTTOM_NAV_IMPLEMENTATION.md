# 🚀 Bottom Navigation Bar - Implementazione Instagram-Style

## 📱 Caratteristiche

La bottom navigation bar è stata implementata seguendo il design pattern di Instagram con le seguenti caratteristiche:

### ✨ Funzionalità
- **Mobile-first**: Visibile solo su dispositivi mobili (≤767px)
- **5 tab principali**: Home, Search, New (+), Reels, Profile
- **Safe-area iOS**: Rispetta `env(safe-area-inset-bottom)` per dispositivi con notch
- **Accessibilità**: Aria-label e ruoli semantici
- **Nessun badge**: Nessuna notifica rossa o punto di attenzione
- **Spaziatore**: Previene sovrapposizione con i contenuti della pagina

### 🎨 Design
- **Backdrop blur**: Sfondo semi-trasparente con effetto blur
- **Dark mode support**: Classi `dark:` per tema scuro
- **Icone SVG**: 24x24px con stroke-width 1.8
- **Animazioni**: Scale-down al touch (`active:scale-95`)
- **Bordi arrotondati**: `rounded-xl` per tab, `rounded-2xl` per il pulsante +

## 🏗️ Struttura File

```
frontend/
├── templates/
│   ├── partials/
│   │   └── bottom_nav.html          # Template della navbar
│   └── layouts/
│       └── base.html                # Include la navbar
└── static/css/
    └── output.css                   # Classi CSS personalizzate
```

## 🎯 Utilizzo

### 1. Template Base
La navbar è automaticamente inclusa in `base.html`:

```html
<!-- Spaziatore per evitare che la tabbar copra i contenuti -->
<div class="tabbar-spacer"></div>
{% include 'partials/bottom_nav.html' %}
```

### 2. Endpoint Detection
La navbar rileva automaticamente l'endpoint corrente per evidenziare il tab attivo:

```jinja2
{% set ep = request.endpoint or '' %}
class="tabbar-item {{ 'tabbar-item--active' if ep in ['user.dashboard'] else '' }}"
```

### 3. User Authentication
Gestisce automaticamente utenti autenticati e non:

```jinja2
{% if current_user and getattr(current_user, 'avatar_url', None) %}
  <img src="{{ current_user.avatar_url }}" alt="" class="h-6 w-6 rounded-full">
{% else %}
  <!-- SVG fallback -->
{% endif %}
```

## 🎨 Classi CSS

### Tabbar Container
```css
.tabbar {
  @apply fixed bottom-0 inset-x-0 z-50 md:hidden
         bg-white/95 dark:bg-neutral-900/90 backdrop-blur
         border-t border-neutral-200 dark:border-neutral-800
         px-4 pt-2
         pb-[calc(10px+env(safe-area-inset-bottom))];
}
```

### Tab Items
```css
.tabbar-item {
  @apply h-12 w-12 flex items-center justify-center rounded-xl
         transition-transform active:scale-95 select-none;
}

.tabbar-item--active svg, .tabbar-item--active img { 
  @apply opacity-100; 
}
```

### Spaziatore
```css
.tabbar-spacer { 
  @apply h-16 md:hidden; 
}
```

## 🔧 Personalizzazione

### 1. Modificare gli Endpoint
Aggiorna gli `url_for()` nel file `bottom_nav.html`:

```jinja2
<!-- Esempio per endpoint personalizzati -->
<a href="{{ url_for('custom.search') }}" class="tabbar-item">
```

### 2. Aggiungere Nuove Tab
Aggiungi nuove tab seguendo il pattern esistente:

```html
<!-- Nuova Tab -->
<a href="{{ url_for('custom.new_feature') }}" 
   class="tabbar-item {{ 'tabbar-item--active' if ep.startswith('custom.new_feature') else '' }}"
   aria-label="Nuova Funzionalità">
  <svg>...</svg>
</a>
```

### 3. Modificare le Icone
Sostituisci gli SVG con icone personalizzate:

```html
<!-- Icona personalizzata -->
<img src="{{ url_for('static', filename='icons/custom-icon.svg') }}" 
     alt="" class="h-6 w-6">
```

## 🧪 Testing

### Test Mobile
1. Apri la pagina su dispositivo mobile o dev tools mobile
2. Verifica che la navbar sia visibile in basso
3. Controlla che le icone siano 24x24px
4. Verifica il safe-area su dispositivi iOS

### Test Desktop
1. Apri la pagina su desktop (≥768px)
2. Verifica che la navbar sia nascosta
3. Controlla che lo spaziatore sia rimosso

### Test Funzionalità
1. Naviga tra le diverse pagine
2. Verifica che il tab attivo sia evidenziato
3. Controlla che i link puntino agli endpoint corretti

## 🐛 Troubleshooting

### Navbar Non Visibile
- Verifica che il CSS sia caricato correttamente
- Controlla che la viewport sia mobile (≤767px)
- Verifica che non ci siano conflitti CSS

### Icone Non Allineate
- Controlla che le classi `h-6 w-6` siano applicate
- Verifica che non ci siano override CSS
- Controlla la struttura HTML delle icone

### Safe-Area Non Funziona
- Verifica che il dispositivo supporti safe-area
- Controlla che il CSS sia compilato correttamente
- Testa su dispositivo iOS fisico

## 📱 Responsive Behavior

| Breakpoint | Comportamento |
|------------|---------------|
| `< 768px`  | Navbar visibile, spaziatore attivo |
| `≥ 768px`  | Navbar nascosta, spaziatore rimosso |

## 🔒 Sicurezza

- Nessun endpoint hardcoded
- Controlli di autenticazione per avatar
- Escape automatico dei dati utente
- Nessuna esposizione di informazioni sensibili

## 🚀 Performance

- CSS ottimizzato con Tailwind
- SVG inline per ridurre richieste HTTP
- Lazy loading per avatar utente
- Transizioni hardware-accelerated
