#!/usr/bin/env python3
"""
WSGI entry point per produzione
Usa con: gunicorn wsgi:app
"""

import os
from dotenv import load_dotenv

# Carica variabili ambiente
load_dotenv()

# Importa l'app Flask
from admin import app

if __name__ == "__main__":
    # Configurazione produzione
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=debug
    )
