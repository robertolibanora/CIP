"""
Decoratori per autorizzazione e controllo accessi
Task 1.3: Ruoli e Permessi
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, jsonify
from typing import Callable, Any, Union, List
import logging

from backend.shared.models import UserRole, KYCStatus
from backend.auth.middleware import get_current_user, is_authenticated, validate_session_security
from backend.utils.http import is_api_request

logger = logging.getLogger(__name__)

# ============================================================================
# DECORATORI BASE
# ============================================================================

def login_required(f: Callable) -> Callable:
    """Decorator per richiedere autenticazione base"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Debug log
        logger.info(f"login_required: {request.path} -> is_authenticated: {is_authenticated()}")
        logger.info(f"Session data: {dict(session)}")
        
        if not is_authenticated():
            # Se è una richiesta API, restituisci errore JSON
            if is_api_request():
                return jsonify({'error': 'unauthorized'}), 401
            # Altrimenti redirect HTML
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def guest_only(f: Callable) -> Callable:
    """Decorator per utenti non autenticati (es. login, register)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Se è una richiesta POST (login/register), permetti sempre l'accesso
        # per permettere la validazione delle credenziali
        if request.method == 'POST':
            return f(*args, **kwargs)
        
        # Se l'utente è autenticato e la sessione è valida, reindirizza
        if is_authenticated() and validate_session_security():
            flash("Sei già autenticato", "info")
            return redirect(url_for('user.dashboard'))
        
        # Se l'utente è autenticato ma la sessione non è valida, distruggi la sessione
        # e permetti l'accesso alla pagina di login per mostrare errori
        if is_authenticated() and not validate_session_security():
            from backend.auth.middleware import destroy_session
            destroy_session()
        
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# DECORATORI RUOLI
# ============================================================================

def role_required(required_role: Union[UserRole, str]) -> Callable:
    """Decorator per richiedere ruolo specifico"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authenticated():
                # Se è una richiesta API, restituisci errore JSON
                if is_api_request():
                    return jsonify({'error': 'unauthorized'}), 401
                # Altrimenti redirect HTML
                flash("Accesso richiesto per visualizzare questa pagina", "warning")
                return redirect(url_for('auth.login'))
            
            user = get_current_user()
            if not user:
                # Se è una richiesta API, restituisci errore JSON
                if is_api_request():
                    return jsonify({'error': 'unauthorized'}), 401
                # Altrimenti redirect HTML
                flash("Sessione utente non valida", "error")
                return redirect(url_for('auth.login'))
            
            user_role = user.get('ruolo')
            required_role_str = required_role.value if hasattr(required_role, 'value') else required_role
            
            if user_role != required_role_str:
                logger.warning(f"Accesso negato: {user.get('email')} (ruolo: {user_role}) -> richiesto: {required_role_str}")
                # Se è una richiesta API, restituisci errore JSON
                if is_api_request():
                    return jsonify({'error': 'forbidden'}), 403
                # Altrimenti redirect HTML
                flash(f"Accesso negato. Ruolo {required_role_str} richiesto", "error")
                return redirect(url_for('user.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f: Callable) -> Callable:
    """Decorator per richiedere ruolo admin"""
    return role_required(UserRole.ADMIN)(f)

def investor_required(f: Callable) -> Callable:
    """Decorator per richiedere ruolo investor"""
    return role_required(UserRole.INVESTOR)(f)

def any_role_required(allowed_roles: List[Union[UserRole, str]]) -> Callable:
    """Decorator per richiedere uno dei ruoli specificati"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authenticated():
                flash("Accesso richiesto per visualizzare questa pagina", "warning")
                return redirect(url_for('auth.login'))
            
            user = get_current_user()
            if not user:
                flash("Sessione utente non valida", "error")
                return redirect(url_for('auth.login'))
            
            user_role = user.get('ruolo')
            allowed_roles_str = [
                role.value if hasattr(role, 'value') else role 
                for role in allowed_roles
            ]
            
            if user_role not in allowed_roles_str:
                logger.warning(f"Accesso negato: {user.get('email')} (ruolo: {user_role}) -> permessi: {allowed_roles_str}")
                flash("Accesso negato. Ruolo non autorizzato", "error")
                return redirect(url_for('user.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================================================
# DECORATORI KYC
# ============================================================================

def kyc_verified(f: Callable) -> Callable:
    """Decorator per richiedere KYC verificato"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user:
            flash("Sessione utente non valida", "error")
            return redirect(url_for('auth.login'))
        
        # Admin può sempre accedere
        if user.get('ruolo') == UserRole.ADMIN.value:
            return f(*args, **kwargs)
        
        # Utenti normali devono avere KYC verificato
        if user.get('kyc_status') != KYCStatus.VERIFIED.value:
            # Se è una richiesta AJAX, restituisci errore JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'kyc_required',
                    'message': 'Verifica KYC richiesta per accedere a questa funzionalità',
                    'kyc_status': user.get('kyc_status')
                }), 403
            
            # Altrimenti, reindirizza al profilo
            flash("Verifica KYC richiesta per accedere a questa funzionalità", "warning")
            return redirect(url_for('user.profile'))
        
        return f(*args, **kwargs)
    return decorated_function

def kyc_pending_allowed(f: Callable) -> Callable:
    """Decorator per permettere accesso anche con KYC in attesa"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # Per richieste API restituisci JSON, non redirect HTML
            if is_api_request():
                return jsonify({'error': 'unauthorized'}), 401
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user:
            if is_api_request():
                return jsonify({'error': 'unauthorized'}), 401
            flash("Sessione utente non valida", "error")
            return redirect(url_for('auth.login'))
        
        # Admin può sempre accedere
        if user.get('ruolo') == UserRole.ADMIN.value:
            return f(*args, **kwargs)
        
        # Utenti normali devono avere KYC almeno in attesa
        kyc_status = user.get('kyc_status')
        if kyc_status not in [KYCStatus.PENDING.value, KYCStatus.VERIFIED.value]:
            if is_api_request():
                return jsonify({
                    'error': 'kyc_required',
                    'message': 'Verifica KYC richiesta per accedere a questa funzionalità',
                    'kyc_status': kyc_status
                }), 403
            flash("Verifica KYC richiesta per accedere a questa funzionalità", "warning")
            return redirect(url_for('user.profile'))
        
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# DECORATORI PERMESSI SPECIFICI
# ============================================================================

def can_invest(f: Callable) -> Callable:
    """Decorator per verificare se l'utente può investire"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user:
            flash("Sessione utente non valida", "error")
            return redirect(url_for('auth.login'))
        
        # Admin può sempre investire
        if user.get('ruolo') == UserRole.ADMIN.value:
            return f(*args, **kwargs)
        
        # Utenti normali devono avere KYC verificato
        if user.get('kyc_status') != KYCStatus.VERIFIED.value:
            # Se è una richiesta AJAX, restituisci errore JSON
            from flask import request, jsonify
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'error': 'kyc_required',
                    'message': 'Verifica KYC richiesta per investire',
                    'kyc_status': user.get('kyc_status')
                }), 403
            
            # Altrimenti, reindirizza al profilo (fallback per browser senza JS)
            flash("Verifica KYC richiesta per investire", "warning")
            return redirect(url_for('user.profile'))
        
        return f(*args, **kwargs)
    return decorated_function

def can_withdraw(f: Callable) -> Callable:
    """Decorator per verificare se l'utente può prelevare"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # Per richieste API restituisci JSON, non redirect HTML
            if is_api_request():
                return jsonify({'error': 'unauthorized'}), 401
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        user = get_current_user()
        if not user:
            if is_api_request():
                return jsonify({'error': 'unauthorized'}), 401
            flash("Sessione utente non valida", "error")
            return redirect(url_for('auth.login'))
        
        # Admin può sempre prelevare
        if user.get('ruolo') == UserRole.ADMIN.value:
            return f(*args, **kwargs)
        
        # Utenti normali devono avere KYC verificato
        if user.get('kyc_status') != KYCStatus.VERIFIED.value:
            if is_api_request():
                return jsonify({
                    'error': 'kyc_required',
                    'message': 'Verifica KYC richiesta per prelevare',
                    'kyc_status': user.get('kyc_status')
                }), 403
            flash("Verifica KYC richiesta per prelevare", "warning")
            return redirect(url_for('user.profile'))
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# DECORATORI CONDIZIONALI
# ============================================================================

def conditional_access(condition_func: Callable[[], bool], 
                      redirect_to: str = 'user.dashboard',
                      message: str = "Accesso negato") -> Callable:
    """Decorator per accesso condizionale basato su funzione personalizzata"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not condition_func():
                flash(message, "error")
                return redirect(url_for(redirect_to))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def rate_limit(max_requests: int = 100, window_seconds: int = 3600) -> Callable:
    """Decorator per limitare il numero di richieste per IP"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Implementazione base rate limiting
            # In produzione, usare Redis o database per tracking
            client_ip = request.remote_addr
            logger.info(f"Rate limit check per IP: {client_ip}")
            
            # Per ora, permette sempre l'accesso
            # TODO: Implementare rate limiting reale
            return f(*args, **kwargs)
        return decorated_function
    return decorator
