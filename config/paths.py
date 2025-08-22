"""
Configurazione percorsi per template e file statici
"""

import os

# Percorsi base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Percorsi frontend
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR = os.path.join(FRONTEND_DIR, "assets")
UPLOADS_DIR = os.path.join(FRONTEND_DIR, "uploads")

# Percorsi backend
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Percorsi configurazione
CONFIG_DIR = os.path.join(BASE_DIR, "config")
ENV_FILE = os.path.join(CONFIG_DIR, "env.local")
