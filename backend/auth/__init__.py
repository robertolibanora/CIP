"""
Modulo di autenticazione e autorizzazioni
Task 1.3: Middleware KYC, Ruoli e Permessi, Validazioni
"""

from .middleware import (
    KYCRequired,
    login_required,
    admin_required,
    kyc_verified,
    role_required,
    can_user_invest,
    can_user_withdraw,
    can_user_access_portfolio,
    setup_auth_middleware
)

from .decorators import (
    login_required as decorator_login_required,
    admin_required as decorator_admin_required,
    investor_required,
    kyc_verified as decorator_kyc_verified,
    kyc_pending_allowed,
    can_invest,
    can_withdraw,
    can_access_portfolio,
    conditional_access,
    rate_limit
)

from .validators import (
    validate_password_strength,
    validate_password_common,
    generate_strong_password,
    validate_email_format,
    validate_email_domain,
    is_disposable_email,
    validate_session_security,
    generate_session_token,
    validate_session_token,
    sanitize_input,
    validate_phone_number,
    validate_telegram_username,
    validate_kyc_status_transition,
    validate_user_role_assignment,
    validate_referral_code,
    check_password_breach,
    validate_ip_address,
    is_suspicious_activity,
    generate_csrf_token,
    hash_sensitive_data,
    generate_secure_filename,
    validate_file_upload
)

__all__ = [
    # Middleware
    'KYCRequired',
    'login_required',
    'admin_required', 
    'kyc_verified',
    'role_required',
    'can_user_invest',
    'can_user_withdraw',
    'can_user_access_portfolio',
    'setup_auth_middleware',
    
    # Decoratori
    'decorator_login_required',
    'decorator_admin_required',
    'investor_required',
    'decorator_kyc_verified',
    'kyc_pending_allowed',
    'can_invest',
    'can_withdraw',
    'can_access_portfolio',
    'conditional_access',
    'rate_limit',
    
    # Validatori
    'validate_password_strength',
    'validate_password_common',
    'generate_strong_password',
    'validate_email_format',
    'validate_email_domain',
    'is_disposable_email',
    'validate_session_security',
    'generate_session_token',
    'validate_session_token',
    'sanitize_input',
    'validate_phone_number',
    'validate_telegram_username',
    'validate_kyc_status_transition',
    'validate_user_role_assignment',
    'validate_referral_code',
    'check_password_breach',
    'validate_ip_address',
    'is_suspicious_activity',
    'generate_csrf_token',
    'hash_sensitive_data',
    'generate_secure_filename',
    'validate_file_upload'
]
