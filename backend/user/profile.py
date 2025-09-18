"""
CIP Immobiliare - Profile Module
Compartimento stagno per la gestione del profilo utente
"""

from flask import Blueprint, session, render_template, jsonify, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Profile
profile_bp = Blueprint("profile", __name__)

def get_connection():
    from backend.shared.database import get_connection
    return get_connection()

@profile_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route profile"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@profile_bp.get("/profile")
def profile():
    """
    Gestione profilo utente
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: users (lettura e scrittura)
    """
    uid = session.get("user_id")
    
    with get_connection() as conn, conn.cursor() as cur:
        # Dati utente completi - TABELLA: users
        cur.execute("""
            SELECT id, full_name, email, nome, cognome, telefono, nome_telegram, 
                   address, currency_code, referral_code, created_at
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
    
    return render_template("user/profile.html", 
                         user_id=uid,
                         user=user_data,
                         current_page="profile")

@profile_bp.post("/profile/update")
def profile_update():
    """
    Aggiornamento dati profilo
    ACCESSO: Solo tramite profile.html e portfolio.html
    TABELLE: users (aggiornamento)
    """
    uid = session.get("user_id")
    data = request.get_json()
    
    # Validazione dati base
    if not data:
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    # Gestisce sia il form profile.html che portfolio.html
    update_fields = []
    update_values = []
    
    # Campi del form profile.html
    if 'full_name' in data and data['full_name']:
        update_fields.append('full_name = %s')
        update_values.append(data['full_name'])
    
    if 'email' in data and data['email']:
        update_fields.append('email = %s')
        update_values.append(data['email'])
    
    # Campi del form portfolio.html
    if 'nome' in data and data['nome']:
        update_fields.append('nome = %s')
        update_values.append(data['nome'])
    
    if 'cognome' in data and data['cognome']:
        update_fields.append('cognome = %s')
        update_values.append(data['cognome'])
    
    if 'telefono' in data and data['telefono']:
        update_fields.append('telefono = %s')
        update_values.append(data['telefono'])
    
    if 'nome_telegram' in data:
        update_fields.append('nome_telegram = %s')
        update_values.append(data['nome_telegram'])
    
    if 'address' in data:
        update_fields.append('address = %s')
        update_values.append(data['address'])
    
    if 'currency_code' in data and data['currency_code']:
        update_fields.append('currency_code = %s')
        update_values.append(data['currency_code'])
    
    if not update_fields:
        return jsonify({'success': False, 'error': 'Nessun campo valido da aggiornare'}), 400
    
    # Aggiungi updated_at e user_id
    update_fields.append('updated_at = NOW()')
    update_values.append(uid)
    
    with get_connection() as conn, conn.cursor() as cur:
        # Aggiorna profilo - TABELLA: users
        query = f"""
            UPDATE users 
            SET {', '.join(update_fields)}
            WHERE id = %s
        """
        cur.execute(query, update_values)
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Profilo aggiornato con successo'})

@profile_bp.post("/profile/change-password")
def change_password():
    """
    Cambio password utente
    ACCESSO: Solo tramite profile.html (non accessibile direttamente)
    TABELLE: users (aggiornamento password)
    """
    uid = session.get("user_id")
    if not uid:
        return jsonify({'success': False, 'error': 'Non autenticato'}), 401
    
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'success': False, 'error': 'Password mancanti'}), 400
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    # Validazione lunghezza password
    if len(new_password) < 6:
        return jsonify({'success': False, 'error': 'La nuova password deve essere di almeno 6 caratteri'}), 400
    
    with get_connection() as conn, conn.cursor() as cur:
        # Verifica password corrente
        cur.execute("SELECT password_hash, password_reset_required FROM users WHERE id = %s", (uid,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'error': 'Utente non trovato'}), 404
        
        # Verifica password corrente usando SHA-256
        import hashlib
        if user['password_hash'] != hashlib.sha256(current_password.encode()).hexdigest():
            return jsonify({'success': False, 'error': 'Password corrente non corretta'}), 400
        
        # Hash della nuova password
        new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        # Aggiorna password e resetta il flag password_reset_required
        cur.execute("""
            UPDATE users 
            SET password_hash = %s, password_reset_required = false, updated_at = NOW()
            WHERE id = %s
        """, (new_password_hash, uid))
        
        # Log dell'azione
        cur.execute("""
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'password_change', 'user', %s, 'Password cambiata dall''utente')
        """, (uid, uid))
    
    return jsonify({'success': True, 'message': 'Password cambiata con successo'})
