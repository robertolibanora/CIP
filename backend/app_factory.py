"""
Factory per creare l'applicazione Flask
Configura i percorsi per template e static files
"""

from flask import Flask, url_for
from werkzeug.routing import BuildError
import logging
from config.paths import TEMPLATES_DIR, STATIC_DIR, UPLOADS_DIR

def create_app():
    """Crea e configura l'applicazione Flask"""
    
    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR
    )
    
    # Configurazione percorsi
    app.config['UPLOAD_FOLDER'] = UPLOADS_DIR
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB
    
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
    
    return app
