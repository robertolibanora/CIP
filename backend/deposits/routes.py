"""
Deposits API routes
API per gestione ricariche: Richieste, approvazioni
"""

import secrets
import string
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
from backend.shared.models import TransactionStatus

deposits_bp = Blueprint("deposits", __name__)

def get_conn():
    return get_connection()

def generate_unique_key(length=6):
    """Genera una chiave univoca alfanumerica"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_payment_reference(length=12):
    """Genera una chiave randomica per causale bonifico"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, kyc_verified

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 3. RICARICHE API - Richieste, approvazioni
# =====================================================

@deposits_bp.route('/api/requests', methods=['GET'])
@login_required
def get_deposit_requests():
    """Ottiene le richieste di ricarica dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, iban, unique_key, payment_reference, status, 
                   admin_notes, created_at, approved_at
            FROM deposit_requests 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (uid,))
        requests = cur.fetchall()
    
    return jsonify({'deposit_requests': requests})

@deposits_bp.route('/api/requests/<int:request_id>', methods=['GET'])
@login_required
def get_deposit_request_detail(request_id):
    """Ottiene i dettagli di una richiesta di ricarica specifica"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, iban, unique_key, payment_reference, status, 
                   admin_notes, created_at, approved_at, approved_by
            FROM deposit_requests 
            WHERE id = %s AND user_id = %s
        """, (request_id, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        # Ottieni dettagli IBAN
        cur.execute("""
            SELECT bank_name, account_holder
            FROM iban_configurations 
            WHERE iban = %s
        """, (request_detail['iban'],))
        iban_info = cur.fetchone()
        
        if iban_info:
            request_detail['bank_name'] = iban_info['bank_name']
            request_detail['account_holder'] = iban_info['account_holder']
    
    return jsonify({'deposit_request': request_detail})

@deposits_bp.route('/api/requests/new', methods=['POST'])
@kyc_verified
def create_deposit_request():
    """Crea una nuova richiesta di ricarica"""
    uid = session.get("user_id")
    data = request.get_json() or {}
    
    # Validazione dati
    if 'amount' not in data:
        return jsonify({'error': 'Importo obbligatorio'}), 400
    
    try:
        amount = Decimal(str(data['amount']))
    except (ValueError, TypeError):
        return jsonify({'error': 'Importo non valido'}), 400
    
    # Validazione importo minimo (500€)
    if amount < 500:
        return jsonify({'error': 'Importo minimo richiesto: 500€'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni IBAN attivo
        cur.execute("""
            SELECT iban, bank_name, account_holder
            FROM iban_configurations 
            WHERE is_active = TRUE 
            LIMIT 1
        """)
        iban_config = cur.fetchone()
        
        if not iban_config:
            return jsonify({'error': 'Nessun IBAN configurato per le ricariche'}), 500
        
        # Genera chiavi univoche
        unique_key = generate_unique_key()
        payment_reference = generate_payment_reference()
        
        # Verifica unicità chiavi
        cur.execute("""
            SELECT id FROM deposit_requests 
            WHERE unique_key = %s OR payment_reference = %s
        """, (unique_key, payment_reference))
        
        if cur.fetchone():
            return jsonify({'error': 'Errore generazione chiavi univoche. Riprova.'}), 500
        
        # Crea richiesta
        cur.execute("""
            INSERT INTO deposit_requests 
            (user_id, amount, iban, unique_key, payment_reference, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, created_at
        """, (uid, amount, iban_config['iban'], unique_key, payment_reference, 'pending'))
        
        new_request = cur.fetchone()
        conn.commit()
    
    return jsonify({
        'success': True,
        'deposit_request': {
            'id': new_request['id'],
            'amount': float(amount),
            'iban': iban_config['iban'],
            'bank_name': iban_config['bank_name'],
            'account_holder': iban_config['account_holder'],
            'unique_key': unique_key,
            'payment_reference': payment_reference,
            'status': 'pending',
            'created_at': new_request['created_at'].isoformat() if new_request['created_at'] else None
        },
        'message': 'Richiesta di ricarica creata con successo'
    })

@deposits_bp.route('/api/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_deposit_request(request_id):
    """Annulla una richiesta di ricarica (solo se pending)"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica proprietà e stato
        cur.execute("""
            SELECT id, status FROM deposit_requests 
            WHERE id = %s AND user_id = %s
        """, (request_id, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere annullate'}), 400
        
        # Annulla richiesta
        cur.execute("""
            UPDATE deposit_requests 
            SET status = 'cancelled' 
            WHERE id = %s
        """, (request_id,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Richiesta annullata con successo'
    })

@deposits_bp.route('/api/iban-info', methods=['GET'])
@login_required
def get_iban_info():
    """Ottiene le informazioni IBAN per le ricariche"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT iban, bank_name, account_holder
            FROM iban_configurations 
            WHERE is_active = TRUE 
            LIMIT 1
        """)
        iban_info = cur.fetchone()
        
        if not iban_info:
            return jsonify({'error': 'Nessun IBAN configurato'}), 404
    
    return jsonify({
        'iban': iban_info['iban'],
        'bank_name': iban_info['bank_name'],
        'account_holder': iban_info['account_holder']
    })

@deposits_bp.route('/api/status/<unique_key>', methods=['GET'])
@login_required
def get_deposit_status_by_key(unique_key):
    """Ottiene lo stato di una richiesta tramite chiave univoca"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, status, created_at, approved_at, admin_notes
            FROM deposit_requests 
            WHERE unique_key = %s AND user_id = %s
        """, (unique_key, uid))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
    
    return jsonify({
        'unique_key': unique_key,
        'amount': float(request_detail['amount']),
        'status': request_detail['status'],
        'created_at': request_detail['created_at'].isoformat() if request_detail['created_at'] else None,
        'approved_at': request_detail['approved_at'].isoformat() if request_detail['approved_at'] else None,
        'admin_notes': request_detail['admin_notes']
    })

# =====================================================
# ENDPOINT ADMIN (richiedono ruolo admin)
# =====================================================

from backend.auth.decorators import admin_required

@deposits_bp.route('/api/admin/pending', methods=['GET'])
@admin_required
def admin_get_pending_deposits():
    """Admin ottiene tutte le richieste di ricarica in attesa"""
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT dr.id, dr.amount, dr.iban, dr.unique_key, dr.payment_reference,
                   dr.created_at, dr.admin_notes,
                   u.id as user_id, u.full_name, u.email, u.kyc_status,
                   ic.bank_name, ic.account_holder
            FROM deposit_requests dr
            JOIN users u ON dr.user_id = u.id
            JOIN iban_configurations ic ON dr.iban = ic.iban
            WHERE dr.status = 'pending'
            ORDER BY dr.created_at ASC
        """)
        pending_deposits = cur.fetchall()
    
    return jsonify({'pending_deposits': pending_deposits})

@deposits_bp.route('/api/admin/approve/<int:request_id>', methods=['POST'])
@admin_required
def admin_approve_deposit(request_id):
    """Admin approva una richiesta di ricarica"""
    
    data = request.get_json() or {}
    admin_notes = data.get('admin_notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica richiesta esiste e è pending
        cur.execute("""
            SELECT id, user_id, amount, status FROM deposit_requests 
            WHERE id = %s
        """, (request_id,))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere approvate'}), 400
        
        # Approva richiesta
        cur.execute("""
            UPDATE deposit_requests 
            SET status = 'completed', approved_at = NOW(), approved_by = %s, admin_notes = %s
            WHERE id = %s
        """, (session.get('user_id'), admin_notes, request_id))
        
        # Aggiorna portfolio utente
        cur.execute("""
            UPDATE user_portfolios 
            SET free_capital = free_capital + %s, updated_at = NOW()
            WHERE user_id = %s
        """, (request_detail['amount'], request_detail['user_id']))
        
        # Crea transazione portfolio
        cur.execute("""
            INSERT INTO portfolio_transactions 
            (user_id, type, amount, balance_before, balance_after, description, 
             reference_id, reference_type, status)
            SELECT 
                %s, 'deposit', %s, 
                (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                'Ricarica approvata', %s, 'deposit_request', 'completed'
            FROM user_portfolios WHERE user_id = %s
        """, (request_detail['user_id'], request_detail['amount'], 
              request_detail['user_id'], request_detail['user_id'],
              request_id, request_detail['user_id']))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ricarica approvata con successo'
    })

@deposits_bp.route('/api/admin/reject/<int:request_id>', methods=['POST'])
@admin_required
def admin_reject_deposit(request_id):
    """Admin rifiuta una richiesta di ricarica"""
    
    data = request.get_json() or {}
    admin_notes = data.get('admin_notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica richiesta esiste e è pending
        cur.execute("""
            SELECT id, status FROM deposit_requests 
            WHERE id = %s
        """, (request_id,))
        request_detail = cur.fetchone()
        
        if not request_detail:
            return jsonify({'error': 'Richiesta non trovata'}), 404
        
        if request_detail['status'] != 'pending':
            return jsonify({'error': 'Solo le richieste in attesa possono essere rifiutate'}), 400
        
        # Rifiuta richiesta
        cur.execute("""
            UPDATE deposit_requests 
            SET status = 'failed', admin_notes = %s
            WHERE id = %s
        """, (admin_notes, request_id))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Ricarica rifiutata'
    })

@deposits_bp.route('/api/admin/iban/configure', methods=['POST'])
@admin_required
def admin_configure_iban():
    """Admin configura l'IBAN per le ricariche"""
    
    data = request.get_json() or {}
    
    # Validazione dati
    required_fields = ['iban', 'bank_name', 'account_holder']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo obbligatorio mancante: {field}'}), 400
    
    iban = data['iban']
    bank_name = data['bank_name']
    account_holder = data['account_holder']
    
    with get_conn() as conn, conn.cursor() as cur:
        # Disattiva tutti gli IBAN esistenti
        cur.execute("""
            UPDATE iban_configurations 
            SET is_active = FALSE, updated_at = NOW()
        """)
        
        # Inserisci nuovo IBAN
        cur.execute("""
            INSERT INTO iban_configurations (iban, bank_name, account_holder, is_active)
            VALUES (%s, %s, %s, TRUE)
            ON CONFLICT (iban) 
            DO UPDATE SET 
                bank_name = EXCLUDED.bank_name,
                account_holder = EXCLUDED.account_holder,
                is_active = TRUE,
                updated_at = NOW()
        """, (iban, bank_name, account_holder))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'IBAN configurato con successo',
        'iban': iban,
        'bank_name': bank_name,
        'account_holder': account_holder
    })
