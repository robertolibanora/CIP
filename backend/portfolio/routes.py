"""
Modulo Portfolio - Gestione investimenti e referral
Versione semplificata per la nuova struttura
"""

from flask import Blueprint, request, jsonify, session, current_app
from datetime import datetime, timedelta
import os

portfolio_bp = Blueprint('portfolio', __name__)

def get_db_connection():
    """Ottiene connessione al database"""
    from backend.shared.database import get_connection
    return get_connection()

def require_login():
    """Verifica che l'utente sia loggato"""
    if 'user_id' not in session:
        return False
    return True

# =====================================================
# ENDPOINT PER DATI DI TEST (NON RICHIEDE LOGIN)
# =====================================================

@portfolio_bp.route('/test/seed', methods=['POST'])
def seed_test_data():
    """Inserisce dati di test nel database per sviluppo e testing (non richiede login)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Inserisce utenti di test
        test_users = [
            ('test.user1@example.com', 'Test User 1', 'investor'),
            ('test.user2@example.com', 'Test User 2', 'investor'),
            ('test.admin@example.com', 'Test Admin', 'admin'),
            ('test.investor@example.com', 'Test Investor', 'investor')
        ]
        
        user_ids = []
        for email, name, role in test_users:
            cur.execute("""
                INSERT INTO users (email, password_hash, full_name, role, kyc_status)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET 
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role
                RETURNING id
            """, (email, 'test_hash_' + email, name, role, 'verified'))
            result = cur.fetchone()
            user_ids.append(result['id'])
        
        # Inserisce progetti di test
        test_projects = [
            ('PROJ001', 'Progetto Residenziale Milano', 'Edificio residenziale di lusso nel centro di Milano', 'active', 500000.00, 250000.00),
            ('PROJ002', 'Centro Commerciale Roma', 'Centro commerciale moderno nella periferia di Roma', 'funded', 800000.00, 800000.00),
            ('PROJ003', 'Hotel Venezia', 'Hotel boutique nel cuore di Venezia', 'in_progress', 1200000.00, 900000.00),
            ('PROJ004', 'Uffici Torino', 'Complesso di uffici a Torino', 'draft', 600000.00, 0.00)
        ]
        
        project_ids = []
        for code, title, description, status, target, raised in test_projects:
            cur.execute("""
                INSERT INTO projects (code, title, description, status, target_amount, raised_amount, start_date, end_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET 
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    target_amount = EXCLUDED.target_amount,
                    raised_amount = EXCLUDED.raised_amount
                RETURNING id
            """, (code, title, description, status, target, raised, '2024-01-01', '2025-12-31'))
            result = cur.fetchone()
            project_ids.append(result['id'])
        
        # Inserisce investimenti di test
        test_investments = [
            (user_ids[0], project_ids[0], 50000.00, 'active', 8.5),
            (user_ids[0], project_ids[1], 75000.00, 'active', 7.2),
            (user_ids[1], project_ids[0], 30000.00, 'active', 8.5),
            (user_ids[2], project_ids[2], 100000.00, 'active', 9.0),
            (user_ids[3], project_ids[1], 25000.00, 'completed', 7.2)
        ]
        
        investment_ids = []
        for user_id, project_id, amount, status, yield_pct in test_investments:
            cur.execute("""
                INSERT INTO investments (user_id, project_id, amount, status, expected_yield_pct, activated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, project_id, amount, status, yield_pct, '2024-01-15'))
            result = cur.fetchone()
            investment_ids.append(result['id'])
        
        # Inserisce richieste di investimento di test
        test_requests = [
            (user_ids[1], project_ids[3], 40000.00, 'in_review'),
            (user_ids[3], project_ids[0], 35000.00, 'approved')
        ]
        
        for user_id, project_id, amount, state in test_requests:
            cur.execute("""
                INSERT INTO investment_requests (user_id, project_id, amount, state)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (user_id, project_id, amount, state))
        
        # Inserisce notifiche di test
        test_notifications = [
            (user_ids[0], 'medium', 'investment', 'Nuovo investimento attivato', 'Il tuo investimento nel progetto PROJ001 è stato attivato'),
            (user_ids[1], 'high', 'system', 'Richiesta approvata', 'La tua richiesta di investimento è stata approvata'),
            (None, 'low', 'system', 'Nuovo progetto disponibile', 'È disponibile un nuovo progetto di investimento')
        ]
        
        for user_id, priority, kind, title, body in test_notifications:
            cur.execute("""
                INSERT INTO notifications (user_id, priority, kind, title, body)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, priority, kind, title, body))
        
        # Inserisce bonus referral di test
        test_bonuses = [
            (user_ids[0], user_ids[1], investment_ids[0], 1, 2500.00, '2024-01-01'),
            (user_ids[0], user_ids[2], investment_ids[1], 1, 3750.00, '2024-01-01'),
            (user_ids[1], user_ids[3], investment_ids[2], 2, 1500.00, '2024-01-01')
        ]
        
        for receiver_id, source_id, investment_id, level, amount, month_ref in test_bonuses:
            cur.execute("""
                INSERT INTO referral_bonuses (receiver_user_id, source_user_id, investment_id, level, amount, month_ref, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (receiver_id, source_id, investment_id, level, amount, month_ref, 'accrued'))
        
        # Commit delle modifiche
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Dati di test inseriti con successo! Ora puoi fare login con:',
            'login_credentials': {
                'test.user1@example.com': {'password': 'test123', 'role': 'investor'},
                'test.user2@example.com': {'password': 'test123', 'role': 'investor'},
                'test.admin@example.com': {'password': 'test123', 'role': 'admin'},
                'test.investor@example.com': {'password': 'test123', 'role': 'investor'}
            },
            'data': {
                'users_created': len(user_ids),
                'projects_created': len(project_ids),
                'investments_created': len(investment_ids)
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore inserimento dati di test: {str(e)}")
        return jsonify({'success': False, 'error': f'Errore inserimento dati: {str(e)}'}), 500

@portfolio_bp.route('/test/clear', methods=['DELETE'])
def clear_test_data():
    """Elimina tutti i dati di test dal database (non richiede login)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Elimina in ordine per rispettare i vincoli di integrità referenziale
        cur.execute("DELETE FROM referral_bonuses WHERE receiver_user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        cur.execute("DELETE FROM referral_bonuses WHERE source_user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        
        cur.execute("DELETE FROM investment_yields WHERE investment_id IN (SELECT id FROM investments WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com'))")
        cur.execute("DELETE FROM investments WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        
        cur.execute("DELETE FROM investment_requests WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        
        cur.execute("DELETE FROM documents WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        
        cur.execute("DELETE FROM notifications WHERE user_id IN (SELECT id FROM users WHERE email LIKE 'test.%@example.com')")
        cur.execute("DELETE FROM notifications WHERE user_id IS NULL AND title LIKE '%test%'")
        
        cur.execute("DELETE FROM projects WHERE code LIKE 'PROJ%'")
        
        cur.execute("DELETE FROM users WHERE email LIKE 'test.%@example.com'")
        
        # Commit delle modifiche
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Dati di test eliminati con successo'
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore eliminazione dati di test: {str(e)}")
        return jsonify({'success': False, 'error': f'Errore eliminazione dati: {str(e)}'}), 500

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
