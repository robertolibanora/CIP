"""
Portfolio API routes
API per gestione portafoglio: Lettura 4 sezioni, movimenti
"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
from backend.shared.models import TransactionType, TransactionStatus

portfolio_api_bp = Blueprint("portfolio_api", __name__)

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

# Importa decoratori di autorizzazione
from backend.auth.decorators import kyc_verified

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 2. PORTFOLIO API - Lettura 4 sezioni, movimenti
# =====================================================

@portfolio_api_bp.route('/api/overview', methods=['GET'])
@kyc_verified
def get_portfolio_overview():
    """Ottiene l'overview completo del portafoglio con le 4 sezioni"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni portfolio utente
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits,
                   created_at, updated_at
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            # Crea portfolio se non esiste
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
        
        # Ottieni ultimi movimenti
        cur.execute("""
            SELECT type, amount, description, status, created_at
            FROM portfolio_transactions 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 10
        """, (uid,))
        recent_transactions = cur.fetchall()
        
        # Ottieni statistiche investimenti
        cur.execute("""
            SELECT COUNT(*) as active_investments,
                   COALESCE(SUM(amount), 0) as total_invested
            FROM investments 
            WHERE user_id = %s AND status = 'active'
        """, (uid,))
        investment_stats = cur.fetchone()
    
    return jsonify({
        'portfolio': {
            'free_capital': float(portfolio['free_capital']),
            'invested_capital': float(portfolio['invested_capital']),
            'referral_bonus': float(portfolio['referral_bonus']),
            'profits': float(portfolio['profits']),
            'total_available': float(total_available),
            'total_balance': float(total_balance),
            'created_at': portfolio['created_at'].isoformat() if portfolio['created_at'] else None,
            'updated_at': portfolio['updated_at'].isoformat() if portfolio['updated_at'] else None
        },
        'investment_stats': {
            'active_investments': investment_stats['active_investments'],
            'total_invested': float(investment_stats['total_invested'])
        },
        'recent_transactions': recent_transactions
    })

@portfolio_api_bp.route('/api/sections/<section>', methods=['GET'])
@kyc_verified
def get_portfolio_section(section):
    """Ottiene i dettagli di una sezione specifica del portafoglio"""
    uid = session.get("user_id")
    
    # Validazione sezione
    valid_sections = ['free_capital', 'invested_capital', 'referral_bonus', 'profits']
    if section not in valid_sections:
        return jsonify({'error': 'Sezione non valida'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni valore sezione
        cur.execute("""
            SELECT {} FROM user_portfolios WHERE user_id = %s
        """.format(section), (uid,))
        result = cur.fetchone()
        
        if not result:
            return jsonify({'error': 'Portfolio non trovato'}), 404
        
        section_value = result[section]
        
        # Ottieni transazioni per questa sezione
        cur.execute("""
            SELECT type, amount, description, status, created_at, reference_type, reference_id
            FROM portfolio_transactions 
            WHERE user_id = %s 
            AND (
                (type = 'deposit' AND %s = 'free_capital') OR
                (type = 'withdrawal' AND %s = 'free_capital') OR
                (type = 'investment' AND %s = 'free_capital') OR
                (type = 'roi' AND %s = 'profits') OR
                (type = 'referral' AND %s = 'referral_bonus')
            )
            ORDER BY created_at DESC 
            LIMIT 50
        """, (uid, section, section, section, section, section))
        transactions = cur.fetchall()
        
        # Ottieni dettagli aggiuntivi per investimenti se è la sezione invested_capital
        investment_details = []
        if section == 'invested_capital':
            cur.execute("""
                SELECT i.id, i.amount, i.percentage, i.status, i.investment_date,
                       p.title as project_name, p.code as project_code
                FROM investments i
                JOIN projects p ON i.project_id = p.id
                WHERE i.user_id = %s AND i.status = 'active'
                ORDER BY i.investment_date DESC
            """, (uid,))
            investment_details = cur.fetchall()
    
    return jsonify({
        'section': section,
        'value': float(section_value),
        'transactions': transactions,
        'investment_details': investment_details if section == 'invested_capital' else []
    })

@portfolio_api_bp.route('/api/transactions', methods=['GET'])
@kyc_verified
def get_portfolio_transactions():
    """Ottiene tutte le transazioni del portafoglio con filtri"""
    uid = session.get("user_id")
    
    # Parametri di filtro
    transaction_type = request.args.get('type')
    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
    offset = int(request.args.get('offset', 0))
    
    with get_conn() as conn, conn.cursor() as cur:
        # Costruisci query con filtri
        where_conditions = ["user_id = %s"]
        params = [uid]
        
        if transaction_type:
            where_conditions.append("type = %s")
            params.append(transaction_type)
        
        if status:
            where_conditions.append("status = %s")
            params.append(status)
        
        where_clause = " AND ".join(where_conditions)
        
        # Conta totale transazioni
        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM portfolio_transactions 
            WHERE {where_clause}
        """, params)
        total_count = cur.fetchone()['total']
        
        # Ottieni transazioni paginate
        cur.execute(f"""
            SELECT id, type, amount, balance_before, balance_after, 
                   description, reference_id, reference_type, status, created_at
            FROM portfolio_transactions 
            WHERE {where_clause}
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        transactions = cur.fetchall()
        
        # Ottieni dettagli aggiuntivi per transazioni con reference
        for transaction in transactions:
            if transaction['reference_type'] == 'investment' and transaction['reference_id']:
                cur.execute("""
                    SELECT p.title as project_name, p.code as project_code
                    FROM investments i
                    JOIN projects p ON i.project_id = p.id
                    WHERE i.id = %s
                """, (transaction['reference_id'],))
                ref_details = cur.fetchone()
                if ref_details:
                    transaction['reference_details'] = ref_details
    
    return jsonify({
        'transactions': transactions,
        'pagination': {
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count
        }
    })

@portfolio_api_bp.route('/api/transactions/<int:transaction_id>', methods=['GET'])
@kyc_verified
def get_transaction_detail(transaction_id):
    """Ottiene i dettagli di una transazione specifica"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, type, amount, balance_before, balance_after, 
                   description, reference_id, reference_type, status, created_at
            FROM portfolio_transactions 
            WHERE id = %s AND user_id = %s
        """, (transaction_id, uid))
        transaction = cur.fetchone()
        
        if not transaction:
            return jsonify({'error': 'Transazione non trovata'}), 404
        
        # Ottieni dettagli aggiuntivi per reference
        if transaction['reference_type'] and transaction['reference_id']:
            if transaction['reference_type'] == 'investment':
                cur.execute("""
                    SELECT i.amount, i.percentage, i.status, i.investment_date,
                           p.title as project_name, p.code as project_code
                    FROM investments i
                    JOIN projects p ON i.project_id = p.id
                    WHERE i.id = %s
                """, (transaction['reference_id'],))
                ref_details = cur.fetchone()
                if ref_details:
                    transaction['reference_details'] = ref_details
    
    return jsonify({'transaction': transaction})

    
    # Validazione dati
    required_fields = ['type', 'amount', 'description']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo obbligatorio mancante: {field}'}), 400
    
    transaction_type = data['type']
    amount = Decimal(str(data['amount']))
    description = data['description']
    reference_id = data.get('reference_id')
    reference_type = data.get('reference_type')
    
    # Validazione tipo transazione
    valid_types = [t.value for t in TransactionType]
    if transaction_type not in valid_types:
        return jsonify({'error': f'Tipo transazione non valido. Valori ammessi: {valid_types}'}), 400
    
    # Validazione importo
    if amount <= 0:
        return jsonify({'error': 'Importo deve essere positivo'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni balance corrente
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            return jsonify({'error': 'Portfolio non trovato'}), 404
        
        # Calcola nuovo balance
        balance_before = portfolio['free_capital'] + portfolio['referral_bonus'] + portfolio['profits']
        
        # Aggiorna sezione appropriata
        if transaction_type == 'deposit':
            new_free_capital = portfolio['free_capital'] + amount
            cur.execute("""
                UPDATE user_portfolios 
                SET free_capital = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (new_free_capital, uid))
        elif transaction_type == 'withdrawal':
            new_free_capital = portfolio['free_capital'] - amount
            if new_free_capital < 0:
                return jsonify({'error': 'Saldo insufficiente per il prelievo'}), 400
            cur.execute("""
                UPDATE user_portfolios 
                SET free_capital = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (new_free_capital, uid))
        elif transaction_type == 'investment':
            new_free_capital = portfolio['free_capital'] - amount
            if new_free_capital < 0:
                return jsonify({'error': 'Saldo insufficiente per l\'investimento'}), 400
            new_invested_capital = portfolio['invested_capital'] + amount
            cur.execute("""
                UPDATE user_portfolios 
                SET free_capital = %s, invested_capital = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (new_free_capital, new_invested_capital, uid))
        elif transaction_type == 'roi':
            new_profits = portfolio['profits'] + amount
            cur.execute("""
                UPDATE user_portfolios 
                SET profits = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (new_profits, uid))
        elif transaction_type == 'referral':
            new_referral_bonus = portfolio['referral_bonus'] + amount
            cur.execute("""
                UPDATE user_portfolios 
                SET referral_bonus = %s, updated_at = NOW()
                WHERE user_id = %s
            """, (new_referral_bonus, uid))
        
        # Ottieni nuovo balance
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        new_portfolio = cur.fetchone()
        balance_after = new_portfolio['free_capital'] + new_portfolio['referral_bonus'] + new_portfolio['profits']
        
        # Crea record transazione
        cur.execute("""
            INSERT INTO portfolio_transactions 
            (user_id, type, amount, balance_before, balance_after, description, 
             reference_id, reference_type, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            uid, transaction_type, amount, balance_before, balance_after,
            description, reference_id, reference_type, 'completed'
        ))
        
        transaction_id = cur.fetchone()['id']
        conn.commit()
    
    return jsonify({
        'success': True,
        'transaction_id': transaction_id,
        'message': 'Movimento creato con successo'
    })

@portfolio_api_bp.route('/api/balance', methods=['GET'])
@kyc_verified
def get_current_balance():
    """Ottiene il balance corrente del portafoglio"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            return jsonify({
                'free_capital': 0.0,
                'invested_capital': 0.0,
                'referral_bonus': 0.0,
                'profits': 0.0,
                'total_available': 0.0,
                'total_balance': 0.0
            })
        
        total_available = portfolio['free_capital'] + portfolio['referral_bonus'] + portfolio['profits']
        total_balance = total_available + portfolio['invested_capital']
    
    return jsonify({
        'free_capital': float(portfolio['free_capital']),
        'invested_capital': float(portfolio['invested_capital']),
        'referral_bonus': float(portfolio['referral_bonus']),
        'profits': float(portfolio['profits']),
        'total_available': float(total_available),
        'total_balance': float(total_balance)
    })
