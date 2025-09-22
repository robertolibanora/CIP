"""
Modulo Portfolio - Gestione investimenti
Gestisce portfolio, investimenti e sistema referral
"""

from flask import Blueprint

# Crea blueprint portfolio
portfolio_bp = Blueprint('portfolio_v2', __name__)

# Importa routes
from . import routes
