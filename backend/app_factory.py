"""
Factory per creare l'applicazione Flask
Configura i percorsi per template e file assets
Task 2.2: Configurazione sicura sessioni
"""

from flask import Flask, url_for
from werkzeug.routing import BuildError
import logging
from config.paths import TEMPLATES_DIR, ASSETS_DIR, UPLOADS_DIR

def create_app():
    """Crea e configura l'applicazione Flask"""
    
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=ASSETS_DIR
    )
    
    # Configurazione percorsi
    app.config['UPLOAD_FOLDER'] = UPLOADS_DIR
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB
    
    # Configurazione CSRF protection
    app.config['SECRET_KEY'] = 'your-secret-key-here'  # Cambia con una chiave sicura
    app.config['WTF_CSRF_ENABLED'] = True
    
    # ============================================================================
    # CONFIGURAZIONE SICUREZZA SESSIONI - Task 2.2
    # ============================================================================
    
    # Timeout sessione (1 ora)
    app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # secondi
    
    # Cookie sicuri
    app.config['SESSION_COOKIE_SECURE'] = False  # True in produzione con HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    # Controlli sicurezza sessione
    app.config['CHECK_SESSION_IP'] = True
    app.config['CHECK_SESSION_USER_AGENT'] = True
    
    # Carica configurazione
    from config.config import config
    app.config.from_object(config['default'])
    
    # Utility Jinja per URL sicuri
    def safe_url_for(endpoint, **values):
        """Versione sicura di url_for che non crasha se l'endpoint manca"""
        try:
            return url_for(endpoint, **values)
        except BuildError as e:
            app.logger.warning("safe_url_for: endpoint mancante: %s (%s)", endpoint, e)
            return "#"
    
    app.jinja_env.globals["safe_url_for"] = safe_url_for
    
    # Configura middleware di autenticazione
    try:
        from backend.auth.middleware import setup_auth_middleware
        setup_auth_middleware(app)
        app.logger.info("Middleware di autenticazione configurato con successo")
    except Exception as e:
        app.logger.warning(f"Impossibile configurare middleware di autenticazione: {e}")
    
    return app
