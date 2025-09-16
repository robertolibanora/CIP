import os
from datetime import timedelta
from dotenv import load_dotenv
from .paths import UPLOADS_DIR, TEMPLATES_DIR, ASSETS_DIR, ENV_FILE

# Carica variabili ambiente dal file config/env.local
load_dotenv(ENV_FILE)

# Percorsi base
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.getenv("INSTANCE_DIR") or os.path.join(os.path.dirname(BASE_DIR), "instance")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER") or os.path.join(INSTANCE_DIR, "uploads", "kyc")

class Config:
    """Configurazione base Flask"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://localhost/cip_immobiliare'
    UPLOAD_FOLDER = UPLOAD_FOLDER  # Usa il percorso KYC specifico
    INSTANCE_UPLOADS_DIR = UPLOAD_FOLDER  # Alias per chiarezza
    TEMPLATE_FOLDER = TEMPLATES_DIR
    ASSETS_FOLDER = ASSETS_DIR
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
    
    # KYC Upload settings
    ALLOWED_KYC_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    
    # Referral settings
    # DEFAULT_REFERRAL_CODE rimosso - ora usiamo logica dinamica per assegnare al primo utente 'investor'
    
    # ============================================================================
    # CONFIGURAZIONE SESSIONI SICURE
    # ============================================================================
    SESSION_COOKIE_NAME = "session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"  # Lax in dev, Strict in prod
    SESSION_COOKIE_SECURE = False    # False in dev, True in prod su HTTPS
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    
    # ============================================================================
    # CONFIGURAZIONE CSRF
    # ============================================================================
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

class DevelopmentConfig(Config):
    """Configurazione sviluppo"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Configurazione produzione"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # HTTPS obbligatorio in produzione
    SESSION_COOKIE_SAMESITE = "Strict"

class TestingConfig(Config):
    """Configurazione test"""
    TESTING = True
    DEBUG = True
    DATABASE_URL = os.environ.get('TEST_DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/cip_test'

# Configurazione per ambiente
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
