"""
CIP Immobiliare - Dashboard Module
Compartimento stagno per la dashboard utente
"""

from flask import Blueprint, session, render_template, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Dashboard
dashboard_bp = Blueprint("dashboard", __name__)

def get_conn():
    return get_connection()

@dashboard_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route dashboard"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@dashboard_bp.get("/dashboard")
def dashboard():
    """
    Dashboard principale con overview portfolio e statistiche
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: users, investments, investment_yields, referral_bonuses
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Portfolio overview - TABELLA: investments
        cur.execute("SELECT total_invested, active_count FROM v_user_invested WHERE user_id=%s", (uid,))
        inv = cur.fetchone() or {"total_invested": 0, "active_count": 0}
        
        # Rendimenti totali - TABELLA: investment_yields
        cur.execute("""
            SELECT COALESCE(SUM(iy.amount),0) AS total_yields 
            FROM investment_yields iy 
            JOIN investments i ON i.id=iy.investment_id 
            WHERE i.user_id=%s
        """, (uid,))
        yields = cur.fetchone()
        
        # Bonus referral totali - TABELLA: referral_bonuses
        cur.execute("SELECT bonus_total FROM v_user_bonus WHERE user_id=%s", (uid,))
        bonus = cur.fetchone()
        
        # Investimenti attivi dettagliati - TABELLE: investments + projects
        cur.execute("""
            SELECT i.id, i.amount, i.created_at as date_invested, p.name as project_name,
                   CASE WHEN p.total_amount > 0 THEN (i.amount / p.total_amount * 100) ELSE 0 END as percentage
            FROM investments i 
            JOIN projects p ON p.id = i.project_id 
            WHERE i.user_id = %s AND i.status = 'active'
            ORDER BY i.created_at DESC
        """, (uid,))
        active_investments_data = cur.fetchall()
        
        # Statistiche referral - TABELLA: users
        cur.execute("SELECT COUNT(*) as count FROM users WHERE referred_by = %s", (uid,))
        referred_users_count = cur.fetchone()['count'] or 0
        
        cur.execute("""
            SELECT COALESCE(SUM(i.amount), 0) as total_invested 
            FROM investments i 
            JOIN users u ON u.id = i.user_id 
            WHERE u.referred_by = %s AND i.status IN ('active', 'completed')
        """, (uid,))
        total_referral_investments = cur.fetchone()['total_invested'] or 0
        
        # Dati utente completi - TABELLA: users
        cur.execute("""
            SELECT id, email, full_name, role, referral_code, nome, cognome
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
        referral_code = user_data['referral_code'] if user_data else None
    
    # Calcola valori portfolio
    total_invested = (inv and inv.get('total_invested', 0) or 0) or 0
    total_yields = (yields and yields.get('total_yields', 0) or 0) or 0
    referral_bonus_value = (bonus and bonus.get('bonus_total', 0) or 0) or 0
    
    # Portfolio balance = investimenti + rendimenti + bonus
    portfolio_balance = total_invested + total_yields + referral_bonus_value
    
    # Portfolio change simulato (in futuro calcolare dai dati storici)
    portfolio_change = 2.5  # +2.5%
    
    # Genera link referral
    base_url = request.url_root.rstrip('/')
    referral_link = f"{base_url}/auth/register?ref={referral_code}" if referral_code else f"{base_url}/auth/register"
    
    # Calcola nome da mostrare per saluto
    full_name_value = ((user_data.get("full_name") if user_data else "") or "").strip()
    nome_value = ((user_data.get("nome") if user_data else "") or "").strip()
    greet_name = full_name_value.split()[0] if full_name_value else (nome_value if nome_value else "Utente")

    return render_template("user/dashboard.html", 
                         user=user_data,
                         greet_name=greet_name,
                         total_invested=total_invested,
                         avg_roi=8.5,  # RA medio simulato
                         current_page="dashboard"
                         )
