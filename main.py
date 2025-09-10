#!/usr/bin/env python3
"""
CIP Immobiliare - Main Application
Applicazione principale con struttura riorganizzata in compartimenti stagni
"""

import os
from dotenv import load_dotenv
from flask import redirect, url_for, send_from_directory

# Carica configurazione
load_dotenv("config/env.local")

# Importa configurazione
from config.config import config

# Importa factory app
from backend.app_factory import create_app

# Crea app Flask
app = create_app()

# Configura logging per autenticazione
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.info("Applicazione CIP Immobiliare avviata con middleware di autenticazione")

# Importa moduli backend riorganizzati
from backend.admin.routes import admin_bp
from backend.auth.routes import auth_bp
from backend.user.routes import user_bp

# Importa i nuovi blueprint dei compartimenti stagni User
from backend.user import user_blueprints

# Importa i nuovi blueprint per le API
# I blueprint KYC sono già registrati in app_factory.py
from backend.portfolio_api import portfolio_api_bp
from backend.deposits import deposits_bp
from backend.withdrawals import withdrawals_bp
from backend.profits import profits_bp

# Healthcheck minimale per smoke test
@app.get("/health")
def health():
    return {"status": "ok"}, 200

# Registra blueprints principali
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')

# Registra i blueprint dei compartimenti stagni User
for blueprint in user_blueprints:
    app.register_blueprint(blueprint, url_prefix='/user')

# Registra i nuovi blueprint per le API
# I blueprint KYC sono già registrati in app_factory.py
app.register_blueprint(portfolio_api_bp, url_prefix='/portfolio')
app.register_blueprint(deposits_bp, url_prefix='/deposits')
app.register_blueprint(withdrawals_bp, url_prefix='/withdrawals')
app.register_blueprint(profits_bp, url_prefix='/profits')

# Route per assets
@app.route('/assets/<path:filename>')
def assets(filename):
    """Serve i file dalla cartella frontend/assets"""
    assets_dir = os.path.join(os.path.dirname(__file__), 'frontend', 'assets')
    return send_from_directory(assets_dir, filename)

# Route per uploads (documenti KYC)
@app.route('/uploads/<path:filename>')
def uploads(filename):
    """Serve i file caricati dagli utenti"""
    # 1) Prova prima nella cartella KYC in instance (nuovo flusso)
    kyc_dir = app.config.get('UPLOAD_FOLDER', os.path.join('instance', 'uploads', 'kyc'))
    kyc_path = os.path.join(kyc_dir, filename)
    try:
        if os.path.exists(kyc_path):
            return send_from_directory(kyc_dir, filename)
    except Exception:
        pass

    # 2) Fallback: vecchia cartella /uploads nello stesso repo (compatibilità legacy)
    legacy_uploads_dir = os.path.join(os.path.dirname(__file__), 'uploads')
    return send_from_directory(legacy_uploads_dir, filename)

# Route specifica per KYC uploads
@app.route('/uploads/kyc/<path:filename>')
def kyc_uploads(filename):
    """Serve i file KYC caricati"""
    kyc_dir = app.config.get('UPLOAD_FOLDER', os.path.join('instance', 'uploads', 'kyc'))
    return send_from_directory(kyc_dir, filename)

# Route per immagini progetti (pubblica)
@app.route('/uploads/projects/<filename>')
def project_images(filename):
    """Serve le immagini dei progetti pubblicamente"""
    from flask import current_app
    # Usa la cartella configurata (UPLOAD_FOLDER)/projects
    upload_base = current_app.config.get('UPLOAD_FOLDER', os.path.join('instance', 'uploads'))
    projects_dir = os.path.join(upload_base, 'projects')
    return send_from_directory(projects_dir, filename)

# Route per file statici (rimossa - cartella static eliminata)
# Tutti i file sono ora serviti dalla cartella assets

# Route principale con reindirizzamento intelligente
@app.route("/")
def index():
    from flask import session
    
    # Reindirizzamento basato su ruolo se utente già autenticato
    if 'user_id' in session and 'role' in session:
        if session.get('role') == 'admin':
            return redirect(url_for("admin.admin_dashboard"))
        else:
            return redirect(url_for("user.dashboard"))
    
    return redirect(url_for("auth.login"))

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 12345)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )

