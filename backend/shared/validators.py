import re
from decimal import Decimal

# Classe ValidationError semplice
class ValidationError(Exception):
    """Eccezione per errori di validazione"""
    pass

def validate_email(email):
    """Valida formato email"""
    if not email:
        raise ValidationError("Email richiesta")
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise ValidationError("Formato email non valido")
    
    return email.lower().strip()

def validate_password(password):
    """Valida password"""
    if not password:
        raise ValidationError("Password richiesta")
    
    if len(password) < 8:
        raise ValidationError("Password deve essere di almeno 8 caratteri")
    
    if len(password) > 128:
        raise ValidationError("Password troppo lunga")
    
    return password

def validate_amount(amount):
    """Valida importo monetario"""
    if not amount:
        raise ValidationError("Importo richiesto")
    
    try:
        amount_decimal = Decimal(str(amount))
        if amount_decimal <= 0:
            raise ValidationError("Importo deve essere positivo")
        if amount_decimal > 999999999.99:
            raise ValidationError("Importo troppo elevato")
        return amount_decimal
    except (ValueError, TypeError):
        raise ValidationError("Importo non valido")

def validate_phone(phone):
    """Valida numero di telefono"""
    if not phone:
        return None
    
    # Rimuovi spazi e caratteri speciali
    phone_clean = re.sub(r'[^\d+]', '', phone)
    
    if len(phone_clean) < 8:
        raise ValidationError("Numero di telefono troppo corto")
    
    if len(phone_clean) > 15:
        raise ValidationError("Numero di telefono troppo lungo")
    
    return phone_clean

def validate_currency_code(currency_code):
    """Valida codice valuta"""
    if not currency_code:
        return 'EUR'
    
    valid_currencies = ['EUR', 'USD', 'GBP', 'CHF']
    if currency_code.upper() not in valid_currencies:
        raise ValidationError(f"Valuta non supportata. Usa una di: {', '.join(valid_currencies)}")
    
    return currency_code.upper()

def validate_project_status(status):
    """Valida stato progetto"""
    valid_statuses = ['draft', 'active', 'funded', 'in_progress', 'completed', 'cancelled']
    if status not in valid_statuses:
        raise ValidationError(f"Stato non valido. Usa uno di: {', '.join(valid_statuses)}")
    return status

def validate_investment_status(status):
    """Valida stato investimento"""
    valid_statuses = ['pending', 'approved', 'rejected', 'active', 'completed', 'cancelled']
    if status not in valid_statuses:
        raise ValidationError(f"Stato non valido. Usa uno di: {', '.join(valid_statuses)}")
    return status

def validate_kyc_status(status):
    """Valida stato KYC"""
    valid_statuses = ['unverified', 'pending', 'verified', 'rejected']
    if status not in valid_statuses:
        raise ValidationError(f"Stato KYC non valido. Usa uno di: {', '.join(valid_statuses)}")
    return status

def validate_priority(priority):
    """Valida priorità notifica"""
    valid_priorities = ['low', 'medium', 'high', 'urgent']
    if priority not in valid_priorities:
        raise ValidationError(f"Priorità non valida. Usa una di: {', '.join(valid_priorities)}")
    return priority

def validate_file_upload(file, allowed_extensions=None, max_size_mb=16):
    """Valida upload file"""
    if not file:
        return None
    
    if not file.filename:
        raise ValidationError("Nome file richiesto")
    
    # Estensioni permesse
    if allowed_extensions is None:
        allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
    
    file_ext = file.filename.lower().rsplit('.', 1)[1] if '.' in file.filename else ''
    if f'.{file_ext}' not in allowed_extensions:
        raise ValidationError(f"Tipo file non supportato. Estensioni permesse: {', '.join(allowed_extensions)}")
    
    # Dimensione file
    file.seek(0, 2)  # Vai alla fine del file
    file_size = file.tell()
    file.seek(0)  # Torna all'inizio
    
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        raise ValidationError(f"File troppo grande. Dimensione massima: {max_size_mb}MB")
    
    return file

def sanitize_string(text, max_length=255):
    """Pulisce e valida stringa"""
    if not text:
        return None
    
    # Rimuovi caratteri pericolosi
    text = re.sub(r'[<>"\']', '', str(text))
    text = text.strip()
    
    if len(text) > max_length:
        text = text[:max_length]
    
    return text

def validate_date_range(start_date, end_date):
    """Valida intervallo date"""
    if start_date and end_date:
        if start_date >= end_date:
            raise ValidationError("Data inizio deve essere precedente alla data fine")
    
    return start_date, end_date

def validate_withdrawal_amount(amount):
    """Valida importo prelievo (minimo 50 dollari)"""
    if not amount:
        raise ValidationError("Importo prelievo richiesto")
    
    try:
        amount_decimal = Decimal(str(amount))
        if amount_decimal < Decimal('50.00'):
            raise ValidationError("Importo minimo prelievo: 50 dollari")
        if amount_decimal > 999999999.99:
            raise ValidationError("Importo troppo elevato")
        return amount_decimal
    except (ValueError, TypeError):
        raise ValidationError("Importo prelievo non valido")

def validate_withdrawal_source(source_section):
    """Valida sezione fonte prelievo"""
    if not source_section:
        raise ValidationError("Sezione fonte prelievo richiesta")
    
    valid_sections = ['free_capital', 'referral_bonus', 'profits']
    if source_section not in valid_sections:
        raise ValidationError(f"Sezione fonte non valida. Usa una di: {', '.join(valid_sections)}")
    
    return source_section

def validate_bank_details(bank_details):
    """Valida dettagli bancari per prelievo"""
    if not bank_details:
        raise ValidationError("Dettagli bancari richiesti")
    
    required_fields = ['iban', 'account_holder', 'bank_name']
    for field in required_fields:
        if not bank_details.get(field):
            raise ValidationError(f"Campo {field} richiesto nei dettagli bancari")
    
    # Validazione IBAN base
    iban = bank_details['iban'].replace(' ', '').upper()
    if len(iban) < 15 or len(iban) > 34:
        raise ValidationError("IBAN non valido")
    
    return bank_details

def validate_wallet_address(wallet_address, network='BEP20'):
    """Valida indirizzo wallet USDT"""
    if not wallet_address:
        raise ValidationError("Indirizzo wallet richiesto")
    
    wallet_address = wallet_address.strip()
    
    if network.upper() == 'BEP20':
        # Validazione indirizzo BEP20 (Binance Smart Chain)
        if not wallet_address.startswith('0x'):
            raise ValidationError("Indirizzo BEP20 deve iniziare con 0x")
        if len(wallet_address) != 42:
            raise ValidationError("Indirizzo BEP20 deve essere di 42 caratteri")
        if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
            raise ValidationError("Indirizzo BEP20 non valido")
    
    elif network.upper() == 'ERC20':
        # Validazione indirizzo ERC20 (Ethereum)
        if not wallet_address.startswith('0x'):
            raise ValidationError("Indirizzo ERC20 deve iniziare con 0x")
        if len(wallet_address) != 42:
            raise ValidationError("Indirizzo ERC20 deve essere di 42 caratteri")
        if not re.match(r'^0x[a-fA-F0-9]{40}$', wallet_address):
            raise ValidationError("Indirizzo ERC20 non valido")
    
    elif network.upper() == 'TRC20':
        # Validazione indirizzo TRC20 (Tron)
        if not wallet_address.startswith('T'):
            raise ValidationError("Indirizzo TRC20 deve iniziare con T")
        if len(wallet_address) != 34:
            raise ValidationError("Indirizzo TRC20 deve essere di 34 caratteri")
        if not re.match(r'^T[a-zA-Z0-9]{33}$', wallet_address):
            raise ValidationError("Indirizzo TRC20 non valido")
    
    else:
        raise ValidationError(f"Network {network} non supportato")
    
    return wallet_address

def validate_wallet_network(network):
    """Valida network wallet"""
    if not network:
        return 'BEP20'
    
    valid_networks = ['BEP20', 'ERC20', 'TRC20']
    network_upper = network.upper()
    if network_upper not in valid_networks:
        raise ValidationError(f"Network non supportato. Usa uno di: {', '.join(valid_networks)}")
    
    return network_upper
