"""
Routes per gestione profitti
"""

from flask import Blueprint

profits_bp = Blueprint('profits', __name__, url_prefix='/profits')

@profits_bp.route('/')
def index():
    """Pagina principale profitti"""
    return "Profitti - In sviluppo"
