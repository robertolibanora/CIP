"""
Factory per creare l'applicazione Flask
Configura i percorsi per template e file assets
Task 2.2: Configurazione sicura sessioni
"""

from flask import Flask, url_for
from werkzeug.routing import BuildError
import logging
import os
import hashlib
from config.paths import TEMPLATES_DIR, ASSETS_DIR, UPLOADS_DIR
from backend.shared.database import get_db_connection

def hash_password(password: str) -> str:
    """Hash della password usando SHA-256 (stesso sistema dell'autenticazione)"""
    return hashlib.sha256(password.encode()).hexdigest()

def create_admin_user():
    """
    Crea utente admin se non esiste già nel database.
    Usa variabili ambiente per credenziali.
    Gestisce errori senza bloccare l'avvio app.
    """
    logger = logging.getLogger(__name__)
    
    # Ottieni credenziali admin dalle variabili ambiente
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@cipimmobiliare.it')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    admin_nome = os.environ.get('ADMIN_NOME', 'Admin')
    admin_cognome = os.environ.get('ADMIN_COGNOME', 'CIP')
    admin_telegram = os.environ.get('ADMIN_TELEGRAM', 'admin_cip')
    admin_telefono = os.environ.get('ADMIN_TELEFONO', '+39000000000')
    
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                # Verifica se esiste già un admin
                cur.execute("SELECT id, email FROM users WHERE role = 'admin' LIMIT 1")
                existing_admin = cur.fetchone()
                
                if existing_admin:
                    logger.info(f"Utente admin già esistente: {existing_admin['email']}")
                    return existing_admin
                
                # Crea nuovo admin
                password_hash = hash_password(admin_password)
                
                cur.execute("""
                    INSERT INTO users (
                        email, password_hash, nome, cognome, nome_telegram, telefono,
                        role, referral_code, kyc_status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    RETURNING id, email
                """, (
                    admin_email,
                    password_hash,
                    admin_nome,
                    admin_cognome,
                    admin_telegram,
                    admin_telefono,
                    'admin',
                    'ADMIN001',
                    'verified'
                ))
                
                new_admin = cur.fetchone()
                logger.info(f"✅ Utente admin creato con successo: {new_admin['email']}")
                return new_admin
                
    except Exception as e:
        logger.warning(f"⚠️ Impossibile creare utente admin: {e}")
        # Non bloccare l'avvio dell'app se la creazione admin fallisce
        return None

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
    
    # Crea utente admin automaticamente se non esiste
    try:
        create_admin_user()
    except Exception as e:
        app.logger.warning(f"Impossibile creare utente admin: {e}")
    
    return app
