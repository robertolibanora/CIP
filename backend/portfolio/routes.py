"""
Portfolio API routes
API per gestione portfolio e investimenti
"""

from flask import Blueprint, request, session, jsonify
import json
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
    """API per ottenere storico ricariche dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id, amount, status, created_at, approved_at,
                unique_key, payment_reference, admin_notes
            FROM deposit_requests 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (uid,))
        
        deposits = cur.fetchall()
        
        # Converti Decimal in float per JSON
        for deposit in deposits:
            deposit['amount'] = float(deposit['amount'])
    
    return jsonify({'deposits': deposits})

@portfolio_bp.route('/api/portfolio/withdrawals', methods=['POST'])
def create_withdrawal_request():
    """API per creare richiesta prelievo da sezioni disponibili"""
    uid = session.get("user_id")
    
    try:
        data = request.get_json()
        
        # Validazioni
        from backend.shared.validators import (
            validate_withdrawal_amount, 
            validate_withdrawal_source, 
            validate_bank_details
        )
        
        amount = validate_withdrawal_amount(data.get('amount'))
        source_section = validate_withdrawal_source(data.get('source_section'))
        bank_details = validate_bank_details(data.get('bank_details'))
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica disponibilità nella sezione selezionata
            cur.execute("""
                SELECT free_capital, referral_bonus, profits
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            
            portfolio = cur.fetchone()
            if not portfolio:
                return jsonify({'error': 'Portafoglio non trovato'}), 404
            
            # Controlla disponibilità
            available_amount = 0
            if source_section == 'free_capital':
                available_amount = portfolio['free_capital']
            elif source_section == 'referral_bonus':
                available_amount = portfolio['referral_bonus']
            elif source_section == 'profits':
                available_amount = portfolio['profits']
            
            if available_amount < amount:
                return jsonify({'error': f'Importo non disponibile in {source_section}. Disponibile: €{available_amount}'}), 400
            
            # Crea richiesta prelievo
            cur.execute("""
                INSERT INTO withdrawal_requests (
                    user_id, amount, source_section, bank_details, status
                ) VALUES (%s, %s, %s, %s, 'pending')
                RETURNING id, amount, source_section, status, created_at
            """, (uid, amount, source_section, json.dumps(bank_details)))
            
            withdrawal = cur.fetchone()
            conn.commit()
            
            return jsonify({
                'withdrawal_request': {
                    'id': withdrawal['id'],
                    'amount': float(withdrawal['amount']),
                    'source_section': withdrawal['source_section'],
                    'status': withdrawal['status'],
                    'created_at': withdrawal['created_at'].isoformat()
                }
            }), 201
            
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@portfolio_bp.route('/api/portfolio/withdrawals', methods=['GET'])
def get_withdrawal_requests():
    """API per ottenere richieste prelievo dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                id, amount, source_section, status, created_at, approved_at,
                admin_notes, bank_details
            FROM withdrawal_requests 
            WHERE user_id = %s
            ORDER BY created_at DESC
        """, (uid,))
        
        withdrawals = cur.fetchall()
        
        # Converti Decimal in float per JSON
        for withdrawal in withdrawals:
            withdrawal['amount'] = float(withdrawal['amount'])
            if withdrawal['bank_details']:
                withdrawal['bank_details'] = json.loads(withdrawal['bank_details'])
    
    return jsonify({'withdrawals': withdrawals})

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
def get_profits_and_yields():
    """API per ottenere profitti e rendimenti accumulati"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni profitti dai rendimenti investimenti
        cur.execute("""
            SELECT 
                p.title as project_title,
                i.amount as invested_amount,
                i.roi_earned as profit,
                ROUND((i.roi_earned / i.amount * 100), 2) as roi_percentage,
                i.completion_date,
                i.status
            FROM investments i
            JOIN projects p ON p.id = i.project_id
            WHERE i.user_id = %s AND i.status = 'completed'
            ORDER BY i.completion_date DESC
        """, (uid,))
        
        profits = cur.fetchall()
        
        # Converti Decimal in float per JSON
        for profit in profits:
            profit['invested_amount'] = float(profit['invested_amount'])
            profit['profit'] = float(profit['profit'])
            profit['roi_percentage'] = float(profit['roi_percentage'])
    
    return jsonify({'profits': profits})
