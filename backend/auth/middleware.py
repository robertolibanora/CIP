"""
Middleware per autenticazione e autorizzazioni - VERSIONE CORRETTA
Task 2.2: Auth System - Verifiche e Blocchi
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app
from typing import Optional, Callable, Any
import logging
import time
from datetime import datetime, timedelta

from backend.shared.models import UserRole, KYCStatus
from backend.shared.database import get_connection
from backend.utils.http import is_api_request

logger = logging.getLogger(__name__)

# ============================================================================
# COSTANTI SICUREZZA SESSIONI
# ============================================================================

SESSION_TIMEOUT = 3600  # 1 ora in secondi
SESSION_LAST_ACTIVITY_KEY = 'last_activity'
SESSION_CREATED_KEY = 'created_at'
SESSION_IP_KEY = 'ip_address'
SESSION_USER_AGENT_KEY = 'user_agent'

# ============================================================================
# FUNZIONI UTILITY
# ============================================================================

def get_user_by_id(user_id: int) -> Optional[dict]:
    """Recupera utente dal database per ID"""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, email, nome, cognome, role, kyc_status
                FROM users WHERE id = %s
            """, (user_id,))
            user = cur.fetchone()
            return user
    except Exception as e:
        logger.error(f"Errore nel recupero utente {user_id}: {e}")
        return None

def get_current_user() -> Optional[dict]:
    """Recupera utente corrente dalla sessione"""
    user_id = session.get('user_id')
    if not user_id:
        return None
    
    return get_user_by_id(user_id)

def is_authenticated() -> bool:
    """Verifica se l'utente è autenticato"""
    return 'user_id' in session

def is_admin() -> bool:
    """Verifica se l'utente corrente è admin"""
    user = get_current_user()
    return user and user.get('role') == UserRole.ADMIN.value

def is_kyc_verified() -> bool:
    """Verifica se l'utente corrente ha KYC verificato"""
    user = get_current_user()
    return user and user.get('kyc_status') == KYCStatus.VERIFIED.value

# ============================================================================
# VALIDAZIONE SICUREZZA SESSIONI
# ============================================================================

def validate_session_security() -> bool:
    """Valida la sicurezza della sessione corrente"""
    if not is_authenticated():
        return False
    
    # Verifica timeout sessione
    last_activity = session.get(SESSION_LAST_ACTIVITY_KEY)
    if last_activity:
        if time.time() - last_activity > SESSION_TIMEOUT:
            logger.warning(f"Sessione scaduta per utente {session.get('user_id')}")
            return False
    
    # Verifica IP address (se configurato)
    if current_app.config.get('CHECK_SESSION_IP', False):
        stored_ip = session.get(SESSION_IP_KEY)
        if stored_ip and stored_ip != request.remote_addr:
            logger.warning(f"Cambio IP sospetto per utente {session.get('user_id')}: {stored_ip} -> {request.remote_addr}")
            return False
    
    # Verifica User-Agent (se configurato)
    if current_app.config.get('CHECK_SESSION_USER_AGENT', False):
        stored_ua = session.get(SESSION_USER_AGENT_KEY)
        current_ua = request.headers.get('User-Agent', '')
        
        # Solo se entrambi sono presenti e diversi
        if stored_ua and current_ua and stored_ua != current_ua:
            logger.warning(f"Cambio User-Agent sospetto per utente {session.get('user_id')}")
            return False
    
    return True

def update_session_activity():
    """Aggiorna timestamp ultima attività sessione"""
    if is_authenticated():
        session[SESSION_LAST_ACTIVITY_KEY] = time.time()
        session.modified = True

def create_secure_session(user_data: dict):
    """Crea una sessione sicura con tutti i controlli"""
    logger.info(f"Creazione sessione per utente: {user_data['email']}")
    session.clear()
    session['user_id'] = user_data['id']
    session['user_role'] = user_data['role']
    session['role'] = user_data['role']  # Per compatibilità
    session['user_name'] = user_data.get('nome', '') + ' ' + user_data.get('cognome', '')
    session[SESSION_CREATED_KEY] = time.time()
    session[SESSION_LAST_ACTIVITY_KEY] = time.time()
    session[SESSION_IP_KEY] = request.remote_addr
    session[SESSION_USER_AGENT_KEY] = request.headers.get('User-Agent', '')
    session.permanent = True
    session.modified = True
    logger.info(f"Sessione creata con successo per: {user_data['email']}")

def destroy_session():
    """Distrugge completamente la sessione - USARE SOLO PER LOGOUT ESPLICITO"""
    logger.info("Distruzione sessione richiesta")
    session.clear()
    session.modified = True

# ============================================================================
# MIDDLEWARE KYC
# ============================================================================

class KYCRequired:
    """Middleware per richiedere verifica KYC"""
    
    def __init__(self, redirect_to: str = 'user.profile'):
        self.redirect_to = redirect_to
    
    def check_access(self) -> bool:
        """Verifica se l'utente può accedere (KYC verificato o admin)"""
        if not is_authenticated():
            return False
        
        if not validate_session_security():
            return False
        
        user = get_current_user()
        if not user:
            return False
        
        # Admin può sempre accedere
        if user.get('role') == UserRole.ADMIN.value:
            return True
        
        # Utenti normali devono avere KYC verificato
        return user.get('kyc_status') == KYCStatus.VERIFIED.value
    
    def __call__(self, f: Callable) -> Callable:
        """Decorator per proteggere route"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not self.check_access():
                flash("Verifica KYC richiesta per accedere a questa funzionalità", "warning")
                return redirect(url_for(self.redirect_to))
            return f(*args, **kwargs)
        return decorated_function

# ============================================================================
# DECORATORI AUTORIZZAZIONE
# ============================================================================

def login_required(f: Callable) -> Callable:
    """Decorator per richiedere autenticazione"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        if not validate_session_security():
            destroy_session()
            flash("Sessione non valida. Effettua nuovamente il login.", "error")
            return redirect(url_for('auth.login'))
        
        update_session_activity()
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """Decorator per richiedere ruolo admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        if not validate_session_security():
            destroy_session()
            flash("Sessione non valida. Effettua nuovamente il login.", "error")
            return redirect(url_for('auth.login'))
        
        if not is_admin():
            flash("Accesso negato. Solo gli amministratori possono accedere a questa pagina", "error")
            return redirect(url_for('user.dashboard'))
        
        update_session_activity()
        return f(*args, **kwargs)
    return decorated_function

def kyc_verified(f: Callable) -> Callable:
    """Decorator per richiedere KYC verificato"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        if not validate_session_security():
            destroy_session()
            flash("Sessione non valida. Effettua nuovamente il login.", "error")
            return redirect(url_for('auth.login'))
        
        if not is_kyc_verified():
            flash("Verifica KYC richiesta per accedere a questa funzionalità", "warning")
            return redirect(url_for('user.profile'))
        
        update_session_activity()
        return f(*args, **kwargs)
    return decorated_function

def role_required(required_role: UserRole) -> Callable:
    """Decorator per richiedere ruolo specifico"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authenticated():
                flash("Accesso richiesto per visualizzare questa pagina", "warning")
                return redirect(url_for('auth.login'))
            
            if not validate_session_security():
                destroy_session()
                flash("Sessione non valida. Effettua nuovamente il login.", "error")
                return redirect(url_for('auth.login'))
            
            user = get_current_user()
            if not user or user.get('role') != required_role.value:
                flash(f"Accesso negato. Ruolo {required_role.value} richiesto", "error")
                return redirect(url_for('user.dashboard'))
            
            update_session_activity()
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================================================
# MIDDLEWARE GLOBALE CORRETTO
# ============================================================================

def setup_auth_middleware(app):
    """Configura middleware di autenticazione globale"""
    
    @app.before_request
    def before_request():
        """Middleware eseguito prima di ogni richiesta"""
        # Skip per route statiche e pubbliche
        if (request.path.startswith("/static") or 
            request.path.startswith("/assets") or
            request.path.startswith("/kyc/api/") or  # Tutte le API KYC
            request.endpoint in ['auth.login', 'auth.register', 'auth.logout']):
            return
        
        # Aggiorna attività sessione per utenti autenticati (anche per API)
        if is_authenticated():
            update_session_activity()
        
        # NON fare controlli di redirect/clear per API - lascia ai decorator
        if is_api_request():
            logger.info(f"API request detected: {request.path} -> skipping middleware")
            return
        
        # Controlli solo per pagine HTML
        if not is_authenticated():
            # Route che richiedono autenticazione
            protected_routes = [
                'user.', 'admin.', 'portfolio.', 
                'deposits.', 'withdrawals.', 'profits.'
            ]
            # Escludi le API KYC dal controllo globale - gestite dai decorator
            
            if request.endpoint and any(request.endpoint.startswith(prefix) for prefix in protected_routes):
                flash("Accesso richiesto per visualizzare questa pagina", "warning")
                return redirect(url_for('auth.login'))
        else:
            # Verifica sicurezza sessione solo per pagine HTML
            if not validate_session_security():
                destroy_session()
                flash("Sessione non valida. Effettua nuovamente il login.", "error")
                return redirect(url_for('auth.login'))
            
            # Verifica separazione ruoli Admin/User solo per pagine HTML
            if request.endpoint:
                user_role = session.get('user_role', 'investor')
                
                # Admin NON deve accedere a rotte user
                if user_role == 'admin' and request.endpoint.startswith('user.'):
                    logger.warning(f"ADMIN ha tentato accesso rotta USER: {request.endpoint}")
                    flash("Accesso negato: Gli amministratori devono usare il pannello admin", "error")
                    return redirect(url_for('admin.admin_dashboard'))
                
                # User NON deve accedere a rotte admin
                if user_role == 'investor' and request.endpoint.startswith('admin.'):
                    logger.warning(f"USER ha tentato accesso rotta ADMIN: {request.endpoint}")
                    flash("Accesso negato: Area riservata agli amministratori", "error")
                    return redirect(url_for('user.dashboard'))
    
    @app.after_request
    def after_request(response):
        """Middleware eseguito dopo ogni richiesta"""
        # Log accessi per sicurezza
        if is_authenticated():
            user = get_current_user()
            if user:
                logger.info(f"Accesso: {user.get('email')} -> {request.endpoint}")
        
        return response

# ============================================================================
# VALIDAZIONI BUSINESS LOGIC
# ============================================================================

def can_user_invest(user_id: int) -> bool:
    """Verifica se un utente può investire"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    # Admin può sempre investire
    if user.get('role') == UserRole.ADMIN.value:
        return True
    
    # Utenti normali devono avere KYC verificato
    return user.get('kyc_status') == KYCStatus.VERIFIED.value

def can_user_withdraw(user_id: int) -> bool:
    """Verifica se un utente può prelevare"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    # Admin può sempre prelevare
    if user.get('role') == UserRole.ADMIN.value:
        return True
    
    # Utenti normali devono avere KYC verificato
    return user.get('kyc_status') == KYCStatus.VERIFIED.value

def can_user_access_portfolio(user_id: int) -> bool:
    """Verifica se un utente può accedere al portafoglio"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    # Admin può sempre accedere
    if user.get('role') == UserRole.ADMIN.value:
        return True
    
    # Utenti normali devono avere KYC verificato
    return user.get('kyc_status') == KYCStatus.VERIFIED.value
