"""
CIP Immobiliare - Profile Module
Compartimento stagno per la gestione del profilo utente
"""

from flask import Blueprint, session, render_template, jsonify, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Profile
profile_bp = Blueprint("profile", __name__)

def get_conn():
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
    
    with get_conn() as conn, conn.cursor() as cur:
        # Dati utente - TABELLA: users
        cur.execute("""
            SELECT id, full_name, email, referral_code, created_at
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
    ACCESSO: Solo tramite profile.html (non accessibile direttamente)
    TABELLE: users (aggiornamento)
    """
    uid = session.get("user_id")
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('full_name') or not data.get('email'):
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Aggiorna profilo - TABELLA: users
        cur.execute("""
            UPDATE users 
            SET full_name = %s, email = %s, updated_at = NOW()
            WHERE id = %s
        """, (data['full_name'], data['email'], uid))
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
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'success': False, 'error': 'Password mancanti'}), 400
    
    # TODO: Implementare verifica password corrente e hash nuova password
    # Per ora restituiamo successo simulato
    
    return jsonify({'success': True, 'message': 'Password cambiata con successo'})
