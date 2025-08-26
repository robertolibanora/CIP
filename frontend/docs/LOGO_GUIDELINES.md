# 🏢 Logo CIP Immobiliare - Linee Guida

## Panoramica

Il logo di CIP Immobiliare rappresenta la nostra identità visiva e simboleggia la crescita, la stabilità e l'innovazione nel settore immobiliare. È composto da tre edifici stilizzati che rappresentano diversità, progresso e solidità.

## Design del Logo

### Elementi Principali
- **Sfondo**: Quadrato blu (#1e40af) con bordi arrotondati
- **Edifici**: Tre strutture architettoniche stilizzate in bianco
- **Finestre**: Dettagli che aggiungono profondità e realismo
- **Linee di base**: Fondamenta che simboleggiano stabilità

### Significato Simbolico
- **Edificio sinistro**: Rappresenta la tradizione e la solidità
- **Edificio centrale**: Simboleggia la crescita e il progresso
- **Edificio destro**: Incarna l'innovazione e il design moderno

## Varianti del Logo

### 1. Logo Standard (Default)
- Sfondo blu (#1e40af)
- Edifici bianchi
- Utilizzo: Header principale, documenti ufficiali

### 2. Logo Invertito (Inverted)
- Sfondo bianco
- Edifici blu (#1e40af)
- Utilizzo: Sfondi scuri, contrasti elevati

### 3. Logo Minimalista (Minimal)
- Solo contorni degli edifici
- Colore ereditato dal contesto (currentColor)
- Utilizzo: Icone, elementi decorativi

## Utilizzo del Componente

### Importazione
```html
{% from 'components/logo.html' import logo, logo_with_text %}
```

### Logo Base
```html
<!-- Logo standard 32x32 -->
{{ logo(size='32', variant='default') }}

<!-- Logo invertito 48x48 -->
{{ logo(size='48', variant='inverted') }}

<!-- Logo minimalista 24x24 -->
{{ logo(size='24', variant='minimal') }}
```

### Logo con Testo
```html
<!-- Logo con testo brand -->
{{ logo_with_text(size='32', variant='default', show_text=true) }}

<!-- Solo logo senza testo -->
{{ logo_with_text(size='40', variant='inverted', show_text=false) }}
```

## Classi CSS Disponibili

### Effetti Base
- `.cip-logo` - Logo con transizioni base
- `.cip-logo-glow` - Effetto glow blu
- `.cip-logo-pulse` - Pulsazione sottile

### Effetti Avanzati
- `.cip-logo-3d` - Rotazione 3D al hover
- `.cip-logo-glass` - Effetto glassmorphism
- `.cip-logo-gradient` - Gradiente animato
- `.cip-logo-neon` - Effetto neon

### Effetti Interattivi
- `.cip-logo-magnetic` - Effetto magnetico
- `.cip-logo-spotlight` - Effetto spotlight
- `.cip-logo-particle` - Particelle decorative

## Dimensioni Raccomandate

### Header e Navigation
- **Mobile**: 24x24px
- **Tablet**: 32x32px
- **Desktop**: 40x40px

### Documenti e Materiali
- **Stampa**: 48x48px
- **Presentazioni**: 64x64px
- **Grandi formati**: 96x96px

### Favicon e Icone
- **Favicon**: 32x32px
- **App icon**: 180x180px
- **Touch icon**: 152x152px

## Spazio di Respirazione

Il logo deve sempre avere uno spazio di respirazione minimo pari alla metà dell'altezza dell'edificio centrale:

- **Logo 32x32**: Spazio minimo 8px
- **Logo 48x48**: Spazio minimo 12px
- **Logo 64x64**: Spazio minimo 16px

## Colori del Brand

### Colori Principali
- **Blu principale**: #1e40af
- **Blu chiaro**: #3b82f6
- **Blu scuro**: #1e3a8a

### Colori di Supporto
- **Bianco**: #ffffff
- **Grigio chiaro**: #f8fafc
- **Grigio scuro**: #1f2937

## Utilizzo Responsive

### Breakpoint Mobile (< 640px)
```html
{{ logo(size='24', variant='default', class='cip-logo-mobile') }}
```

### Breakpoint Tablet (641px - 1024px)
```html
{{ logo(size='32', variant='default', class='cip-logo-tablet') }}
```

### Breakpoint Desktop (> 1024px)
```html
{{ logo(size='40', variant='default', class='cip-logo-desktop') }}
```

## Esempi di Implementazione

### Header Principale
```html
<div class="flex items-center space-x-3">
    {{ logo(size='32', variant='inverted', class='cip-logo cip-logo-glow') }}
    <div>
        <h1 class="text-xl font-bold text-gray-900">CIP Immobiliare</h1>
        <p class="text-sm text-gray-600">Investment Platform</p>
    </div>
</div>
```

### Footer
```html
<div class="flex items-center space-x-2">
    {{ logo(size='24', variant='minimal', class='cip-logo cip-logo-magnetic') }}
    <span class="text-sm text-gray-600">© 2024 CIP Immobiliare</span>
</div>
```

### Card Promozionale
```html
<div class="text-center p-6">
    {{ logo(size='48', variant='default', class='cip-logo cip-logo-pulse mx-auto mb-4') }}
    <h3 class="text-lg font-bold">Scopri i Nostri Progetti</h3>
</div>
```

## Best Practices

### ✅ Cosa Fare
- Mantenere sempre le proporzioni originali
- Utilizzare le varianti appropriate per il contesto
- Rispettare lo spazio di respirazione
- Applicare effetti CSS per migliorare l'interattività

### ❌ Cosa Non Fare
- Deformare o allungare il logo
- Cambiare i colori del brand
- Ridurre eccessivamente le dimensioni
- Posizionare troppo vicino ad altri elementi

## File Disponibili

- `logo.svg` - Logo standard 48x48
- `logo-large.svg` - Logo grande 64x64 con dettagli
- `favicon.svg` - Favicon 32x32
- `components/logo.html` - Componente riutilizzabile
- `css/logo.css` - Stili e animazioni

## Supporto Tecnico

Per domande o problemi relativi al logo, contattare il team di design o consultare la documentazione CSS per gli effetti disponibili.
