import logging
import traceback
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CIPError(Exception):
    """Classe base per errori personalizzati CIP"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['error'] = self.message
        rv['status_code'] = self.status_code
        return rv

class ValidationError(CIPError):
    """Errore di validazione dati"""
    def __init__(self, message="Dati non validi", payload=None):
        super().__init__(message, 400, payload)

class AuthenticationError(CIPError):
    """Errore di autenticazione"""
    def __init__(self, message="Non autorizzato", payload=None):
        super().__init__(message, 401, payload)

class AuthorizationError(CIPError):
    """Errore di autorizzazione"""
    def __init__(self, message="Accesso negato", payload=None):
        super().__init__(message, 403, payload)

class NotFoundError(CIPError):
    """Risorsa non trovata"""
    def __init__(self, message="Risorsa non trovata", payload=None):
        super().__init__(message, 404, payload)

def register_error_handlers(app):
    """Registra i gestori di errore per l'app Flask"""
    
    @app.errorhandler(CIPError)
    def handle_cip_error(error):
        """Gestisce errori CIP personalizzati"""
        response = jsonify(error.to_dict())
        response.status_code = error.status_code
        return response

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        """Gestisce errori HTTP standard"""
        response = jsonify({
            'error': error.description,
            'status_code': error.code
        })
        response.status_code = error.code
        return response

    @app.errorhandler(Exception)
    def handle_generic_error(error):
        """Gestisce errori generici non catturati"""
        logger.error(f"Errore non gestito: {error}")
        logger.error(traceback.format_exc())
        
        response = jsonify({
            'error': 'Errore interno del server',
            'status_code': 500
        })
        response.status_code = 500
        return response

    @app.errorhandler(404)
    def not_found(error):
        """Gestisce errori 404"""
        return jsonify({
            'error': 'Endpoint non trovato',
            'status_code': 404,
            'path': request.path
        }), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        """Gestisce errori 405 (Method Not Allowed)"""
        return jsonify({
            'error': 'Metodo non consentito',
            'status_code': 405,
            'method': request.method,
            'path': request.path
        }), 405

def log_request_info():
    """Logga informazioni sulla richiesta per debugging"""
    logger.info(f"Request: {request.method} {request.path}")
    if request.json:
        logger.info(f"JSON data: {request.json}")
    if request.files:
        logger.info(f"Files: {list(request.files.keys())}")

def log_error(error, context=""):
    """Logga errori con contesto"""
    logger.error(f"Errore in {context}: {error}")
    logger.error(traceback.format_exc())
