#!/usr/bin/env python3
"""
CIP Immobiliare - Main Application
Applicazione principale con struttura riorganizzata
"""

import os
from dotenv import load_dotenv
from flask import redirect, url_for

# Carica configurazione
load_dotenv("config/env.local")

# Importa configurazione
from config.config import config

# Importa factory app
from backend.app_factory import create_app

# Crea app Flask
app = create_app()

# Importa moduli backend riorganizzati
from backend.admin.routes import admin_bp
from backend.auth.routes import auth_bp
from backend.user.routes import user_bp
from backend.portfolio.routes import portfolio_bp

# Registra blueprints
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(user_bp, url_prefix='/user')
app.register_blueprint(portfolio_bp, url_prefix='/portfolio')

# Route principale
@app.route("/")
def index():
    return redirect(url_for("auth.login"))

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 8090)),
        debug=os.environ.get("FLASK_DEBUG", "0") == "1"
    )
