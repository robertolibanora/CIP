"""
Validazioni di sicurezza e business logic
Task 1.3: Validazioni, Controlli Sicurezza
"""

import re
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# VALIDAZIONI PASSWORD
# ============================================================================

def validate_password_strength(password: str) -> bool:
    """
    Valida la forza della password secondo criteri di sicurezza
    
    Requisiti minimi:
    - Almeno 8 caratteri
    - Almeno una lettera maiuscola
    - Almeno una lettera minuscola  
    - Almeno un numero
    - Almeno un carattere speciale
    """
    if not password or len(password) < 8:
        return False
    
    # Controlla presenza di almeno una lettera maiuscola
    if not re.search(r'[A-Z]', password):
        return False
    
    # Controlla presenza di almeno una lettera minuscola
    if not re.search(r'[a-z]', password):
        return False
    
    # Controlla presenza di almeno un numero
    if not re.search(r'\d', password):
        return False
    
    # Controlla presenza di almeno un carattere speciale
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', password):
        return False
    
    return True

def validate_password_common(password: str) -> bool:
    """Verifica che la password non sia troppo comune"""
    common_passwords = {
        'password', '123456', '12345678', 'qwerty', 'abc123',
        'password123', 'admin', 'letmein', 'welcome', 'monkey'
    }
    
    return password.lower() not in common_passwords

def generate_strong_password(length: int = 16) -> str:
    """Genera una password forte e sicura"""
    import string
    
    # Caratteri disponibili
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    symbols = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    
    # Assicura almeno un carattere di ogni tipo
    password = [
        secrets.choice(lowercase),
        secrets.choice(uppercase),
        secrets.choice(digits),
        secrets.choice(symbols)
    ]
    
    # Riempi il resto con caratteri casuali
    all_chars = lowercase + uppercase + digits + symbols
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))
    
    # Mischia la password
    secrets.SystemRandom().shuffle(password)
    
    return ''.join(password)

# ============================================================================
# VALIDAZIONI EMAIL
# ============================================================================

def validate_email_format(email: str) -> bool:
    """Valida il formato dell'email"""
    if not email:
        return False
    
    # Pattern regex per email valida (accetta anche IP come domini)
    pattern = r'^[a-zA-Z0-9._%+-]+@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$'
    
    # Verifica pattern base
    if not re.match(pattern, email):
        return False
    
    # Verifica che non ci siano punti consecutivi nella parte locale
    local_part = email.split('@')[0]
    if '..' in local_part:
        return False
        
    return True

def validate_email_domain(email: str, allowed_domains: Optional[list] = None) -> bool:
    """Valida il dominio dell'email"""
    if not validate_email_format(email):
        return False
    
    # Estrai dominio
    domain = email.split('@')[1].lower()
    
    # Se non ci sono domini specifici, accetta tutto
    if not allowed_domains:
        return True
    
    return domain in [d.lower() for d in allowed_domains]

def is_disposable_email(email: str) -> bool:
    """Verifica se l'email è da un servizio temporaneo"""
    disposable_domains = {
        '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
        'tempmail.org', 'throwaway.email', 'yopmail.com'
    }
    
    if not validate_email_format(email):
        return False
    
    domain = email.split('@')[1].lower()
    return domain in disposable_domains

# ============================================================================
# VALIDAZIONI SESSIONE
# ============================================================================

def validate_session_security(session_data: Dict[str, Any]) -> bool:
    """Valida la sicurezza della sessione"""
    required_keys = ['user_id', 'user_role', 'user_name']
    
    # Verifica presenza chiavi richieste
    for key in required_keys:
        if key not in session_data:
            return False
    
    # Verifica tipi di dati
    if not isinstance(session_data['user_id'], int):
        return False
    
    if not isinstance(session_data['user_role'], str):
        return False
    
    # Verifica valori validi
    valid_roles = ['admin', 'investor']
    if session_data['user_role'] not in valid_roles:
        return False
    
    return True

def generate_session_token() -> str:
    """Genera un token di sessione sicuro"""
    return secrets.token_urlsafe(32)

def validate_session_token(token: str) -> bool:
    """Valida un token di sessione"""
    if not token:
        return False
    
    # Verifica lunghezza minima
    if len(token) < 32:
        return False
    
    # Verifica che contenga solo caratteri validi per base64 URL safe
    import string
    valid_chars = string.ascii_letters + string.digits + '-_'
    if not all(c in valid_chars for c in token):
        return False
    
    # Verifica formato (base64 URL safe)
    try:
        import base64
        base64.urlsafe_b64decode(token + '=' * (4 - len(token) % 4))
        return True
    except Exception:
        return False

# ============================================================================
# VALIDAZIONI INPUT
# ============================================================================

def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """Sanitizza input utente per prevenire XSS"""
    if not input_string:
        return ""
    
    # Limita lunghezza
    if len(input_string) > max_length:
        input_string = input_string[:max_length]
    
    # Rimuovi script tags mantenendo il contenuto interno
    input_string = re.sub(r'<script[^>]*>(.*?)</script>', r'\1', input_string, flags=re.IGNORECASE)
    
    # Rimuovi caratteri pericolosi
    dangerous_chars = ['<', '>', '"', "'", '&', 'javascript:', 'vbscript:']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')
    
    return input_string.strip()

def validate_phone_number(phone: str) -> bool:
    """Valida numero di telefono italiano"""
    if not phone:
        return False
    
    # Rimuovi spazi e caratteri speciali
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Pattern per numeri italiani
    patterns = [
        r'^\+39\d{10}$',  # +39 + 10 cifre
        r'^39\d{10}$',    # 39 + 10 cifre
        r'^0\d{9,10}$',   # 0 + 9-10 cifre
        r'^\d{9,10}$'     # 9-10 cifre
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)

def validate_telegram_username(username: str) -> bool:
    """Valida username Telegram"""
    if not username:
        return False
    
    # Username Telegram: 5-32 caratteri, solo lettere, numeri e underscore
    pattern = r'^[a-zA-Z0-9_]{5,32}$'
    return bool(re.match(pattern, username))

# ============================================================================
# VALIDAZIONI BUSINESS LOGIC
# ============================================================================

def validate_kyc_status_transition(current_status: str, new_status: str) -> bool:
    """Valida transizione stato KYC"""
    valid_transitions = {
        'unverified': ['pending'],
        'pending': ['verified', 'rejected'],
        'verified': [],  # Una volta verificato, non può cambiare
        'rejected': ['pending']  # Può ricaricare nuovo documento
    }
    
    current = current_status.lower()
    new = new_status.lower()
    
    return new in valid_transitions.get(current, [])

def validate_user_role_assignment(current_role: str, new_role: str, 
                                assigned_by_admin: bool = False) -> bool:
    """Valida assegnazione ruolo utente"""
    # Solo admin può cambiare ruoli
    if not assigned_by_admin:
        return False
    
    # Ruoli validi
    valid_roles = ['admin', 'investor']
    if new_role not in valid_roles:
        return False
    
    # Non può rimuovere l'ultimo admin
    if current_role == 'admin' and new_role != 'admin':
        # TODO: Verificare se è l'ultimo admin nel sistema
        pass
    
    return True

def validate_referral_code(code: str) -> bool:
    """Valida codice referral"""
    if not code:
        return False
    
    # Codice referral: 6-12 caratteri alfanumerici
    pattern = r'^[a-zA-Z0-9]{6,12}$'
    return bool(re.match(pattern, code))

# ============================================================================
# VALIDAZIONI SICUREZZA AVANZATE
# ============================================================================

def check_password_breach(password: str) -> bool:
    """Verifica se la password è stata compromessa (simulato)"""
    # In produzione, integrare con servizi come HaveIBeenPwned
    # Per ora, simuliamo il controllo
    
    compromised_passwords = {
        'password123', 'admin123', 'qwerty123', '123456789'
    }
    
    return password.lower() in compromised_passwords

def validate_ip_address(ip: str) -> bool:
    """Valida indirizzo IP"""
    import ipaddress
    
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def is_suspicious_activity(user_id: int, action: str, 
                          timestamp: datetime) -> bool:
    """Rileva attività sospette"""
    # Implementazione base per rilevamento anomalie
    # In produzione, usare machine learning o regole più sofisticate
    
    suspicious_patterns = {
        'multiple_login_attempts': 5,  # Tentativi di login
        'rapid_requests': 10,          # Richieste in breve tempo
        'unusual_hours': [0, 1, 2, 3, 4, 5, 6, 23]  # Ore sospette
    }
    
    # Per ora, ritorna sempre False (nessuna attività sospetta)
    # TODO: Implementare logica reale di rilevamento
    return False

# ============================================================================
# UTILITY SICUREZZA
# ============================================================================

def generate_csrf_token() -> str:
    """Genera token CSRF"""
    return secrets.token_hex(32)

def hash_sensitive_data(data: str) -> str:
    """Hash di dati sensibili"""
    return hashlib.sha256(data.encode()).hexdigest()

def generate_secure_filename(original_filename: str) -> str:
    """Genera nome file sicuro per upload"""
    import os
    from datetime import datetime
    
    # Estrai estensione
    name, ext = os.path.splitext(original_filename)
    
    # Genera nome sicuro con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = secrets.token_hex(8)
    
    return f"{timestamp}_{random_suffix}{ext}"

def validate_file_upload(filename: str, mime_type: str, 
                        max_size: int = 16 * 1024 * 1024) -> Tuple[bool, str]:
    """
    Valida upload file
    
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    import os
    
    # Verifica estensione
    allowed_extensions = {'.pdf', '.jpg', '.jpeg', '.png', '.gif'}
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        return False, f"Estensione file non consentita: {file_ext}"
    
    # Verifica MIME type
    allowed_mimes = {
        'application/pdf',
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif'
    }
    
    if mime_type not in allowed_mimes:
        return False, f"Tipo file non consentito: {mime_type}"
    
    # Verifica dimensione (default 16MB)
    # La dimensione effettiva verrà controllata da Flask
    
    return True, "File valido"
