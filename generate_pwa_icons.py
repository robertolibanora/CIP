#!/usr/bin/env python3
"""
Script per generare le icone PWA basate sul logo principale
"""

from PIL import Image
import os

def generate_pwa_icons():
    # Percorso del logo principale
    logo_path = "frontend/assets/logo.png"
    
    # Dimensioni richieste per PWA
    sizes = [
        16, 32, 57, 60, 72, 76, 96, 114, 120, 128, 144, 152, 180, 192, 384, 512
    ]
    
    # Crea la directory delle icone se non esiste
    icons_dir = "frontend/assets/icons"
    os.makedirs(icons_dir, exist_ok=True)
    
    try:
        # Carica il logo principale
        with Image.open(logo_path) as logo:
            print(f"Logo caricato: {logo.size}")
            
            # Genera tutte le icone
            for size in sizes:
                # Ridimensiona mantenendo le proporzioni
                resized = logo.resize((size, size), Image.Resampling.LANCZOS)
                
                # Salva l'icona
                icon_path = os.path.join(icons_dir, f"icon-{size}x{size}.png")
                resized.save(icon_path, "PNG", optimize=True)
                print(f"Generata: {icon_path} ({size}x{size})")
            
            print("\n✅ Tutte le icone PWA sono state generate con successo!")
            print("Le icone sono basate sul logo principale e ottimizzate per PWA.")
            
    except FileNotFoundError:
        print(f"❌ Errore: Logo non trovato in {logo_path}")
    except Exception as e:
        print(f"❌ Errore durante la generazione: {e}")

if __name__ == "__main__":
    generate_pwa_icons()
