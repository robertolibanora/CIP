import os
from dotenv import load_dotenv
from .paths import UPLOADS_DIR, TEMPLATES_DIR, STATIC_DIR, ENV_FILE

# Carica variabili ambiente dal file config/env.local
load_dotenv(ENV_FILE)

class Config:
    """Configurazione base Flask"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DATABASE_URL = os.environ.get('DATABASE_URL') or 'postgresql://postgres:postgres@localhost:5432/cip'
    UPLOAD_FOLDER = UPLOADS_DIR
    TEMPLATE_FOLDER = TEMPLATES_DIR
    STATIC_FOLDER = STATIC_DIR
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    FLASK_DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'

class DevelopmentConfig(Config):
    """Configurazione sviluppo"""
    DEBUG = True
    TESTING = False

class ProductionConfig(Config):
    """Configurazione produzione"""
    DEBUG = False
    TESTING = False

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
