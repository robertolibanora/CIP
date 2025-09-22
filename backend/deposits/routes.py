"""
Deposits API routes
API per gestione ricariche: Richieste, approvazioni
"""

import secrets
import string
from datetime import datetime
import logging
from decimal import Decimal
from flask import Blueprint, request, session, jsonify, render_template
from backend.shared.database import get_connection
from backend.shared.notifications import create_deposit_notification
import psycopg
from psycopg import errors as pg_errors
from backend.shared.models import TransactionStatus

deposits_bp = Blueprint("deposits", __name__)
logger = logging.getLogger(__name__)

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

def generate_unique_key(length=6):
    """Genera una chiave univoca alfanumerica"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def generate_payment_reference(user_name=None, length=12):
    """Genera una causale bonifico unica usando il template configurato dall'admin"""
    # Fallback: genera una chiave randomica
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def ensure_deposits_schema(cur):
    """Crea tabelle minime necessarie se mancanti (solo per ambienti dev)."""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS bank_configurations (
            id SERIAL PRIMARY KEY,
            iban TEXT NOT NULL UNIQUE,
            bank_name TEXT NOT NULL,
            account_holder TEXT NOT NULL,
            bic_swift TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS wallet_configurations (
            id SERIAL PRIMARY KEY,
            wallet_address TEXT NOT NULL,
            network TEXT NOT NULL,
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
    # Allinea tipo admin_notes a TEXT (alcuni vecchi schemi avevano BOOLEAN)
    try:
        cur.execute("""
            ALTER TABLE deposit_requests 
            ALTER COLUMN admin_notes TYPE TEXT USING admin_notes::text
        """)
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
    # Assicura colonne approved_at e approved_by su installazioni esistenti
    try:
        cur.execute("ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE deposit_requests ADD COLUMN IF NOT EXISTS approved_by INT")
    except Exception:
        pass
    # Assicura vincoli UNIQUE (usa indici unici, più tolleranti se la colonna già esiste)
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS deposit_requests_unique_key_idx ON deposit_requests (unique_key)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS deposit_requests_payment_reference_idx ON deposit_requests (payment_reference)")
    # Allinea constraint di stato (alcuni ambienti potrebbero avere un set limitato)
    try:
        cur.execute("ALTER TABLE deposit_requests DROP CONSTRAINT IF EXISTS deposit_requests_status_check")
    except Exception:
        pass
    try:
        cur.execute("""
            ALTER TABLE deposit_requests 
            ADD CONSTRAINT deposit_requests_status_check 
            CHECK (status IN ('pending','completed','failed','cancelled'))
        """)
    except Exception:
        pass

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, kyc_pending_allowed
from backend.shared.notifications import create_deposit_notification

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 3. RICARICHE API - Richieste, approvazioni
# =====================================================

@deposits_bp.route('/api/requests', methods=['GET'])
@login_required
def get_deposit_requests():
    """Ottiene le richieste di deposito dell'utente"""
    uid = session.get("user_id")
    
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, amount, iban, 
                   COALESCE(unique_key, '') as unique_key, 
                   COALESCE(payment_reference, '') as payment_reference, 
                   status, admin_notes, created_at, approved_at, 
                   COALESCE(method, 'bank') as method,
                   COALESCE(network, 'ethereum') as network
            FROM deposit_requests 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (uid,))
        rows = cur.fetchall()
        # Serializza datetime e normalizza campi per JSON
        requests = []
        for row in rows:
            item = dict(row)
            created = item.get('created_at')
            approved = item.get('approved_at')
            if created is not None:
                try:
                    item['created_at'] = created.isoformat()
                except Exception:
                    item['created_at'] = str(created)
            if approved is not None:
                try:
                    item['approved_at'] = approved.isoformat()
                except Exception:
                    item['approved_at'] = str(approved)
            requests.append(item)
    
    return jsonify({'deposit_requests': requests})

@deposits_bp.route('/api/rate-limit-status', methods=['GET'])
@login_required
def get_rate_limit_status():
    """Controlla lo stato del rate limiting per i depositi"""
    uid = session.get("user_id")
    
    if not uid:
        return jsonify({'error': 'unauthorized'}), 401
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT created_at 
                FROM deposit_requests 
                WHERE user_id = %s 
                AND created_at > NOW() - INTERVAL '5 minutes'
                ORDER BY created_at DESC 
                LIMIT 1
            """, (uid,))
            recent_request = cur.fetchone()
            
            if recent_request:
                # Calcola il tempo rimanente
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                last_request_time = recent_request['created_at']
                if last_request_time.tzinfo is None:
                    last_request_time = last_request_time.replace(tzinfo=timezone.utc)
                
                time_diff = now - last_request_time
                remaining_seconds = 300 - int(time_diff.total_seconds())  # 5 minuti = 300 secondi
                
                if remaining_seconds > 0:
                    minutes = remaining_seconds // 60
                    seconds = remaining_seconds % 60
                    return jsonify({
                        'rate_limited': True,
                        'remaining_seconds': remaining_seconds,
                        'message': f'Puoi fare una nuova richiesta di deposito tra {minutes}m {seconds}s',
                        'last_request': last_request_time.isoformat()
                    })
            
            return jsonify({
                'rate_limited': False,
                'remaining_seconds': 0,
                'message': 'Puoi fare una nuova richiesta di deposito'
            })
            
    except Exception as e:
        logger.warning("[deposits] rate limit status check failed: %s", e)
        return jsonify({
            'rate_limited': False,
            'remaining_seconds': 0,
            'message': 'Puoi fare una nuova richiesta di deposito'
        })

@deposits_bp.route('/api/requests/<int:request_id>', methods=['GET'])
@login_required
def get_deposit_request_detail(request_id):
    """Ottiene i dettagli di una richiesta di deposito specifica"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            ensure_deposits_schema(cur)
        except Exception:
            pass
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
def create_deposit_request():
    """Crea una nuova richiesta di deposito"""
    uid = session.get("user_id")
    
    if not uid:
        # Per test, usa l'utente piero (ID 6)
        uid = 6
    try:
        data = request.get_json(force=True, silent=True) or {}
    except Exception:
        data = {}
    logger.info("[deposits] create payload=%s headers=%s", data, dict(request.headers))

    if not uid:
        logger.warning("[deposits] create denied: missing user session")
        return jsonify({'error': 'unauthorized'}), 401
    logger.info("[deposits] POST /api/requests/new uid=%s payload=%s", uid, data)
    
    # Rate limiting: controlla se l'utente ha già fatto una richiesta negli ultimi 5 minuti
    # DISABILITATO TEMPORANEAMENTE PER DEBUG
    # try:
    #     with get_conn() as conn, conn.cursor() as cur:
    #         cur.execute("""
    #             SELECT created_at 
    #             FROM deposit_requests 
    #             WHERE user_id = %s 
    #             AND created_at > NOW() - INTERVAL '5 minutes'
    #             ORDER BY created_at DESC 
    #             LIMIT 1
    #         """, (uid,))
    #         recent_request = cur.fetchone()
    #         
    #         if recent_request:
    #             # Calcola il tempo rimanente
    #             from datetime import datetime, timezone
    #             now = datetime.now(timezone.utc)
    #             last_request_time = recent_request['created_at']
    #             if last_request_time.tzinfo is None:
    #                 last_request_time = last_request_time.replace(tzinfo=timezone.utc)
    #             
    #             time_diff = now - last_request_time
    #             remaining_seconds = 300 - int(time_diff.total_seconds())  # 5 minuti = 300 secondi
    #             
    #             if remaining_seconds > 0:
    #                 minutes = remaining_seconds // 60
    #                 seconds = remaining_seconds % 60
    #                 return jsonify({
    #                     'error': 'Rate limit exceeded',
    #                     'message': f'Puoi fare una nuova richiesta di deposito tra {minutes}m {seconds}s',
    #                     'remaining_seconds': remaining_seconds
    #                 }), 429
    # except Exception as e:
    #     logger.warning("[deposits] rate limiting check failed: %s", e)
    #     # Continua comunque se il controllo fallisce
    
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
        # Transazione per le operazioni
        with get_conn() as conn, conn.cursor() as cur:
            try:
                # Ottieni configurazione bonifici attiva
                cur.execute("""
                    SELECT iban, bank_name, account_holder, bic_swift
                    FROM bank_configurations 
                    WHERE is_active = true 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                bank_config = cur.fetchone()
                logger.info("[deposits] active bank config fetched: %s", bank_config)
                
                if not bank_config:
                    # Se non esiste una configurazione attiva, usa valori di default
                    bank_config = {
                        'iban': 'IT60X0542811101000000123456',
                        'bank_name': 'Banca Example',
                        'account_holder': 'CIP Immobiliare SRL',
                        'bic_swift': ''
                    }
                
                # Ottieni configurazione wallet USDT
                cur.execute("""
                    SELECT wallet_address, network
                    FROM wallet_configurations 
                    WHERE is_active = true 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                wallet_config = cur.fetchone()
                logger.info("[deposits] active wallet config fetched: %s", wallet_config)
                
                if not wallet_config:
                    # Se non esiste una configurazione attiva, usa valori di default
                    import os
                    wallet_config = {
                        'wallet_address': os.environ.get('USDT_BEP20_WALLET', '0xF00DBABECAFEBABE000000000000000000000000'),
                        'network': 'BEP20'
                    }
                
                # Determina destinatario fondi in base al metodo
                # - bank: usa IBAN configurato
                # - usdt: usa wallet configurato
                if method == 'bank':
                    receiver_field_value = bank_config['iban']
                else:
                    receiver_field_value = wallet_config['wallet_address']

                # Ottieni nome utente per la causale
                cur.execute("SELECT nome, cognome FROM users WHERE id = %s", (uid,))
                user_info = cur.fetchone()
                user_name = f"{user_info.get('nome', '')} {user_info.get('cognome', '')}".strip() if user_info else None
                
                # Prova inserimento con retry per evitare collisioni univoche
                attempts = 0
                new_request = None
                last_error = None
                while attempts < 5 and not new_request:
                    attempts += 1
                    unique_key = generate_unique_key()
                    payment_reference = generate_payment_reference(user_name)
                    try:
                        cur.execute("""
                            INSERT INTO deposit_requests 
                            (user_id, amount, iban, method, unique_key, payment_reference, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id, created_at
                        """, (uid, amount, receiver_field_value, method, unique_key, payment_reference, 'pending'))
                        new_request = cur.fetchone()
                    except pg_errors.UniqueViolation as ue:
                        conn.rollback()
                        last_error = ue
                        # Ritenta con nuove chiavi
                        continue
                if not new_request:
                    logger.error("[deposits] unique key generation failed after retries: %s", last_error)
                    return jsonify({'error': 'Errore generazione chiavi, riprovare tra poco'}), 500
                
                logger.info("[deposits] created deposit_request id=%s amount=%s user=%s", new_request['id'] if new_request else None, amount, uid)
                
                # Crea notifica per admin
                try:
                    # Recupera nome utente per la notifica
                    cur.execute("SELECT nome, cognome FROM users WHERE id = %s", (uid,))
                    user_data = cur.fetchone()
                    if user_data:
                        user_name = f"{user_data['nome']} {user_data['cognome']}"
                        create_deposit_notification(uid, user_name)
                except Exception as e:
                    logger.error(f"Errore creazione notifica deposito: {e}")
                
                # COMMIT DELLA TRANSAZIONE
                conn.commit()
                
            except Exception as db_error:
                logger.exception("[deposits] database error: %s", db_error)
                conn.rollback()
                return jsonify({'error': 'Errore interno durante la creazione della richiesta', 'debug': str(db_error)}), 500
            
    except Exception as e:
        logger.exception("[deposits] create failed: %s", e)
        # Rollback in caso di errore
        try:
            conn.rollback()
        except:
            pass
        # Risposta dettagliata in dev per debug rapido
        return jsonify({'error': 'Errore interno durante la creazione della richiesta', 'debug': str(e)}), 500
    
    # Prepara dati di risposta
    response_data = {
        'id': new_request['id'],
        'amount': float(amount),
        'method': method,
        'unique_key': unique_key,
        'payment_reference': payment_reference,
        'status': 'pending',
        'created_at': new_request['created_at'].isoformat() if new_request['created_at'] else None
    }
    
    # Aggiungi dati specifici per metodo
    if method == 'bank':
        response_data.update({
            'iban': bank_config['iban'],
            'bank_name': bank_config['bank_name'],
            'account_holder': bank_config['account_holder'],
            'bic_swift': bank_config.get('bic_swift', '')
        })
    else:  # USDT
        response_data.update({
            'wallet_address': wallet_config['wallet_address'],
            'network': wallet_config['network']
        })
    
    return jsonify({
        'success': True,
        'deposit_request': response_data,
        'message': 'Richiesta di deposito creata con successo'
    })

@deposits_bp.route('/api/requests/<int:request_id>/cancel', methods=['POST'])
@login_required
def cancel_deposit_request(request_id):
    """Annulla una richiesta di deposito (solo se pending)"""
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
            SELECT iban, bank_name, account_holder, bic_swift
            FROM bank_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        bank_info = cur.fetchone()
        
        if not bank_info:
            return jsonify({'error': 'Nessuna configurazione bancaria configurata'}), 404
    
    return jsonify({
        'iban': bank_info['iban'],
        'bank_name': bank_info['bank_name'],
        'account_holder': bank_info['account_holder'],
        'bic_swift': bank_info.get('bic_swift', '')
    })

@deposits_bp.route('/api/status/<unique_key>', methods=['GET'])
@login_required
def get_deposit_status_by_key(unique_key):
    """Ottiene lo stato di una richiesta tramite chiave univoca"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            ensure_deposits_schema(cur)
        except Exception:
            pass
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
    """Admin ottiene tutte le richieste di deposito in attesa"""
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT dr.id, dr.amount, dr.iban, dr.method, dr.unique_key, dr.payment_reference,
                   dr.created_at, dr.admin_notes,
                   u.id as user_id, u.nome, u.email, u.kyc_status,
                   ic.bank_name, ic.account_holder
            FROM deposit_requests dr
            JOIN users u ON dr.user_id = u.id
            LEFT JOIN bank_configurations ic ON (dr.iban = ic.iban AND dr.method = 'bank')
            WHERE dr.status = 'pending'
            ORDER BY dr.created_at ASC
        """)
        pending_deposits = cur.fetchall()
    
    return jsonify({'pending_deposits': pending_deposits})

@deposits_bp.route('/api/admin/history', methods=['GET'])
@admin_required
def admin_get_deposits_history():
    """Admin ottiene lo storico di tutti i depositi"""
    
    # Parametri di paginazione
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    offset = (page - 1) * per_page
    
    with get_conn() as conn, conn.cursor() as cur:
        # Query base
        base_query = """
            SELECT dr.id, dr.amount, dr.iban, dr.method, dr.unique_key, dr.payment_reference,
                   dr.status, dr.created_at, dr.approved_at, dr.admin_notes,
                   u.id as user_id, u.nome, u.email, u.kyc_status,
                   ic.bank_name, ic.account_holder,
                   admin_user.nome as approved_by_name
            FROM deposit_requests dr
            JOIN users u ON dr.user_id = u.id
            LEFT JOIN bank_configurations ic ON (dr.iban = ic.iban AND dr.method = 'bank')
            LEFT JOIN users admin_user ON dr.approved_by = admin_user.id
        """
        
        # Condizioni WHERE
        where_conditions = []
        params = []
        
        if status_filter:
            where_conditions.append("dr.status = %s")
            params.append(status_filter)
        
        if search:
            where_conditions.append("(u.email ILIKE %s OR u.nome ILIKE %s OR dr.unique_key ILIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Query per contare il totale
        count_query = f"""
            SELECT COUNT(*) as total
            FROM deposit_requests dr
            JOIN users u ON dr.user_id = u.id
            {where_clause}
        """
        cur.execute(count_query, params)
        total_count = cur.fetchone()['total']
        
        # Query principale con paginazione
        main_query = f"""
            {base_query}
            {where_clause}
            ORDER BY dr.created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        
        cur.execute(main_query, params)
        deposits = cur.fetchall()
        
        # Calcola statistiche
        stats_query = """
            SELECT 
                status,
                COUNT(*) as count,
                SUM(amount) as total_amount
            FROM deposit_requests
            GROUP BY status
        """
        cur.execute(stats_query)
        stats = cur.fetchall()
        
        # Calcola paginazione
        total_pages = (total_count + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
    
    return jsonify({
        'deposits': deposits,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'total_pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next
        },
        'stats': stats,
        'filters': {
            'status': status_filter,
            'search': search
        }
    })

@deposits_bp.route('/api/admin/approve/<int:request_id>', methods=['POST'])
@admin_required
def admin_approve_deposit(request_id):
    """Admin approva una richiesta di deposito"""
    try:
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', '')
        with get_conn() as conn, conn.cursor() as cur:
            # Garantisce schema coerente
            ensure_deposits_schema(cur)
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
                    'Deposito approvato', %s, 'deposit_request', 'completed'
                FROM user_portfolios WHERE user_id = %s
            """, (request_detail['user_id'], request_detail['amount'], 
                  request_detail['user_id'], request_detail['user_id'],
                  request_id, request_detail['user_id']))
            conn.commit()
        return jsonify({'success': True, 'message': 'Deposito approvato con successo'})
    except Exception as e:
        logger.exception("[deposits] admin approve failed: %s", e)
        return jsonify({'error': 'approve_failed', 'debug': str(e)}), 500

@deposits_bp.route('/api/admin/reject/<int:request_id>', methods=['POST'])
@admin_required
def admin_reject_deposit(request_id):
    """Admin rifiuta una richiesta di deposito"""
    try:
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', '')
        with get_conn() as conn, conn.cursor() as cur:
            # Garantisce schema coerente
            ensure_deposits_schema(cur)
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
        return jsonify({'success': True, 'message': 'Deposito rifiutato'})
    except Exception as e:
        logger.exception("[deposits] admin reject failed: %s", e)
        return jsonify({'error': 'reject_failed', 'debug': str(e)}), 500

@deposits_bp.route('/api/admin/delete-all', methods=['DELETE'])
@admin_required
def admin_delete_all_deposits():
    """Admin elimina tutti i depositi dal database (AZIONE PERICOLOSA)"""
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Prima contiamo quanti depositi ci sono
            cur.execute("SELECT COUNT(*) as total FROM deposit_requests")
            total_deposits = cur.fetchone()['total']
            
            if total_deposits == 0:
                return jsonify({
                    'success': True,
                    'message': 'Nessun deposito da eliminare',
                    'deleted_count': 0
                })
            
            # Log dell'operazione per sicurezza
            admin_user_id = session.get('user_id')
            logger.warning(f"[ADMIN DELETE] User {admin_user_id} is deleting ALL {total_deposits} deposits from database")
            
            # Elimina solo le transazioni del portfolio correlate ai depositi
            # (NON toccare il free_capital degli utenti - rappresenta i soldi reali)
            cur.execute("""
                DELETE FROM portfolio_transactions 
                WHERE reference_type = 'deposit_request'
            """)
            deleted_transactions = cur.rowcount
            
            # Elimina solo i record dei depositi (NON i soldi reali)
            cur.execute("DELETE FROM deposit_requests")
            deleted_deposits = cur.rowcount
            
            conn.commit()
            
            # Log del completamento
            logger.warning(f"[ADMIN DELETE] Completed: {deleted_deposits} deposits, {deleted_transactions} transactions deleted (portfolio NOT touched)")
            
        return jsonify({
            'success': True,
            'message': f'Eliminati {deleted_deposits} depositi e {deleted_transactions} transazioni. I capitali degli utenti NON sono stati modificati.',
            'deleted_count': deleted_deposits,
            'deleted_transactions': deleted_transactions
        })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE] Error deleting deposits: {e}")
        return jsonify({
            'error': 'Errore durante l\'eliminazione dei depositi',
            'debug': str(e)
        }), 500

@deposits_bp.route('/api/admin/delete/<int:deposit_id>', methods=['DELETE'])
@admin_required
def admin_delete_single_deposit(deposit_id):
    """Admin elimina un singolo deposito dal database"""
    
    try:
        admin_user_id = session.get("user_id")
        
        with get_conn() as conn, conn.cursor() as cur:
            # Prima verifichiamo che il deposito esista
            cur.execute("""
                SELECT id, user_id, amount, status, created_at
                FROM deposit_requests 
                WHERE id = %s
            """, (deposit_id,))
            
            deposit = cur.fetchone()
            if not deposit:
                return jsonify({'error': 'Deposito non trovato'}), 404
            
            logger.warning(f"[ADMIN DELETE SINGLE] User {admin_user_id} is deleting deposit {deposit_id} (user: {deposit['user_id']}, amount: {deposit['amount']}, status: {deposit['status']})")
            
            # Elimina il deposito
            cur.execute("DELETE FROM deposit_requests WHERE id = %s", (deposit_id,))
            deleted_count = cur.rowcount
            
            if deleted_count == 0:
                return jsonify({'error': 'Deposito non trovato'}), 404
            
            conn.commit()
            
            logger.warning(f"[ADMIN DELETE SINGLE] Completed: deposit {deposit_id} deleted")
            
            return jsonify({
                'success': True,
                'message': f'Deposito {deposit_id} eliminato con successo',
                'deleted_id': deposit_id
            })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE SINGLE] Error deleting deposit {deposit_id}: {e}")
        return jsonify({
            'error': 'Errore durante l\'eliminazione del deposito',
            'debug': str(e)
        }), 500

@deposits_bp.route('/api/admin/delete-multiple', methods=['DELETE'])
@admin_required
def admin_delete_multiple_deposits():
    """Admin elimina più depositi dal database"""
    
    try:
        admin_user_id = session.get("user_id")
        data = request.get_json()
        
        if not data or 'deposit_ids' not in data:
            return jsonify({'error': 'Lista ID depositi mancante'}), 400
        
        deposit_ids = data['deposit_ids']
        if not isinstance(deposit_ids, list) or len(deposit_ids) == 0:
            return jsonify({'error': 'Lista ID depositi non valida'}), 400
        
        # Verifica che tutti gli ID siano numeri interi
        try:
            deposit_ids = [int(id) for id in deposit_ids]
        except (ValueError, TypeError):
            return jsonify({'error': 'ID depositi non validi'}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Prima verifichiamo quanti depositi esistono
            placeholders = ','.join(['%s'] * len(deposit_ids))
            cur.execute(f"""
                SELECT id, user_id, amount, status, created_at
                FROM deposit_requests 
                WHERE id IN ({placeholders})
            """, deposit_ids)
            
            existing_deposits = cur.fetchall()
            existing_ids = [dep['id'] for dep in existing_deposits]
            
            if len(existing_ids) != len(deposit_ids):
                missing_ids = set(deposit_ids) - set(existing_ids)
                return jsonify({'error': f'Depositi non trovati: {list(missing_ids)}'}), 404
            
            logger.warning(f"[ADMIN DELETE MULTIPLE] User {admin_user_id} is deleting {len(deposit_ids)} deposits: {deposit_ids}")
            
            # Elimina i depositi
            cur.execute(f"DELETE FROM deposit_requests WHERE id IN ({placeholders})", deposit_ids)
            deleted_count = cur.rowcount
            
            if deleted_count == 0:
                return jsonify({'error': 'Nessun deposito eliminato'}), 404
            
            conn.commit()
            
            logger.warning(f"[ADMIN DELETE MULTIPLE] Completed: {deleted_count} deposits deleted")
            
            return jsonify({
                'success': True,
                'message': f'Eliminati {deleted_count} depositi con successo',
                'deleted_count': deleted_count,
                'deleted_ids': existing_ids
            })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE MULTIPLE] Error deleting deposits: {e}")
        return jsonify({
            'error': 'Errore durante l\'eliminazione dei depositi',
            'debug': str(e)
        }), 500

@deposits_bp.route('/api/admin/metrics', methods=['GET'])
@admin_required
def admin_get_deposits_metrics():
    """Admin: Ottiene le metriche dei depositi"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Conta depositi per stato
            cur.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total_amount
                FROM deposit_requests 
                GROUP BY status
            """)
            status_counts = cur.fetchall()
            
            # Calcola metriche
            metrics = {
                'pending': 0,
                'completed': 0,
                'rejected': 0,
                'total_amount': 0
            }
            
            for row in status_counts:
                if row['status'] == 'pending':
                    metrics['pending'] = row['count']
                elif row['status'] == 'completed':
                    metrics['completed'] = row['count']
                    metrics['total_amount'] = float(row['total_amount'])
                elif row['status'] in ['failed', 'cancelled']:
                    metrics['rejected'] += row['count']
            
            return jsonify(metrics)
            
    except Exception as e:
        logger.exception(f"Errore nel recupero metriche depositi: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

# Route per pagine admin (senza prefisso)

@deposits_bp.route('/admin/deposits/history', methods=['GET'])
@admin_required
def admin_deposits_history():
    """Admin: Pagina storico depositi"""
    return render_template('admin/deposits/history.html')

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
