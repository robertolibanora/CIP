"""
Modulo Portfolio - Gestione investimenti e referral
Versione semplificata per la nuova struttura
"""

from flask import Blueprint, request, jsonify, session, current_app
from backend.shared.database import get_connection

portfolio_bp = Blueprint('portfolio', __name__)

def get_db_connection():
    """Ottiene connessione al database"""
    return get_connection()

def require_login():
    """Verifica che l'utente sia loggato"""
    if 'user_id' not in session:
        return False
    return True

# =====================================================
# API PORTFOLIO UTENTE
# =====================================================

@portfolio_bp.route('/overview', methods=['GET'])
def get_portfolio_overview():
    """Ottiene overview completo del portfolio utente"""
    if not require_login():
        return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Portfolio base
        cur.execute("""
            SELECT * FROM user_portfolio_view 
            WHERE user_id = %s
        """, (user_id,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            # Crea portfolio se non esiste
            cur.execute("""
                INSERT INTO user_portfolio (user_id, balance, total_invested, total_earned)
                VALUES (%s, 0.00, 0.00, 0.00)
                RETURNING *
            """, (user_id,))
            portfolio = cur.fetchone()
        
        # Investimenti attivi
        cur.execute("""
            SELECT i.*, p.title as project_name, p.status as project_status
            FROM investments i
            JOIN projects p ON i.project_id = p.id
            WHERE i.user_id = %s AND i.status = 'active'
            ORDER BY i.created_at DESC
        """, (user_id,))
        active_investments = cur.fetchall()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'portfolio': {
                'balance': float(portfolio['balance']) if portfolio['balance'] else 0.0,
                'total_invested': float(portfolio['total_invested']) if portfolio['total_invested'] else 0.0,
                'total_earned': float(portfolio['total_earned']) if portfolio['total_earned'] else 0.0,
                'active_investments_count': len(active_investments)
            },
            'active_investments': [dict(inv) for inv in active_investments]
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore portfolio overview: {str(e)}")
        return jsonify({'success': False, 'error': 'Errore interno del server'}), 500

@portfolio_bp.route('/investments', methods=['GET'])
def get_investments():
    """Ottiene lista investimenti utente"""
    if not require_login():
        return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
    
    try:
        user_id = session['user_id']
        status = request.args.get('status', 'all')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if status == 'all':
            cur.execute("""
                SELECT i.*, p.title as project_name, p.status as project_status
                FROM investments i
                JOIN projects p ON i.project_id = p.id
                WHERE i.user_id = %s
                ORDER BY i.created_at DESC
            """, (user_id,))
        else:
            cur.execute("""
                SELECT i.*, p.title as project_name, p.status as project_status
                FROM investments i
                JOIN projects p ON i.project_id = p.id
                WHERE i.user_id = %s AND i.status = %s
                ORDER BY i.created_at DESC
            """, (user_id, status))
        
        investments = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'investments': [dict(inv) for inv in investments]
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore get investments: {str(e)}")
        return jsonify({'success': False, 'error': 'Errore interno del server'}), 500

# =====================================================
# API REFERRAL
# =====================================================

@portfolio_bp.route('/referral/overview', methods=['GET'])
def get_referral_overview():
    """Ottiene overview del sistema referral"""
    if not require_login():
        return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Codice referral
        cur.execute("""
            SELECT code FROM referral_codes WHERE user_id = %s
        """, (user_id,))
        referral_code = cur.fetchone()
        
        # Utenti invitati
        cur.execute("""
            SELECT COUNT(*) as total_referrals FROM referrals WHERE referrer_id = %s
        """, (user_id,))
        total_referrals = cur.fetchone()
        
        # Commissioni totali
        cur.execute("""
            SELECT COALESCE(SUM(commission_amount), 0) as total_commission 
            FROM referral_commissions WHERE referrer_id = %s
        """, (user_id,))
        total_commission = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'referral_code': referral_code['code'] if referral_code else None,
            'total_referrals': total_referrals['total_referrals'] if total_referrals else 0,
            'total_commission': float(total_commission['total_commission']) if total_commission else 0.0
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore referral overview: {str(e)}")
        return jsonify({'success': False, 'error': 'Errore interno del server'}), 500

@portfolio_bp.route('/referral/commissions', methods=['GET'])
def get_referral_commissions():
    """Ottiene storico commissioni referral"""
    if not require_login():
        return jsonify({'success': False, 'error': 'Non autorizzato'}), 401
    
    try:
        user_id = session['user_id']
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT rc.*, p.title as project_name
            FROM referral_commissions rc
            JOIN projects p ON rc.project_id = p.id
            WHERE rc.referrer_id = %s
            ORDER BY rc.created_at DESC
        """, (user_id,))
        
        commissions = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'commissions': [dict(comm) for comm in commissions]
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore referral commissions: {str(e)}")
        return jsonify({'success': False, 'error': 'Errore interno del server'}), 500
