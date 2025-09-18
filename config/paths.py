"""
Configurazione percorsi per template e file assets
"""

import os

# Percorsi base
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Percorsi frontend
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TEMPLATES_DIR = os.path.join(FRONTEND_DIR, "templates")
ASSETS_DIR = os.path.join(FRONTEND_DIR, "assets")
UPLOADS_DIR = os.path.join(FRONTEND_DIR, "uploads")

# Percorsi backend
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

# Percorsi configurazione
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# Selezione dinamica del file di configurazione
def get_env_file():
    """Seleziona il file di configurazione basato sull'ambiente"""
    flask_env = os.environ.get('FLASK_ENV', 'local')
    if flask_env == 'production':
        return os.path.join(CONFIG_DIR, "env.production")
    else:
        return os.path.join(CONFIG_DIR, "env.local")

ENV_FILE = get_env_file()
