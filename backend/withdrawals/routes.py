"""
Routes per gestione prelievi
"""

import json
import secrets
import string
from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, jsonify, session, render_template
from backend.shared.database import get_connection as get_conn
from backend.auth.decorators import login_required, admin_required, can_withdraw
from backend.shared.validators import ValidationError
import logging

logger = logging.getLogger(__name__)

withdrawals_bp = Blueprint('withdrawals', __name__, url_prefix='/withdrawals')

def generate_unique_key():
    """Genera una chiave unica di 6 caratteri alfanumerici"""
    return ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))

def ensure_withdrawals_schema():
    """Assicura che lo schema dei prelievi sia aggiornato"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica se le colonne esistono e le aggiunge se necessario
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'withdrawal_requests' 
                AND column_name IN ('method', 'wallet_address', 'unique_key', 'source_section')
            """)
            existing_columns = [row['column_name'] for row in cur.fetchall()]
            
            if 'method' not in existing_columns:
                cur.execute("ALTER TABLE withdrawal_requests ADD COLUMN method TEXT CHECK (method IN ('usdt', 'bank'))")
                logger.info("Aggiunta colonna 'method' a withdrawal_requests")
            
            if 'wallet_address' not in existing_columns:
                cur.execute("ALTER TABLE withdrawal_requests ADD COLUMN wallet_address TEXT")
                logger.info("Aggiunta colonna 'wallet_address' a withdrawal_requests")
            
            if 'unique_key' not in existing_columns:
                cur.execute("ALTER TABLE withdrawal_requests ADD COLUMN unique_key TEXT UNIQUE")
                logger.info("Aggiunta colonna 'unique_key' a withdrawal_requests")
            
            if 'source_section' not in existing_columns:
                cur.execute("ALTER TABLE withdrawal_requests ADD COLUMN source_section TEXT CHECK (source_section IN ('free_capital','referral_bonus','profits'))")
                logger.info("Aggiunta colonna 'source_section' a withdrawal_requests")
            
            if 'network' not in existing_columns:
                cur.execute("ALTER TABLE withdrawal_requests ADD COLUMN network TEXT DEFAULT 'BEP20'")
                logger.info("Aggiunta colonna 'network' a withdrawal_requests")
            
            # Aggiorna i record esistenti se necessario
            cur.execute("""
                UPDATE withdrawal_requests 
                SET method = 'bank', unique_key = %s, source_section = 'free_capital'
                WHERE method IS NULL OR unique_key IS NULL OR source_section IS NULL
            """, (generate_unique_key(),))
            
            conn.commit()
            logger.info("Schema withdrawal_requests aggiornato con successo")
            
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento schema withdrawal_requests: {e}")
        raise

@withdrawals_bp.route('/api/rate-limit-status', methods=['GET'])
@login_required
def get_withdrawal_rate_limit_status():
    """Verifica lo stato del rate limit per i prelievi"""
    uid = session.get("user_id")
    if not uid:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Cerca l'ultima richiesta di prelievo negli ultimi 5 minuti
            cur.execute("""
                SELECT created_at 
                FROM withdrawal_requests 
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
                        'message': f'Puoi fare una nuova richiesta di prelievo tra {minutes}m {seconds}s',
                        'last_request': last_request_time.isoformat()
                    })
            
            return jsonify({
                'rate_limited': False,
                'remaining_seconds': 0,
                'message': 'Puoi fare una nuova richiesta di prelievo'
            })
            
    except Exception as e:
        logger.warning("[withdrawals] rate limit status check failed: %s", e)
        return jsonify({
            'rate_limited': False,
            'remaining_seconds': 0,
            'message': 'Puoi fare una nuova richiesta di prelievo'
        })

@withdrawals_bp.route('/api/requests/new', methods=['POST'])
@can_withdraw
def create_withdrawal_request():
    """Crea una nuova richiesta di prelievo"""
    uid = session.get("user_id")
    if not uid:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        data = request.get_json() or {}
        amount = Decimal(str(data.get('amount', 0)))
        method = data.get('method')  # usdt o bank
        source_section = data.get('source_section')
        wallet_address = data.get('wallet_address', '').strip()
        network = data.get('network', 'BEP20')  # BEP20, ERC20, TRC20
        bank_details = data.get('bank_details', {})
        
        # Validazioni base
        if amount <= 0:
            return jsonify({'error': 'Importo deve essere positivo'}), 400
        
        if amount < 50:
            return jsonify({'error': 'Importo minimo: €50'}), 400
        
        if not method or method not in ['usdt', 'bank']:
            return jsonify({'error': 'Metodo di prelievo non valido'}), 400
        
        if not source_section or source_section not in ['free_capital', 'referral_bonus', 'profits']:
            return jsonify({'error': 'Sezione sorgente non valida'}), 400
        
        # Validazioni specifiche per metodo
        if method == 'usdt':
            if not wallet_address:
                return jsonify({'error': 'Indirizzo wallet richiesto per prelievi USDT'}), 400
            # Validazione base indirizzo BEP20 (inizia con 0x e ha 42 caratteri)
            if not wallet_address.startswith('0x') or len(wallet_address) != 42:
                return jsonify({'error': 'Indirizzo wallet non valido'}), 400
        elif method == 'bank':
            if not bank_details.get('iban'):
                return jsonify({'error': 'IBAN richiesto per prelievi bancari'}), 400
            if not bank_details.get('account_holder'):
                return jsonify({'error': 'Intestatario richiesto per prelievi bancari'}), 400
        
        # Assicura schema aggiornato
        ensure_withdrawals_schema()
        
        with get_conn() as conn, conn.cursor() as cur:
            # Controllo rate limit - verifica se c'è stata una richiesta negli ultimi 5 minuti
            cur.execute("""
                SELECT created_at 
                FROM withdrawal_requests 
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
                        'error': 'Rate limit exceeded',
                        'message': f'Puoi fare una nuova richiesta di prelievo tra {minutes}m {seconds}s',
                        'remaining_seconds': remaining_seconds
                    }), 429
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
                return jsonify({'error': f'Saldo insufficiente nella sezione {source_section}. Disponibile: €{available_amount}'}), 400
            
            # Genera chiave unica
            unique_key = generate_unique_key()
            
            # Crea richiesta
            if method == 'usdt':
                cur.execute("""
                    INSERT INTO withdrawal_requests 
                    (user_id, amount, method, source_section, wallet_address, network, unique_key, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id, created_at
                """, (uid, amount, method, source_section, wallet_address, network, unique_key))
            else:  # bank
                cur.execute("""
                    INSERT INTO withdrawal_requests 
                    (user_id, amount, method, source_section, bank_details, unique_key, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id, created_at
                """, (uid, amount, method, source_section, json.dumps(bank_details), unique_key))
            
            new_request = cur.fetchone()
            conn.commit()
        
        return jsonify({
            'success': True,
            'withdrawal_request': {
                'id': new_request['id'],
                'amount': float(amount),
                'method': method,
                'source_section': source_section,
                'unique_key': unique_key,
                'status': 'pending',
                'created_at': new_request['created_at'].isoformat() if new_request['created_at'] else None
            },
            'message': 'Richiesta di prelievo creata con successo'
        })
        
    except Exception as e:
        logger.exception(f"Errore nella creazione richiesta prelievo: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/requests', methods=['GET'])
@login_required
def get_user_withdrawals():
    """Ottiene le richieste di prelievo dell'utente"""
    uid = session.get("user_id")
    if not uid:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, amount, method, source_section, wallet_address, network, bank_details, 
                       unique_key, status, admin_notes, created_at, approved_at
                FROM withdrawal_requests 
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (uid,))
            withdrawals = cur.fetchall()
            
            # Converti i risultati
            result = []
            for w in withdrawals:
                withdrawal_data = {
                    'id': w['id'],
                    'amount': float(w['amount']),
                    'method': w['method'],
                    'source_section': w['source_section'],
                    'unique_key': w['unique_key'],
                    'status': w['status'],
                    'admin_notes': w['admin_notes'],
                    'created_at': w['created_at'].isoformat() if w['created_at'] else None,
                    'approved_at': w['approved_at'].isoformat() if w['approved_at'] else None
                }
                
                # Aggiungi dettagli specifici per metodo
                if w['method'] == 'usdt':
                    withdrawal_data['wallet_address'] = w['wallet_address']
                    withdrawal_data['network'] = w['network'] or 'BEP20'
                elif w['method'] == 'bank' and w['bank_details']:
                    # Per SQLite, bank_details è una stringa JSON che deve essere parsata
                    try:
                        import json
                        withdrawal_data['bank_details'] = json.loads(w['bank_details'])
                    except (json.JSONDecodeError, TypeError):
                        withdrawal_data['bank_details'] = {}
                
                result.append(withdrawal_data)
            
            return jsonify({'withdrawals': result})
            
    except Exception as e:
        logger.exception(f"Errore nel recupero prelievi utente: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

# ============================================================================
# ROUTE ADMIN
# ============================================================================

@withdrawals_bp.route('/api/admin/pending', methods=['GET'])
@admin_required
def admin_get_pending_withdrawals():
    """Admin: Ottiene le richieste di prelievo in attesa"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT wr.id, wr.user_id, 
                       COALESCE(NULLIF(u.full_name, ''), u.nome || ' ' || u.cognome) as full_name,
                       u.email, wr.amount, wr.method,
                       wr.source_section, wr.wallet_address, wr.network, wr.bank_details, wr.unique_key,
                       wr.status, wr.created_at, wr.admin_notes
                FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id
                WHERE wr.status = 'pending'
                ORDER BY wr.created_at ASC
            """)
            withdrawals = cur.fetchall()
            
            # Converti i risultati
            result = []
            for w in withdrawals:
                withdrawal_data = {
                    'id': w['id'],
                    'user_id': w['user_id'],
                    'full_name': w['full_name'],
                    'email': w['email'],
                    'amount': float(w['amount']),
                    'method': w['method'],
                    'source_section': w['source_section'],
                    'unique_key': w['unique_key'],
                    'status': w['status'],
                    'admin_notes': w['admin_notes'],
                    'created_at': w['created_at'].isoformat() if w['created_at'] else None,
                    'hours_pending': 0  # Calcolato nel frontend se necessario
                }
                
                # Aggiungi dettagli specifici per metodo
                if w['method'] == 'usdt':
                    withdrawal_data['wallet_address'] = w['wallet_address']
                    withdrawal_data['network'] = w['network'] or 'BEP20'
                elif w['method'] == 'bank' and w['bank_details']:
                    # Per SQLite, bank_details è una stringa JSON che deve essere parsata
                    try:
                        import json
                        withdrawal_data['bank_details'] = json.loads(w['bank_details'])
                    except (json.JSONDecodeError, TypeError):
                        withdrawal_data['bank_details'] = {}
                
                result.append(withdrawal_data)
            
            return jsonify({'withdrawals': result})
            
    except Exception as e:
        logger.exception(f"Errore nel recupero prelievi admin: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/admin/details/<int:withdrawal_id>', methods=['GET'])
@admin_required
def admin_get_withdrawal_details(withdrawal_id):
    """Admin: Ottiene i dettagli completi di un singolo prelievo"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT wr.id, wr.user_id, 
                       COALESCE(NULLIF(u.full_name, ''), u.nome || ' ' || u.cognome) as full_name,
                       u.email, wr.amount, wr.method,
                       wr.source_section, wr.wallet_address, wr.network, wr.bank_details, wr.unique_key,
                       wr.status, wr.created_at, wr.admin_notes
                FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id
                WHERE wr.id = ?
            """, (withdrawal_id,))
            withdrawal = cur.fetchone()
            
            if not withdrawal:
                return jsonify({'error': 'Prelievo non trovato'}), 404
            
            # Converti il risultato
            withdrawal_data = {
                'id': withdrawal['id'],
                'user_id': withdrawal['user_id'],
                'full_name': withdrawal['full_name'],
                'email': withdrawal['email'],
                'amount': float(withdrawal['amount']),
                'method': withdrawal['method'],
                'source_section': withdrawal['source_section'],
                'unique_key': withdrawal['unique_key'],
                'status': withdrawal['status'],
                'admin_notes': withdrawal['admin_notes'],
                'created_at': withdrawal['created_at'].isoformat() if withdrawal['created_at'] else None,
                'hours_pending': 0
            }
            
            # Aggiungi dettagli specifici per metodo
            if withdrawal['method'] == 'usdt':
                withdrawal_data['wallet_address'] = withdrawal['wallet_address']
                withdrawal_data['network'] = withdrawal['network'] or 'BEP20'
            elif withdrawal['method'] == 'bank' and withdrawal['bank_details']:
                try:
                    import json
                    withdrawal_data['bank_details'] = json.loads(withdrawal['bank_details'])
                except:
                    withdrawal_data['bank_details'] = {}
            
            return jsonify({'withdrawal': withdrawal_data})
            
    except Exception as e:
        logger.exception(f"Errore nel recupero dettagli prelievo {withdrawal_id}: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/admin/approve/<int:request_id>', methods=['POST'])
@admin_required
def admin_approve_withdrawal(request_id):
    """Admin: Approva una richiesta di prelievo"""
    try:
        admin_user_id = session.get('user_id')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste e è pending
            cur.execute("""
                SELECT wr.*, u.email FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id  
                WHERE wr.id = %s AND wr.status = 'pending'
            """, (request_id,))
            withdrawal = cur.fetchone()
            
            if not withdrawal:
                return jsonify({'error': 'Richiesta non trovata o già processata'}), 404
            
            # Aggiorna stato prelievo
            cur.execute("""
                UPDATE withdrawal_requests 
                SET status = 'completed', approved_at = NOW(), approved_by = %s
                WHERE id = %s
            """, (admin_user_id, request_id))
            
            # Rimuovi importo dal portfolio utente
            source_section = withdrawal['source_section']
            amount = withdrawal['amount']
            
            if source_section == 'free_capital':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = free_capital - %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (amount, withdrawal['user_id']))
            elif source_section == 'referral_bonus':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET referral_bonus = referral_bonus - %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (amount, withdrawal['user_id']))
            elif source_section == 'profits':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET profits = profits - %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (amount, withdrawal['user_id']))
            
            # Registra transazione
            cur.execute("""
                INSERT INTO portfolio_transactions (
                    user_id, type, amount, balance_before, balance_after,
                    description, reference_id, reference_type, status, created_at
                ) VALUES (
                    %s, 'withdrawal', %s, 0, 0, 
                    'Prelievo approvato da admin', %s, 'withdrawal_request', 'completed', NOW()
                )
            """, (withdrawal['user_id'], amount, request_id))
            
            conn.commit()
            
            logger.info(f"Prelievo {request_id} approvato da admin {admin_user_id}")
        
        return jsonify({
            'success': True,
            'message': 'Prelievo approvato con successo',
            'withdrawal_id': request_id
        })
        
    except Exception as e:
        logger.exception(f"Errore nell'approvazione prelievo {request_id}: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/admin/reject/<int:request_id>', methods=['POST'])
@admin_required
def admin_reject_withdrawal(request_id):
    """Admin: Rifiuta una richiesta di prelievo"""
    try:
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', 'Rifiutato da admin')
        admin_user_id = session.get('user_id')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste e è pending
            cur.execute("""
                SELECT * FROM withdrawal_requests 
                WHERE id = %s AND status = 'pending'
            """, (request_id,))
            withdrawal = cur.fetchone()
            
            if not withdrawal:
                return jsonify({'error': 'Richiesta non trovata o già processata'}), 404
            
            # Aggiorna stato prelievo
            cur.execute("""
                UPDATE withdrawal_requests 
                SET status = 'cancelled', admin_notes = %s, approved_at = NOW(), approved_by = %s
                WHERE id = %s
            """, (admin_notes, admin_user_id, request_id))
            
            conn.commit()
            
            logger.info(f"Prelievo {request_id} rifiutato da admin {admin_user_id}: {admin_notes}")
        
        return jsonify({
            'success': True,
            'message': 'Prelievo rifiutato',
            'withdrawal_id': request_id
        })
        
    except Exception as e:
        logger.exception(f"Errore nel rifiuto prelievo {request_id}: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/admin/metrics', methods=['GET'])
@admin_required
def admin_get_withdrawals_metrics():
    """Admin: Ottiene le metriche dei prelievi"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Conta prelievi per stato
            cur.execute("""
                SELECT 
                    status,
                    COUNT(*) as count,
                    COALESCE(SUM(amount), 0) as total_amount
                FROM withdrawal_requests 
                GROUP BY status
            """)
            status_counts = cur.fetchall()
            
            # Calcola metriche
            metrics = {
                'pending': 0,
                'completed': 0,
                'cancelled': 0,
                'total_amount': 0
            }
            
            for row in status_counts:
                if row['status'] == 'pending':
                    metrics['pending'] = row['count']
                elif row['status'] == 'completed':
                    metrics['completed'] = row['count']
                    metrics['total_amount'] = float(row['total_amount'])
                elif row['status'] == 'cancelled':
                    metrics['cancelled'] = row['count']
            
            return jsonify(metrics)
            
    except Exception as e:
        logger.exception(f"Errore nel recupero metriche prelievi: {e}")
        return jsonify({'error': 'Errore interno del server'}), 500

@withdrawals_bp.route('/api/admin/history', methods=['GET'])
@admin_required
def admin_get_withdrawals_history():
    """Admin: Ottiene lo storico di tutti i prelievi"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        status_filter = request.args.get('status', '')
        search_query = request.args.get('search', '')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Costruisci query con filtri
            where_conditions = []
            params = []
            
            if status_filter:
                where_conditions.append("wr.status = %s")
                params.append(status_filter)
            
            if search_query:
                where_conditions.append("(u.full_name ILIKE %s OR u.email ILIKE %s)")
                params.extend([f'%{search_query}%', f'%{search_query}%'])
            
            where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
            
            # Query principale
            query = f"""
                SELECT wr.id, wr.user_id, u.full_name, u.email, wr.amount, wr.method,
                       wr.source_section, wr.wallet_address, wr.bank_details, wr.unique_key,
                       wr.status, wr.created_at, wr.approved_at, wr.admin_notes,
                       admin_user.full_name as approved_by_name
                FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id
                LEFT JOIN users admin_user ON admin_user.id = wr.approved_by
                {where_clause}
                ORDER BY wr.created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([per_page, offset])
            
            cur.execute(query, params)
            withdrawals = cur.fetchall()
            
            # Conta totale per paginazione
            count_query = f"""
                SELECT COUNT(*) FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id
                {where_clause}
            """
            cur.execute(count_query, params[:-2])  # Rimuovi LIMIT e OFFSET
            total_count = cur.fetchone()['count']
            
            # Converti i risultati
            result = []
            for w in withdrawals:
                withdrawal_data = {
                    'id': w['id'],
                    'user_id': w['user_id'],
                    'full_name': w['full_name'],
                    'email': w['email'],
                    'amount': float(w['amount']),
                    'method': w['method'],
                    'source_section': w['source_section'],
                    'unique_key': w['unique_key'],
                    'status': w['status'],
                    'admin_notes': w['admin_notes'],
                    'created_at': w['created_at'].isoformat() if w['created_at'] else None,
                    'approved_at': w['approved_at'].isoformat() if w['approved_at'] else None,
                    'approved_by_name': w['approved_by_name']
                }
                
                # Aggiungi dettagli specifici per metodo
                if w['method'] == 'usdt':
                    withdrawal_data['wallet_address'] = w['wallet_address']
                elif w['method'] == 'bank' and w['bank_details']:
                    # Per SQLite, bank_details è una stringa JSON che deve essere parsata
                    try:
                        import json
                        withdrawal_data['bank_details'] = json.loads(w['bank_details'])
                    except (json.JSONDecodeError, TypeError):
                        withdrawal_data['bank_details'] = {}
                
                result.append(withdrawal_data)
            
            return jsonify({
                'withdrawals': result,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total_count': total_count,
                    'total_pages': (total_count + per_page - 1) // per_page
                }
            })
            
    except Exception as e:
        logger.exception(f"Errore nel recupero storico prelievi: {e}")
        return jsonify({'error': 'Errore interno del server'        }), 500

@withdrawals_bp.route('/api/admin/delete-multiple', methods=['DELETE'])
@admin_required
def admin_delete_multiple_withdrawals():
    """Admin elimina più prelievi dal database"""
    
    try:
        admin_user_id = session.get("user_id")
        data = request.get_json()
        
        if not data or 'withdrawal_ids' not in data:
            return jsonify({'error': 'Lista ID prelievi mancante'}), 400
        
        withdrawal_ids = data['withdrawal_ids']
        if not isinstance(withdrawal_ids, list) or len(withdrawal_ids) == 0:
            return jsonify({'error': 'Lista ID prelievi non valida'}), 400
        
        # Verifica che tutti gli ID siano numeri interi
        try:
            withdrawal_ids = [int(id) for id in withdrawal_ids]
        except (ValueError, TypeError):
            return jsonify({'error': 'ID prelievi non validi'}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Prima verifichiamo quanti prelievi esistono
            placeholders = ','.join(['%s'] * len(withdrawal_ids))
            cur.execute(f"""
                SELECT id, user_id, amount, status, created_at
                FROM withdrawal_requests 
                WHERE id IN ({placeholders})
            """, withdrawal_ids)
            
            existing_withdrawals = cur.fetchall()
            existing_ids = [w['id'] for w in existing_withdrawals]
            
            if len(existing_ids) != len(withdrawal_ids):
                missing_ids = set(withdrawal_ids) - set(existing_ids)
                return jsonify({'error': f'Prelievi non trovati: {list(missing_ids)}'}), 404
            
            logger.warning(f"[ADMIN DELETE MULTIPLE] User {admin_user_id} is deleting {len(withdrawal_ids)} withdrawals: {withdrawal_ids}")
            
            # Elimina i prelievi
            cur.execute(f"DELETE FROM withdrawal_requests WHERE id IN ({placeholders})", withdrawal_ids)
            deleted_count = cur.rowcount
            
            if deleted_count == 0:
                return jsonify({'error': 'Nessun prelievo eliminato'}), 404
            
            conn.commit()
            
            logger.warning(f"[ADMIN DELETE MULTIPLE] Completed: {deleted_count} withdrawals deleted")
            
            return jsonify({
                'success': True,
                'message': f'Eliminati {deleted_count} prelievi con successo',
                'deleted_count': deleted_count,
                'deleted_ids': existing_ids
            })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE MULTIPLE] Error deleting withdrawals: {e}")
        return jsonify({
            'error': 'Errore durante l\'eliminazione dei prelievi',
            'debug': str(e)
        }), 500

# Route per pagine admin (senza prefisso)

@withdrawals_bp.route('/admin/withdrawals/history', methods=['GET'])
@admin_required
def admin_withdrawals_history():
    """Admin: Pagina storico prelievi"""
    return render_template('admin/withdrawals/history.html')

@withdrawals_bp.route('/api/admin/delete-all', methods=['DELETE'])
@admin_required
def admin_delete_all_withdrawals():
    """Admin elimina tutti i prelievi dal database (AZIONE PERICOLOSA)"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as total FROM withdrawal_requests")
            total_withdrawals = cur.fetchone()['total']
            
            if total_withdrawals == 0:
                return jsonify({'success': True, 'message': 'Nessun prelievo da eliminare', 'deleted_count': 0})
            
            admin_user_id = session.get('user_id')
            logger.warning(f"[ADMIN DELETE] User {admin_user_id} is deleting ALL {total_withdrawals} withdrawals from database")
            
            # Elimina transazioni correlate
            cur.execute("""
                DELETE FROM portfolio_transactions 
                WHERE reference_type = 'withdrawal_request'
            """)
            deleted_transactions = cur.rowcount
            
            # Elimina tutti i prelievi
            cur.execute("DELETE FROM withdrawal_requests")
            deleted_withdrawals = cur.rowcount
            
            conn.commit()
            
            logger.warning(f"[ADMIN DELETE] Completed: {deleted_withdrawals} withdrawals, {deleted_transactions} transactions deleted")
        
        return jsonify({
            'success': True,
            'message': f'Eliminati {deleted_withdrawals} prelievi e {deleted_transactions} transazioni',
            'deleted_count': deleted_withdrawals,
            'deleted_transactions': deleted_transactions
        })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE] Error deleting withdrawals: {e}")
        return jsonify({'error': 'Errore durante l\'eliminazione dei prelievi', 'debug': str(e)}), 500

@withdrawals_bp.route('/api/admin/delete/<int:withdrawal_id>', methods=['DELETE'])
@admin_required
def admin_delete_single_withdrawal(withdrawal_id):
    """Admin elimina un singolo prelievo dal database"""
    
    try:
        admin_user_id = session.get("user_id")
        
        with get_conn() as conn, conn.cursor() as cur:
            # Prima verifichiamo che il prelievo esista
            cur.execute("""
                SELECT id, user_id, amount, status, created_at
                FROM withdrawal_requests 
                WHERE id = %s
            """, (withdrawal_id,))
            
            withdrawal = cur.fetchone()
            if not withdrawal:
                return jsonify({'error': 'Prelievo non trovato'}), 404
            
            logger.warning(f"[ADMIN DELETE SINGLE] User {admin_user_id} is deleting withdrawal {withdrawal_id} (user: {withdrawal['user_id']}, amount: {withdrawal['amount']}, status: {withdrawal['status']})")
            
            # Elimina il prelievo
            cur.execute("DELETE FROM withdrawal_requests WHERE id = %s", (withdrawal_id,))
            deleted_count = cur.rowcount
            
            if deleted_count == 0:
                return jsonify({'error': 'Prelievo non trovato'}), 404
            
            conn.commit()
            
            logger.warning(f"[ADMIN DELETE SINGLE] Completed: withdrawal {withdrawal_id} deleted")
            
            return jsonify({
                'success': True,
                'message': f'Prelievo {withdrawal_id} eliminato con successo',
                'deleted_id': withdrawal_id
            })
        
    except Exception as e:
        logger.exception(f"[ADMIN DELETE SINGLE] Error deleting withdrawal {withdrawal_id}: {e}")
        return jsonify({
            'error': 'Errore durante l\'eliminazione del prelievo',
            'debug': str(e)
        }), 500
