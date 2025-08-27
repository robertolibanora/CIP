"""
CIP Immobiliare - Referral Module
Compartimento stagno per il sistema di referral e bonus
"""

from flask import Blueprint, session, render_template, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Referral
referral_bp = Blueprint("referral", __name__)

def get_conn():
    return get_connection()

@referral_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route referral"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@referral_bp.get("/referral")
def referral():
    """
    Dashboard referral dell'utente
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: users, investments, referral_bonuses
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Dati utente per codice referral - TABELLA: users
        cur.execute("""
            SELECT id, full_name, email, referral_code, created_at
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
        
        # Genera codice referral se non esiste
        if not user_data.get('referral_code'):
            referral_code = 'REF' + str(uid).zfill(6)
            cur.execute("UPDATE users SET referral_code = %s WHERE id = %s", (referral_code, uid))
            user_data['referral_code'] = referral_code
            conn.commit()
        
        # Statistiche referral - TABELLA: users
        cur.execute("""
            SELECT COUNT(*) as total_referrals,
                   COUNT(CASE WHEN u.kyc_status = 'verified' THEN 1 END) as verified_referrals,
                   COUNT(CASE WHEN u.kyc_status != 'verified' THEN 1 END) as pending_referrals
            FROM users u WHERE u.referred_by = %s
        """, (uid,))
        stats = cur.fetchone()
        
        # Lista referral - TABELLE: users + investments
        cur.execute("""
            SELECT u.id, u.full_name, u.email, u.created_at, u.kyc_status,
                   COALESCE(SUM(i.amount), 0) as total_invested
            FROM users u 
            LEFT JOIN investments i ON u.id = i.user_id AND i.status = 'active'
            WHERE u.referred_by = %s
            GROUP BY u.id, u.full_name, u.email, u.created_at, u.kyc_status
            ORDER BY u.created_at DESC
        """, (uid,))
        referrals = cur.fetchall()
        
        # Bonus totali - TABELLA: referral_bonuses
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_bonus 
            FROM referral_bonuses 
            WHERE receiver_user_id = %s
        """, (uid,))
        bonus = cur.fetchone()
    
    return render_template("user/referral.html", 
                         user_id=uid,
                         user=user_data,
                         stats=stats,
                         referrals=referrals,
                         total_bonus=bonus['total_bonus'] if bonus else 0,
                         current_page="referral")
