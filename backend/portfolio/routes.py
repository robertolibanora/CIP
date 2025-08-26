"""
Portfolio API routes
API per gestione portfolio e investimenti
"""

from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection

portfolio_bp = Blueprint("portfolio", __name__)

def get_conn():
    return get_connection()

@portfolio_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route portfolio"""
    if 'user_id' not in session:
        return jsonify({'error': 'Non autorizzato'}), 401

# =====================================================
# API ENDPOINTS PER FRONTEND
# =====================================================

@portfolio_bp.route('/api/investments', methods=['GET'])
def get_investments():
    """API per ottenere investimenti dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id, i.amount, i.status, i.created_at, p.title as project_title
            FROM investments i 
            JOIN projects p ON p.id = i.project_id
            WHERE i.user_id = %s
            ORDER BY i.created_at DESC
        """, (uid,))
        investments = cur.fetchall()
    
    return jsonify({'investments': investments})

@portfolio_bp.route('/api/yields', methods=['GET'])
def get_yields():
    """API per ottenere rendimenti dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT iy.amount, iy.period_end, p.title as project_title
            FROM investment_yields iy
            JOIN investments i ON i.id = iy.investment_id
            JOIN projects p ON p.id = i.project_id
            WHERE i.user_id = %s
            ORDER BY iy.period_end DESC
        """, (uid,))
        yields = cur.fetchall()
    
    return jsonify({'yields': yields})

@portfolio_bp.route('/api/referral-stats', methods=['GET'])
def get_referral_stats():
    """API per ottenere statistiche referral dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) as total_referrals,
                   COUNT(CASE WHEN u.kyc_status = 'verified' THEN 1 END) as verified_referrals
            FROM users u WHERE u.referred_by = %s
        """, (uid,))
        stats = cur.fetchone()
        
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as total_bonus 
            FROM referral_bonuses 
            WHERE receiver_user_id = %s
        """, (uid,))
        bonus = cur.fetchone()
    
    return jsonify({
        'referral_stats': stats,
        'total_bonus': bonus['total_bonus'] if bonus else 0
    })
