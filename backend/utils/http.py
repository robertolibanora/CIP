"""
Utility HTTP per identificare richieste API vs HTML
"""

from flask import request


def is_api_request() -> bool:
    """
    Determina se la richiesta corrente è una richiesta API che deve ricevere JSON.
    
    Criteri:
    1. Path inizia con /kyc/admin/api/ o /admin/api/
    2. Header Accept contiene application/json
    3. Header X-Requested-With è XMLHttpRequest (AJAX)
    
    Returns:
        bool: True se è una richiesta API, False se è HTML
    """
    # Verifica per path API specifici
    if (request.path.startswith("/kyc/admin/api/") or 
        request.path.startswith("/admin/api/") or
        "/api/" in request.path):
        return True
    
    # Verifica header Accept
    accept = request.headers.get("Accept", "")
    if "application/json" in accept.lower():
        return True
    
    # Verifica header X-Requested-With per AJAX
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    
    return False
