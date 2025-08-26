# 🚀 Guida Mobile-First per CIP Immobiliare

## 📱 Principi Base

### Mobile-First Approach
- **Inizia sempre dal mobile**: Progetta prima per smartphone, poi espandi per tablet/desktop
- **Progressive Enhancement**: Aggiungi funzionalità e spazio man mano che lo schermo si allarga
- **Touch-Friendly**: Tutti gli elementi interattivi devono essere almeno 44x44px

## 🎯 Breakpoint Tailwind

```css
/* Mobile First - Base (default) */
/* 0px - 639px: Smartphone */
/* Layout: 1 colonna, icone piccole, font compatti */

/* sm: 640px+ - Tablet verticale */
/* Layout: 2 colonne KPI, sidebar nascosta ma accessibile */

/* md: 768px+ - Tablet orizzontale/Desktop piccolo */
/* Layout: 2 colonne KPI, sidebar visibile */

/* lg: 1024px+ - Desktop */
/* Layout: 3 colonne KPI, sidebar fissa, layout completo */
```

## 🧩 Componenti Responsive

### Icone
```html
<!-- Header Icons -->
<div class="icon-wrap icon-header bg-indigo-50 text-indigo-600">
  <svg aria-hidden="true"></svg>
</div>

<!-- KPI Icons -->
<div class="icon-wrap icon-kpi bg-blue-100 text-blue-600">
  <svg aria-hidden="true"></svg>
</div>

<!-- Navigation Icons -->
<div class="icon-wrap icon-nav bg-gray-100 text-gray-600">
  <svg aria-hidden="true"></svg>
</div>
```

### KPI Grid
```html
<!-- Mobile: 1 colonna, Tablet: 2 colonne, Desktop: 3 colonne -->
<div class="kpi-grid">
  <!-- KPI cards -->
</div>
```

### Sidebar
```html
<!-- Sidebar mobile-first -->
<aside id="sidebar" class="sidebar-mobile sidebar-desktop">
  <!-- Contenuto sidebar -->
</aside>

<!-- Overlay per mobile -->
<div id="sidebar-overlay" class="sidebar-overlay hidden"></div>

<!-- Toggle button -->
<button onclick="toggleSidebar()" class="hamburger-menu desktop-hidden">
  <svg class="hamburger-icon">...</svg>
</button>
```

## 📏 Typography Responsive

```css
/* Titoli Card */
.card-title {
  @apply text-lg font-semibold;         /* mobile: 18px */
}
@screen md {
  .card-title { @apply text-xl; }      /* desktop: 20px */
}

/* Titoli Header */
.header-title {
  @apply text-xl font-bold;             /* mobile: 20px */
}
@screen md {
  .header-title { @apply text-2xl; }   /* desktop: 24px */
}

/* Descrizioni */
.text-desc {
  @apply text-sm;                       /* mobile: 14px */
}
@screen md {
  .text-desc { @apply text-base; }     /* desktop: 16px */
}
```

## 🎨 Spacing Responsive

```css
/* Card Padding */
.card-padding {
  @apply p-4;                           /* mobile: 16px */
}
@screen md {
  .card-padding { @apply p-6; }        /* desktop: 24px */
}

/* Section Spacing */
.section-spacing {
  @apply py-4;                          /* mobile: 16px */
}
@screen md {
  .section-spacing { @apply py-6; }    /* desktop: 24px */
}

/* Safe Mobile Margins */
.safe-mobile {
  @apply mx-4;                          /* mobile: 16px */
}
@screen md {
  .safe-mobile { @apply mx-6; }        /* desktop: 24px */
}
```

## 🔧 Utility Classes

```css
/* Touch-friendly buttons */
.touch-friendly {
  @apply min-h-[44px] min-w-[44px];    /* iOS/Android touch target */
}

/* Mobile shadows */
.shadow-mobile {
  @apply shadow-sm;                     /* mobile: ombra leggera */
}
@screen md {
  .shadow-mobile { @apply shadow-md; } /* desktop: ombra media */
}

/* Transitions */
.transition-mobile {
  @apply transition-all duration-300 ease-in-out;
}

/* Responsive visibility */
.mobile-hidden { @apply hidden md:block; }    /* Nascondi su mobile */
.desktop-hidden { @apply block md:hidden; }   /* Nascondi su desktop */
```

## 📱 Layout Patterns

### 1. KPI Cards
```html
{% from 'components/kpi-card.html' import kpi_grid, kpi_card %}
{{ kpi_grid() }}
  {{ kpi_card(
    title="Investito",
    value="€1,000",
    icon='<svg>...</svg>',
    color="blue"
  ) }}
{% endcall %}
```

### 2. Content Layout
```html
<!-- Main content con sidebar offset su desktop -->
<main class="pt-20 pb-20 content-mobile">
  {% block content %}{% endblock %}
</main>
```

### 3. Navigation Mobile
```html
<!-- Bottom navigation solo su mobile -->
<nav class="fixed bottom-0 left-0 right-0 bg-white border-t z-50 md:hidden">
  <!-- Navigation items -->
</nav>
```

## 🚀 Come Creare Nuovi Componenti

### 1. Inizia dal Mobile
```html
<!-- Base mobile -->
<div class="bg-white p-4 rounded-lg border">
  <h3 class="text-lg font-semibold">Titolo</h3>
  <p class="text-sm text-gray-600">Descrizione</p>
</div>
```

### 2. Aggiungi Responsive
```html
<!-- Mobile + responsive -->
<div class="bg-white card-padding rounded-lg border shadow-mobile">
  <h3 class="card-title">Titolo</h3>
  <p class="text-desc text-gray-600">Descrizione</p>
</div>
```

### 3. Usa Grid Responsive
```html
<!-- Grid mobile-first -->
<div class="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
  <!-- Items -->
</div>
```

## ✅ Checklist Mobile-First

- [ ] **Icone**: Usa classi `icon-header`, `icon-kpi`, `icon-nav`
- [ ] **Layout**: Inizia con 1 colonna, espandi con `sm:`, `md:`, `lg:`
- [ ] **Typography**: Usa `card-title`, `header-title`, `text-desc`
- [ ] **Spacing**: Usa `card-padding`, `section-spacing`, `safe-mobile`
- [ ] **Touch**: Aggiungi `touch-friendly` ai bottoni
- [ ] **Shadows**: Usa `shadow-mobile` per ombre responsive
- [ ] **Transitions**: Usa `transition-mobile` per animazioni fluide

## 🔍 Testing

### 1. Mobile (360px)
- Sidebar nascosta ma accessibile
- KPI 1 colonna
- Icone piccole (header: 40px, KPI: 32px)
- Font compatti

### 2. Tablet (768px)
- Sidebar visibile
- KPI 2 colonne
- Icone medie (header: 44px, KPI: 36px)

### 3. Desktop (1024px+)
- Sidebar fissa
- KPI 3 colonne
- Icone grandi (header: 48px, KPI: 40px)
- Layout completo

## 📚 File di Riferimento

- `frontend/static/css/mobile-optimizations.css` - CSS mobile-first
- `frontend/templates/components/kpi-card.html` - Componente KPI riutilizzabile
- `frontend/templates/layouts/base.html` - Layout base responsive
- `frontend/templates/includes/header.html` - Header mobile-first
- `frontend/templates/includes/sidebar.html` - Sidebar responsive

---

**Ricorda**: Mobile-first significa pensare prima agli utenti mobile, poi espandere per schermi più grandi. È più facile aggiungere spazio che toglierlo! 🎯
