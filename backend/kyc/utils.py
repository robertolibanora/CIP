"""
Utils per gestione file KYC
"""
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app


def allowed_ext(filename: str) -> bool:
    """Verifica se l'estensione del file è consentita"""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[-1].lower()
    return ext in current_app.config.get('ALLOWED_KYC_EXTENSIONS', {'pdf', 'png', 'jpg', 'jpeg'})


def save_kyc_file(file_storage, user_id: int) -> str:
    """
    Salva un file KYC e ritorna il path relativo per il DB
    
    Args:
        file_storage: FileStorage object da Flask
        user_id: ID dell'utente
        
    Returns:
        str: Path relativo del file salvato (es: "3/abc123.pdf")
        
    Raises:
        ValueError: Se il file non è valido
    """
    if not file_storage:
        return None
        
    filename = secure_filename(file_storage.filename or "")
    if not filename or not allowed_ext(filename):
        raise ValueError("Formato file non supportato. Usa PDF, PNG o JPG")
        
    # Estrai estensione
    ext = filename.rsplit('.', 1)[-1].lower()
    
    # Genera nome univoco
    uid = uuid.uuid4().hex
    rel_path = f"{user_id}/{uid}.{ext}"
    
    # Path assoluto per salvataggio
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    abs_path = os.path.join(upload_folder, rel_path)
    
    # Crea directory utente se non esiste
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    
    # Salva il file
    file_storage.save(abs_path)
    
    current_app.logger.info(f"File KYC salvato: {rel_path}")
    return rel_path


def get_kyc_file_url(rel_path: str) -> str:
    """Genera URL per visualizzare un file KYC"""
    if not rel_path:
        return None
    return f"/uploads/kyc/{rel_path}"
