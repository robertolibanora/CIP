import os
from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template
from backend.shared.database import get_connection

user_bp = Blueprint("user", __name__)

def get_conn():
    return get_connection()

@user_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route user"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

# =====================================================
# 1. DASHBOARD - Vista generale del portfolio e statistiche
# =====================================================

@user_bp.get("/dashboard")
def dashboard():
    """Dashboard principale con overview portfolio e statistiche"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Portfolio overview
        cur.execute("SELECT total_invested, active_count FROM v_user_invested WHERE user_id=%s", (uid,))
        inv = cur.fetchone() or {"total_invested": 0, "active_count": 0}
        
        # Rendimenti totali
        cur.execute("""
            SELECT COALESCE(SUM(iy.amount),0) AS total_yields 
            FROM investment_yields iy 
            JOIN investments i ON i.id=iy.investment_id 
            WHERE i.user_id=%s
        """, (uid,))
        yields = cur.fetchone()
        
        # Bonus referral totali
        cur.execute("SELECT bonus_total FROM v_user_bonus WHERE user_id=%s", (uid,))
        bonus = cur.fetchone()
        
        # Investimenti attivi dettagliati
        cur.execute("""
            SELECT i.id, i.amount, i.created_at as date_invested, p.title as project_name,
                   CASE WHEN p.target_amount > 0 THEN (i.amount / p.target_amount * 100) ELSE 0 END as percentage
            FROM investments i 
            JOIN projects p ON p.id = i.project_id 
            WHERE i.user_id = %s AND i.status = 'active'
            ORDER BY i.created_at DESC
        """, (uid,))
        active_investments_data = cur.fetchall()
        
        # Statistiche referral
        cur.execute("SELECT COUNT(*) as count FROM users WHERE referred_by = %s", (uid,))
        referred_users_count = cur.fetchone()['count'] or 0
        
        cur.execute("""
            SELECT COALESCE(SUM(i.amount), 0) as total_invested 
            FROM investments i 
            JOIN users u ON u.id = i.user_id 
            WHERE u.referred_by = %s AND i.status IN ('active', 'completed')
        """, (uid,))
        total_referral_investments = cur.fetchone()['total_invested'] or 0
        
        # Referral code utente
        cur.execute("SELECT referral_code FROM users WHERE id = %s", (uid,))
        user_data = cur.fetchone()
        referral_code = user_data['referral_code'] if user_data else None
    
    # Calcola valori portfolio
    total_invested = inv.get('total_invested', 0) or 0
    total_yields = (yields and yields['total_yields'] or 0) or 0
    referral_bonus_value = (bonus and bonus['bonus_total'] or 0) or 0
    
    # Portfolio balance = investimenti + rendimenti + bonus
    portfolio_balance = total_invested + total_yields + referral_bonus_value
    
    # Portfolio change simulato (in futuro calcolare dai dati storici)
    portfolio_change = 2.5  # +2.5%
    
    # Genera link referral
    base_url = request.url_root.rstrip('/')
    referral_link = f"{base_url}/auth/register?ref={referral_code}" if referral_code else f"{base_url}/auth/register"
    
    return render_template("user/dashboard.html", 
                         user_id=uid,
                         total_invested=total_invested,
                         active_investments=active_investments_data,
                         total_yields=total_yields,
                         referral_bonus=referral_bonus_value,
                         portfolio_balance=portfolio_balance,
                         portfolio_change=portfolio_change,
                         avg_roi=8.5,  # ROI medio simulato
                         active_projects_count=len(active_investments_data),
                         last_investment_date=None,  # Per ora None
                         recent_activities=[],  # Per ora vuoto
                         # Variabili per referral card
                         referral_earnings=referral_bonus_value,
                         referred_users=[{'id': i} for i in range(referred_users_count)],
                         total_referral_investments=total_referral_investments,
                         referral_link=referral_link
                         )

# =====================================================
# 2. PORTAFOGLIO - Dettaglio investimenti e rendimenti
# =====================================================

@user_bp.get("/portfolio")
def portfolio():
    """Portafoglio dettagliato con investimenti attivi e completati"""
    uid = session.get("user_id")
    tab = request.args.get("tab", "attivi")
    statuses = ('active',) if tab == 'attivi' else ('completed','cancelled','rejected')
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id, p.title, i.amount, i.status, i.created_at
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.user_id=%s AND i.status = ANY(%s)
            ORDER BY i.created_at DESC
        """, (uid, list(statuses)))
        rows = cur.fetchall()
    
    return render_template("user/portfolio.html", 
                         user_id=uid,
                         tab=tab,
                         investments=rows)

@user_bp.get("/portfolio/<int:investment_id>")
def portfolio_detail(investment_id):
    """Dettaglio specifico di un investimento"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.*, p.title AS project_title
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.id=%s AND i.user_id=%s
        """, (investment_id, uid))
        inv = cur.fetchone()
        
        cur.execute("""
            SELECT * FROM investment_yields 
            WHERE investment_id=%s 
            ORDER BY period_end DESC
        """, (investment_id,))
        yields = cur.fetchall()
    
    return jsonify({"investment": inv, "yields": yields})

# =====================================================
# 3. PROGETTI - Lista e dettagli dei progetti disponibili
# =====================================================

@user_bp.get("/projects")
def projects():
    """Lista progetti disponibili per investimento"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT p.id, p.title, p.description, p.target_amount, p.raised_amount,
                   p.status, p.created_at, p.code
            FROM projects p 
            WHERE p.status = 'active'
            ORDER BY p.created_at DESC
        """)
        projects = cur.fetchall()
        
        # Calcola percentuale completamento
        for project in projects:
            if project['target_amount'] and project['target_amount'] > 0:
                project['completion_percent'] = min(100, int((project['raised_amount'] / project['target_amount']) * 100))
            else:
                project['completion_percent'] = 0
            
            # Aggiungi campi mancanti per compatibilità template
            project['location'] = 'N/A'  # Non presente nello schema attuale
            project['expected_yield'] = 0  # Non presente nello schema attuale
    
    return render_template("user/projects.html", 
                         user_id=uid,
                         projects=projects)

# Rota per dettaglio progetto rimossa - ora gestito tramite modal in projects.html

# =====================================================
# 4. REFERRAL - Sistema di referral e bonus
# =====================================================

@user_bp.get("/referral")
def referral():
    """Dashboard referral dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Statistiche referral
        cur.execute("""
            SELECT COUNT(*) as total_referrals,
                   COUNT(CASE WHEN u.kyc_status = 'verified' THEN 1 END) as verified_referrals,
                   COUNT(CASE WHEN u.kyc_status != 'verified' THEN 1 END) as pending_referrals
            FROM users u WHERE u.referred_by = %s
        """, (uid,))
        stats = cur.fetchone()
        
        # Lista referral
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
        
        # Bonus totali
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_bonus 
            FROM referral_bonuses 
            WHERE receiver_user_id = %s
        """, (uid,))
        bonus = cur.fetchone()
    
    return render_template("user/referral.html", 
                         user_id=uid,
                         stats=stats,
                         referrals=referrals,
                         total_bonus=bonus['total_bonus'] if bonus else 0)

# =====================================================
# 5. PROFILO - Gestione account utente
# =====================================================

@user_bp.get("/profile")
def profile():
    """Gestione profilo utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, full_name, email, referral_code, created_at
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
    
    return render_template("user/profile.html", 
                         user_id=uid,
                         user=user_data)

@user_bp.post("/profile/update")
def profile_update():
    """Aggiornamento dati profilo"""
    uid = session.get("user_id")
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('full_name') or not data.get('email'):
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE users 
            SET full_name = %s, email = %s, updated_at = NOW()
            WHERE id = %s
        """, (data['full_name'], data['email'], uid))
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Profilo aggiornato con successo'})

@user_bp.post("/profile/change-password")
def change_password():
    """Cambio password utente"""
    uid = session.get("user_id")
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'success': False, 'error': 'Password mancanti'}), 400
    
    # TODO: Implementare verifica password corrente e hash nuova password
    # Per ora restituiamo successo simulato
    
    return jsonify({'success': True, 'message': 'Password cambiata con successo'})
