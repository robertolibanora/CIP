"""
Withdrawals API routes
API per gestione prelievi: Richieste e approvazioni
"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
from backend.shared.models import TransactionStatus

withdrawals_bp = Blueprint("withdrawals", __name__)

def get_conn():
    return get_connection()

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, can_withdraw

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 4. PRELIEVI API - Richieste e approvazioni
# =====================================================

@withdrawals_bp.route('/api/requests', methods=['GET'])
@login_required
def get_withdrawal_requests():
    """Ottiene le richieste di prelievo dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, source_section, bank_details, status, 
                   admin_notes, created_at, approved_at
            FROM withdrawal_requests 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (uid,))
        requests = cur.fetchall()
    
    return jsonify({'withdrawal_requests': requests})

@withdrawals_bp.route('/api/requests/<int:request_id>', methods=['GET'])
@login_required
def get_withdrawal_request_detail(request_id):
    """Ottiene i dettagli di una richiesta di prelievo specifica"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, source_section, bank_details, status, 
                   admin_notes, created_at, approved_at, approved_by
            FROM withdrawal_requests 
            WHERE id = %s AND user_id = %s
        """, (request_id, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
    
    return jsonify({'withdrawal_request': request_detail})

@withdrawals_bp.route('/api/requests/new', methods=['POST'])
@can_withdraw
def create_withdrawal_request():
    """Crea una nuova richiesta di prelievo"""
    uid = session.get("user_id")
    data = request.get_json() or {}
    
    # Validazione dati
    required_fields = ['amount', 'source_section', 'bank_details']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo obbligatorio mancante: {field}'}), 400
    
    try:
        amount = Decimal(str(data['amount']))
    except (ValueError, TypeError):
        return jsonify({'error': 'Importo non valido'}), 400
    
    source_section = data['source_section']
    bank_details = data['bank_details']
    
    # Validazione importo minimo (50 dollari)
    if amount < 50:
        return jsonify({'error': 'Importo minimo richiesto: 50 dollari'}), 400
    
    # Validazione sezione fonte
    valid_sections = ['free_capital', 'referral_bonus', 'profits']
    if source_section not in valid_sections:
        return jsonify({'error': f'Sezione fonte non valida. Valori ammessi: {valid_sections}'}), 400
    
    # Validazione dettagli bancari
    if not isinstance(bank_details, dict) or 'iban' not in bank_details:
        return jsonify({'error': 'Dettagli bancari non validi. Richiesto campo IBAN'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica disponibilità saldo
        cur.execute("""
            SELECT free_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            return jsonify({'error': 'Portfolio non trovato'}), 404
        
        # Controlla saldo disponibile per la sezione
        available_amount = 0
        if source_section == 'free_capital':
            available_amount = portfolio['free_capital']
        elif source_section == 'referral_bonus':
            available_amount = portfolio['referral_bonus']
        elif source_section == 'profits':
            available_amount = portfolio['profits']
        
        if available_amount < amount:
            return jsonify({'error': f'Saldo insufficiente nella sezione {source_section}. Disponibile: {available_amount}'}), 400
        
        # Crea richiesta
        cur.execute("""
            INSERT INTO withdrawal_requests 
            (user_id, amount, source_section, bank_details, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (uid, amount, source_section, bank_details, 'pending'))
        
        new_request = cur.fetchone()
        conn.commit()
    
    return jsonify({
        'success': True,
        'withdrawal_request': {
            'id': new_request['id'],
            'amount': float(amount),
            'source_section': source_section,
            'bank_details': bank_details,
            'status': 'pending',
            'created_at': new_request['created_at'].isoformat() if new_request['created_at'] else None
        },
        'message': 'Richiesta di prelievo creata con successo'
    })

@withdrawals_bp.route('/api/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_withdrawal_request(request_id):
    """Annulla una richiesta di prelievo (solo se pending)"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica proprietà e stato
        cur.execute("""
            SELECT id, status FROM withdrawal_requests 
            WHERE id = %s AND user_id = %s
        """, (request_id, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere annullate'}), 400
        
        # Annulla richiesta
        cur.execute("""
            UPDATE withdrawal_requests 
            SET status = 'cancelled' 
            WHERE id = %s
        """, (request_id,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Richiesta annullata con successo'
    })

@withdrawals_bp.route('/api/available-amounts', methods=['GET'])
@login_required
def get_available_amounts():
    """Ottiene gli importi disponibili per prelievo dalle varie sezioni"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT free_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            return jsonify({
                'free_capital': 0.0,
                'referral_bonus': 0.0,
                'profits': 0.0,
                'total_available': 0.0
            })
        
        total_available = portfolio['free_capital'] + portfolio['referral_bonus'] + portfolio['profits']
    
    return jsonify({
        'free_capital': float(portfolio['free_capital']),
        'referral_bonus': float(portfolio['referral_bonus']),
        'profits': float(portfolio['profits']),
        'total_available': float(total_available)
    })

@withdrawals_bp.route('/api/status/<int:request_id>', methods=['GET'])
@login_required
def get_withdrawal_status(request_id):
    """Ottiene lo stato di una richiesta di prelievo"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, source_section, status, created_at, approved_at, admin_notes
            FROM withdrawal_requests 
            WHERE id = %s AND user_id = %s
        """, (request_id, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
    
    return jsonify({
        'request_id': request_detail['id'],
        'amount': float(request_detail['amount']),
        'source_section': request_detail['source_section'],
        'status': request_detail['status'],
        'created_at': request_detail['created_at'].isoformat() if request_detail['created_at'] else None,
        'approved_at': request_detail['approved_at'].isoformat() if request_detail['approved_at'] else None,
        'admin_notes': request_detail['admin_notes']
    })

# =====================================================
# ENDPOINT ADMIN (richiedono ruolo admin)
# =====================================================

from backend.auth.decorators import admin_required

@withdrawals_bp.route('/api/admin/pending', methods=['GET'])
@admin_required
def admin_get_pending_withdrawals():
    """Admin ottiene tutte le richieste di prelievo in attesa"""
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT wr.id, wr.amount, wr.source_section, wr.bank_details, wr.created_at,
                   wr.admin_notes,
                   u.id as user_id, u.full_name, u.email, u.kyc_status,
                   up.free_capital, up.referral_bonus, up.profits
            FROM withdrawal_requests wr
            JOIN users u ON wr.user_id = u.id
            JOIN user_portfolios up ON wr.user_id = up.user_id
            WHERE wr.status = 'pending'
            ORDER BY wr.created_at ASC
        """)
        pending_withdrawals = cur.fetchall()
    
    return jsonify({'pending_withdrawals': pending_withdrawals})

@withdrawals_bp.route('/api/admin/approve/<int:request_id>', methods=['POST'])
@admin_required
def admin_approve_withdrawal(request_id):
    """Admin approva una richiesta di prelievo"""
    
    data = request.get_json() or {}
    admin_notes = data.get('admin_notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica richiesta esiste e è pending
        cur.execute("""
            SELECT id, user_id, amount, source_section, status FROM withdrawal_requests 
            WHERE id = %s
        """, (request_id,))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere approvate'}), 400
        
        # Verifica saldo ancora disponibile
        cur.execute("""
            SELECT free_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (request_detail['user_id'],))
        portfolio = cur.fetchone()
        
        if not portfolio:
            return jsonify({'error': 'Portfolio utente non trovato'}), 404
        
        # Controlla saldo per la sezione
        source_section = request_detail['source_section']
        available_amount = 0
        if source_section == 'free_capital':
            available_amount = portfolio['free_capital']
        elif source_section == 'referral_bonus':
            available_amount = portfolio['referral_bonus']
        elif source_section == 'profits':
            available_amount = portfolio['profits']
        
        if available_amount < request_detail['amount']:
            return jsonify({'error': f'Saldo insufficiente nella sezione {source_section}. Disponibile: {available_amount}'}), 400
        
        # Approva richiesta
        cur.execute("""
            UPDATE withdrawal_requests 
            SET status = 'completed', approved_at = NOW(), approved_by = %s, admin_notes = %s
            WHERE id = %s
        """, (session.get('user_id'), admin_notes, request_id))
        
        # Aggiorna portfolio utente
        if source_section == 'free_capital':
            cur.execute("""
                UPDATE user_portfolios 
                SET free_capital = free_capital - %s, updated_at = NOW()
                WHERE user_id = %s
            """, (request_detail['amount'], request_detail['user_id']))
        elif source_section == 'referral_bonus':
            cur.execute("""
                UPDATE user_portfolios 
                SET referral_bonus = referral_bonus - %s, updated_at = NOW()
                WHERE user_id = %s
            """, (request_detail['amount'], request_detail['user_id']))
        elif source_section == 'profits':
            cur.execute("""
                UPDATE user_portfolios 
                SET profits = profits - %s, updated_at = NOW()
                WHERE user_id = %s
            """, (request_detail['amount'], request_detail['user_id']))
        
        # Crea transazione portfolio
        cur.execute("""
            INSERT INTO portfolio_transactions 
            (user_id, type, amount, balance_before, balance_after, description, 
             reference_id, reference_type, status)
            SELECT 
                %s, 'withdrawal', %s, 
                (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                'Prelievo approvato', %s, 'withdrawal_request', 'completed'
            FROM user_portfolios WHERE user_id = %s
        """, (request_detail['user_id'], request_detail['amount'], 
              request_detail['user_id'], request_detail['user_id'],
              request_id, request_detail['user_id']))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Prelievo approvato con successo'
    })

@withdrawals_bp.route('/api/admin/reject/<int:request_id>', methods=['POST'])
@admin_required
def admin_reject_withdrawal(request_id):
    """Admin rifiuta una richiesta di prelievo"""
    
    data = request.get_json() or {}
    admin_notes = data.get('admin_notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica richiesta esiste e è pending
        cur.execute("""
            SELECT id, status FROM withdrawal_requests 
            WHERE id = %s
        """, (request_id,))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere rifiutate'}), 400
        
        # Rifiuta richiesta
        cur.execute("""
            UPDATE withdrawal_requests 
            SET status = 'failed', admin_notes = %s
            WHERE id = %s
        """, (admin_notes, request_id))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Prelievo rifiutato'
    })

@withdrawals_bp.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_get_withdrawal_stats():
    """Admin ottiene statistiche sui prelievi"""
    
    with get_conn() as conn, conn.cursor() as cur:
        # Conta richieste per stato
        cur.execute("""
            SELECT status, COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
            FROM withdrawal_requests 
            GROUP BY status
        """)
        status_stats = cur.fetchall()
        
        # Conta richieste per sezione
        cur.execute("""
            SELECT source_section, COUNT(*) as count, COALESCE(SUM(amount), 0) as total_amount
            FROM withdrawal_requests 
            GROUP BY source_section
        """)
        section_stats = cur.fetchall()
        
        # Richieste in attesa da più di 48h
        cur.execute("""
            SELECT COUNT(*) as count
            FROM withdrawal_requests 
            WHERE status = 'pending' AND created_at < NOW() - INTERVAL '48 hours'
        """)
        overdue_requests = cur.fetchone()
    
    return jsonify({
        'status_stats': status_stats,
        'section_stats': section_stats,
        'overdue_requests': overdue_requests['count'] if overdue_requests else 0
    })
