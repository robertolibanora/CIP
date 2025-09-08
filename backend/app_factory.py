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
from backend.shared.database import get_connection

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
        with get_connection() as conn:
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
    
    # Modalità testing (abilitata se TESTING=1)
    if os.environ.get('TESTING') == '1':
        app.config['TESTING'] = True
    
    # Configurazione percorsi
    app.config['UPLOAD_FOLDER'] = UPLOADS_DIR
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB
    
    # Crea cartella upload KYC se non esiste
    kyc_upload_dir = app.config.get('UPLOAD_FOLDER', UPLOADS_DIR)
    os.makedirs(kyc_upload_dir, exist_ok=True)
    
    # Controlli sicurezza sessione (disabilitati per sviluppo)
    app.config['CHECK_SESSION_IP'] = False  # Disabilitato per test
    app.config['CHECK_SESSION_USER_AGENT'] = False  # Disabilitato per test
    
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
    
    # Registra blueprint KYC
    try:
        from backend.kyc import kyc_bp, kyc_user_api, kyc_admin_api
        app.register_blueprint(kyc_bp)
        app.register_blueprint(kyc_user_api)
        app.register_blueprint(kyc_admin_api)
        app.logger.info("Blueprint KYC registrati con successo")
    except Exception as e:
        app.logger.warning(f"Impossibile registrare blueprint KYC: {e}")
    
    # Registra blueprint Portfolio (API deposito/bonifico/cronologie)
    try:
        from backend.portfolio.routes import portfolio_bp
        # Le route del blueprint iniziano già con '/api/...', quindi non aggiungiamo un ulteriore prefisso
        app.register_blueprint(portfolio_bp)
        app.logger.info("Blueprint Portfolio registrato con successo")
    except Exception as e:
        app.logger.error(f"Errore registrazione blueprint Portfolio: {e}")
    
    # Blueprint Withdrawals è registrato in main.py insieme agli altri moduli API
    
    # Deposits blueprint è registrato in main.py insieme agli altri moduli API
    # per evitare doppie registrazioni durante i test/factory usage.
    
    # Crea utente admin automaticamente se non esiste
    try:
        create_admin_user()
    except Exception as e:
        app.logger.warning(f"Impossibile creare utente admin: {e}")
    
    return app
