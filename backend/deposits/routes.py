"""
Deposits API routes
API per gestione ricariche: Richieste, approvazioni
"""

import secrets
import string
from datetime import datetime
import logging
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
import psycopg
from psycopg import errors as pg_errors
from backend.shared.models import TransactionStatus

deposits_bp = Blueprint("deposits", __name__)
logger = logging.getLogger(__name__)

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

def ensure_deposits_schema(cur):
    """Crea tabelle minime necessarie se mancanti (solo per ambienti dev)."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS iban_configurations (
            id SERIAL PRIMARY KEY,
            iban TEXT NOT NULL UNIQUE,
            bank_name TEXT NOT NULL,
            account_holder TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deposit_requests (
            id SERIAL PRIMARY KEY,
            user_id INT NOT NULL,
            amount NUMERIC(15,2) NOT NULL CHECK (amount >= 500.00),
            iban TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'bank',
            unique_key TEXT NOT NULL UNIQUE,
            payment_reference TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL CHECK (status IN ('pending','completed','failed','cancelled')) DEFAULT 'pending',
            admin_notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            approved_at TIMESTAMPTZ,
            approved_by INT
        );
    """)
    # Assicura presenza colonna method anche su installazioni esistenti
    try:
        cur.execute("ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS method TEXT NOT NULL DEFAULT 'bank'")
    except Exception:
        pass
    # Assicura colonne unique_key e payment_reference su installazioni esistenti
    try:
        cur.execute("ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS unique_key TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS payment_reference TEXT")
    except Exception:
        pass
    # Assicura vincoli UNIQUE (usa indici unici, più tolleranti se la colonna già esiste)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS deposit_requests_unique_key_idx ON deposit_requests (unique_key)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS deposit_requests_payment_reference_idx ON deposit_requests (payment_reference)")

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, kyc_pending_allowed

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
@kyc_pending_allowed
def create_deposit_request():
    """Crea una nuova richiesta di ricarica"""
    uid = session.get("user_id")
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    logger.info("[deposits] create payload=%s headers=%s", data, dict(request.headers))

    if not uid:
        logger.warning("[deposits] create denied: missing user session")
        return jsonify({'error': 'unauthorized'}), 401
    logger.info("[deposits] POST /api/requests/new uid=%s payload=%s", uid, data)
    
    # Validazione dati
    if 'amount' not in data:
        return jsonify({'error': 'Importo obbligatorio'}), 400
    
    try:
        amount = Decimal(str(data['amount']))
    except (ValueError, TypeError, KeyError):
        return jsonify({'error': 'Importo non valido'}), 400
    
    # Validazione importo minimo (500€)
    if amount < Decimal('500'):
        return jsonify({'error': 'Importo minimo richiesto: 500€'}), 400
    
    # Metodo pagamento: 'usdt' | 'bank'
    method = str(data.get('payment_method', 'bank')).lower()
    if method not in ['usdt', 'bank']:
        return jsonify({'error': 'Metodo pagamento non valido'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Garantisce schema in dev
            ensure_deposits_schema(cur)
            # Ottieni IBAN attivo
            cur.execute("""
                SELECT iban, bank_name, account_holder
                FROM iban_configurations 
                WHERE is_active = TRUE 
                LIMIT 1
            """)
            iban_config = cur.fetchone()
            logger.info("[deposits] active IBAN fetched: %s", iban_config)
            
            if not iban_config:
                # Se non esiste una configurazione IBAN attiva, crea una voce di default
                default_iban = 'IT60X0542811101000000123456'
                default_bank = 'Banca Example'
                default_holder = 'CIP Immobiliare SRL'
                cur.execute("""
                    INSERT INTO iban_configurations (iban, bank_name, account_holder, is_active)
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (iban) DO UPDATE SET 
                        bank_name = EXCLUDED.bank_name,
                        account_holder = EXCLUDED.account_holder,
                        is_active = TRUE,
                        updated_at = NOW()
                """, (default_iban, default_bank, default_holder))
                iban_config = {
                    'iban': default_iban,
                    'bank_name': default_bank,
                    'account_holder': default_holder
                }
            
            # Prova inserimento con retry per evitare collisioni univoche
            attempts = 0
            new_request = None
            last_error = None
            while attempts < 5 and not new_request:
                attempts += 1
                unique_key = generate_unique_key()
                payment_reference = generate_payment_reference()
                try:
                    cur.execute("""
                        INSERT INTO deposit_requests 
                        (user_id, amount, iban, method, unique_key, payment_reference, status)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id, created_at
                    """, (uid, amount, iban_config['iban'], method, unique_key, payment_reference, 'pending'))
                    new_request = cur.fetchone()
                except pg_errors.UniqueViolation as ue:
                    conn.rollback()
                    last_error = ue
                    # Ritenta con nuove chiavi
                    continue
            if not new_request:
                logger.error("[deposits] unique key generation failed after retries: %s", last_error)
                return jsonify({'error': 'Errore generazione chiavi, riprovare tra poco'}), 500
            conn.commit()
            logger.info("[deposits] created deposit_request id=%s amount=%s user=%s", new_request['id'] if new_request else None, amount, uid)
    except Exception as e:
        logger.exception("[deposits] create failed: %s", e)
        # Risposta dettagliata in dev per debug rapido
        return jsonify({'error': 'Errore interno durante la creazione della richiesta', 'debug': str(e)}), 500
    
    return jsonify({
        'success': True,
        'deposit_request': {
            'id': new_request['id'],
            'amount': float(amount),
            'iban': iban_config['iban'],
            'bank_name': iban_config['bank_name'],
            'account_holder': iban_config['account_holder'],
            'method': method,
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
