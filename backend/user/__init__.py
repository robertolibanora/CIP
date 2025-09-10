"""
CIP Immobiliare - User Module
Modulo utente con compartimenti stagni per ogni sezione
"""

from flask import Blueprint

# Importa tutti i blueprint dei compartimenti stagni
from .dashboard import dashboard_bp
from .portfolio import portfolio_bp
from .projects import projects_bp
from .referral import referral_bp
from .profile import profile_bp
from .new_project import new_project_bp

# Blueprint principale user (per compatibilità)
from .routes import user_bp

# Lista di tutti i blueprint per la registrazione
user_blueprints = [
    dashboard_bp,
    portfolio_bp,
    projects_bp,
    referral_bp,
    profile_bp,
    new_project_bp
]

__all__ = [
    'user_bp',  # Per compatibilità
    'user_blueprints',  # Per la nuova struttura
    'dashboard_bp',
    'portfolio_bp', 
    'projects_bp',
    'referral_bp',
    'profile_bp',
    'new_project_bp'
]
