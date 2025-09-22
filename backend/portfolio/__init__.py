"""
Modulo Portfolio - Gestione investimenti
Gestisce portfolio, investimenti e sistema referral
"""

from flask import Blueprint

# Crea blueprint portfolio
portfolio_bp = Blueprint('portfolio_final', __name__)

# Importa routes
from . import routes
