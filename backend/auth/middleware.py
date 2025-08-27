"""
Middleware per autenticazione e autorizzazioni
Task 1.3: Middleware KYC, Ruoli e Permessi
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, current_app
from typing import Optional, Callable, Any
import logging

from backend.shared.models import UserRole, KYCStatus
from backend.shared.database import get_connection

logger = logging.getLogger(__name__)

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
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f: Callable) -> Callable:
    """Decorator per richiedere ruolo admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        if not is_admin():
            flash("Accesso negato. Solo gli amministratori possono accedere a questa pagina", "error")
            return redirect(url_for('user.dashboard'))
        
        return f(*args, **kwargs)
    return decorated_function

def kyc_verified(f: Callable) -> Callable:
    """Decorator per richiedere KYC verificato"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            flash("Accesso richiesto per visualizzare questa pagina", "warning")
            return redirect(url_for('auth.login'))
        
        if not is_kyc_verified():
            flash("Verifica KYC richiesta per accedere a questa funzionalità", "warning")
            return redirect(url_for('user.profile'))
        
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
            
            user = get_current_user()
            if not user or user.get('role') != required_role.value:
                flash(f"Accesso negato. Ruolo {required_role.value} richiesto", "error")
                return redirect(url_for('user.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ============================================================================
# MIDDLEWARE GLOBALE
# ============================================================================

def setup_auth_middleware(app):
    """Configura middleware di autenticazione globale"""
    
    @app.before_request
    def before_request():
        """Middleware eseguito prima di ogni richiesta"""
        # Skip per route pubbliche
        public_routes = [
            'auth.login', 'auth.register', 'auth.logout',
            'static', 'assets'
        ]
        
        if request.endpoint in public_routes:
            return
        
        # Verifica autenticazione per route protette
        if not is_authenticated():
            # Route che richiedono autenticazione
            protected_routes = [
                'user.', 'admin.', 'kyc.', 'portfolio.', 
                'deposits.', 'withdrawals.', 'profits.'
            ]
            
            if any(request.endpoint.startswith(prefix) for prefix in protected_routes):
                flash("Accesso richiesto per visualizzare questa pagina", "warning")
                return redirect(url_for('auth.login'))
    
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
