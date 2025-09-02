"""
Modulo KYC per gestione verifica identità
"""

from .routes import kyc_bp
from .routes_user_api import kyc_user_api
from .routes_admin_api import kyc_admin_api

__all__ = ['kyc_bp', 'kyc_user_api', 'kyc_admin_api']