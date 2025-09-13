"""
Portfolio API routes
API per gestione portfolio e investimenti
"""

from flask import Blueprint, request, session, jsonify
import json
from backend.shared.database import get_connection
from backend.shared.validators import ValidationError

# Evita conflitti con blueprint user 'portfolio'
portfolio_bp = Blueprint("portfolio_api2", __name__)

def get_conn():
    return get_connection()


def ensure_deposits_schema(cur):
    pass

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
            SELECT i.id, i.amount, i.status, i.created_at, p.name as project_title
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
            SELECT iy.amount, iy.period_end, p.name as project_title
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

# =====================================================
# API PER 4 SEZIONI PORTFOLIO
# =====================================================

@portfolio_bp.route('/api/portfolio/4-sections', methods=['GET'])
def get_portfolio_4_sections():
    """API per ottenere le 4 sezioni del portafoglio utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni portafoglio utente con 4 sezioni
        cur.execute("""
            SELECT 
                free_capital,
                invested_capital,
                referral_bonus,
                profits,
                created_at,
                updated_at
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        
        portfolio = cur.fetchone()
        
        if not portfolio:
            # Crea portafoglio vuoto se non esiste
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                VALUES (%s, 0.00, 0.00, 0.00, 0.00)
                RETURNING free_capital, invested_capital, referral_bonus, profits, created_at, updated_at
            """, (uid,))
            portfolio = cur.fetchone()
            conn.commit()
        
        # Calcola totali
        total_available = portfolio['free_capital'] + portfolio['referral_bonus'] + portfolio['profits']
        total_balance = total_available + portfolio['invested_capital']
        
        return jsonify({
            'portfolio': {
                'free_capital': float(portfolio['free_capital']),
                'invested_capital': float(portfolio['invested_capital']),
                'referral_bonus': float(portfolio['referral_bonus']),
                'profits': float(portfolio['profits']),
                'total_available': float(total_available),
                'total_balance': float(total_balance),
                'last_updated': portfolio['updated_at'].isoformat() if portfolio['updated_at'] else None
            }
        })

@portfolio_bp.route('/api/portfolio/deposits', methods=['GET'])
def get_deposit_history():
    return jsonify({'deposits': []})

@portfolio_bp.route('/api/portfolio/deposits', methods=['POST'])
def create_deposit_request():
    return jsonify({'error': 'Funzione deposito disabilitata'}), 404

@portfolio_bp.route('/api/portfolio/withdrawals', methods=['POST'])
def create_withdrawal_request():
    """API per creare richiesta prelievo - In fase di sviluppo"""
    return jsonify({'error': 'Sezione prelievi in fase di sviluppo'}), 404

@portfolio_bp.route('/api/portfolio/withdrawals', methods=['GET'])
def get_withdrawal_requests():
    """API per ottenere richieste prelievo - In fase di sviluppo"""
    return jsonify({'error': 'Sezione prelievi in fase di sviluppo'}), 404

@portfolio_bp.route('/api/portfolio/movements', methods=['GET'])
def get_capital_movements():
    """API per ottenere movimenti capitali tra sezioni portafoglio"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id, type, amount, balance_before, balance_after,
                description, reference_type, status, created_at
            FROM portfolio_transactions 
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 50
        """, (uid,))
        
        movements = cur.fetchall()
        
        # Converti Decimal in float per JSON
        for movement in movements:
            movement['amount'] = float(movement['amount'])
            movement['balance_before'] = float(movement['balance_before'])
            movement['balance_after'] = float(movement['balance_after'])
    
    return jsonify({'movements': movements})

@portfolio_bp.route('/api/portfolio/profits', methods=['GET'])
def get_profits_movements():
    """API per ottenere i movimenti della sezione profitti"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni i movimenti della sezione profitti
        cur.execute("""
            SELECT 
                pt.id,
                pt.type,
                pt.amount,
                pt.balance_before,
                pt.balance_after,
                pt.description,
                pt.created_at,
                pt.status
            FROM portfolio_transactions pt
            WHERE pt.user_id = %s 
            AND (pt.type = 'roi' OR pt.description LIKE '%profitti%' OR pt.description LIKE '%profit%')
            ORDER BY pt.created_at DESC
        """, (uid,))
        
        movements = cur.fetchall()
        
        # Ottieni il saldo attuale dei profitti
        cur.execute("""
            SELECT profits FROM user_portfolios WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        current_balance = float(portfolio['profits']) if portfolio else 0.0
        
        # Calcola totali
        total_entries = sum(float(m['amount']) for m in movements if m['type'] == 'roi')
        total_exits = sum(float(m['amount']) for m in movements if 'withdrawal' in m['description'].lower() or 'prelievo' in m['description'].lower())
        
        # Converti Decimal in float per JSON
        for movement in movements:
            movement['amount'] = float(movement['amount'])
            movement['balance_before'] = float(movement['balance_before'])
            movement['balance_after'] = float(movement['balance_after'])
    
    return jsonify({
        'movements': movements,
        'current_balance': current_balance,
        'summary': {
            'total_entries': total_entries,
            'total_exits': total_exits,
            'net_profit': total_entries - total_exits
        }
    })

