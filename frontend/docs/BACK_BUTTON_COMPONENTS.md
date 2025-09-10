# Componenti Pulsante "Torna Indietro"

Questo documento descrive i componenti disponibili per il pulsante "Torna indietro" nell'area admin.

## Componenti Disponibili

### 1. Pulsante Standard (incluso in admin_base.html)
Il pulsante è già incluso nell'header di tutte le pagine admin e appare automaticamente.

### 2. back_button.html
Componente base riutilizzabile.

```html
{% include 'admin/components/back_button.html' %}
```

### 3. back_button_compact.html
Versione compatta solo con icona.

```html
{% include 'admin/components/back_button_compact.html' %}
```

### 4. back_button_custom.html
Versione personalizzabile con URL e testo personalizzati.

```html
{% include 'admin/components/back_button_custom.html' with context %}
```

Parametri:
- `back_url` (opzionale): URL specifico per il ritorno
- `back_text` (opzionale): Testo personalizzato per il pulsante

Esempio:
```html
{% set back_url = url_for('admin.projects_list') %}
{% set back_text = 'Torna ai Progetti' %}
{% include 'admin/components/back_button_custom.html' with context %}
```

## Funzioni JavaScript

### goBack()
Torna alla pagina precedente nella cronologia del browser, o alla dashboard admin se non c'è cronologia.

### goBackCustom(customUrl)
Torna a un URL specifico se fornito, altrimenti usa goBack().

## Tasti di Scorciatoia

- **ESC**: Torna indietro (funziona su tutte le pagine admin)

## Stili CSS

Le classi CSS disponibili sono:
- `.back-button`: Stile base
- `.back-button-compact`: Versione compatta
- `.back-button-animated`: Versione con animazioni

## Responsive Design

- Su schermi piccoli (mobile), il testo "Indietro" è nascosto e viene mostrata solo l'icona
- Il pulsante si adatta automaticamente alle dimensioni dello schermo

## Esempi di Utilizzo

### In una pagina di dettaglio progetto
```html
<div class="flex items-center justify-between mb-4">
    {% include 'admin/components/back_button.html' %}
    <h2>Dettagli Progetto</h2>
</div>
```

### Con URL personalizzato
```html
{% set back_url = url_for('admin.projects_list') %}
{% include 'admin/components/back_button_custom.html' with context %}
```

### Versione compatta in una toolbar
```html
<div class="toolbar">
    {% include 'admin/components/back_button_compact.html' %}
    <!-- altri pulsanti -->
</div>
```
