"""
Profits API routes
API per gestione rendimenti: Calcoli e distribuzioni
"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
from backend.shared.models import TransactionStatus

profits_bp = Blueprint("profits", __name__, url_prefix="/api")

def get_conn():
    return get_connection()

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, can_access_portfolio, admin_required

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 5. RENDIMENTI API - Calcoli e distribuzioni
# =====================================================

@profits_bp.route('/overview', methods=['GET'])
@can_access_portfolio
def get_profits_overview():
    """Ottiene l'overview dei rendimenti dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni profitti totali dal portfolio
        cur.execute("""
            SELECT profits FROM user_portfolios WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        total_profits = portfolio['profits'] if portfolio else Decimal('0.00')
        
        # Ottieni investimenti attivi con ROI potenziale
        cur.execute("""
            SELECT i.id, i.amount, i.percentage, i.investment_date,
                   p.name as project_name, p.code as project_code, p.roi
            FROM investments i
            JOIN projects p ON i.project_id = p.id
            WHERE i.user_id = %s AND i.status = 'active'
            ORDER BY i.investment_date ASC
        """, (uid,))
        active_investments = cur.fetchall()
        
        # Calcola ROI potenziale per ogni investimento
        for investment in active_investments:
            investment['potential_roi'] = float(investment['amount'] * investment['roi'] / 100)
        
        # Ottieni distribuzioni profitti ricevute
        cur.execute("""
            SELECT pd.profit_share, pd.referral_bonus, pd.total_payout, pd.paid_at,
                   p.name as project_name, ps.sale_price, ps.sale_date
            FROM profit_distributions pd
            JOIN project_sales ps ON pd.project_sale_id = ps.id
            JOIN projects p ON ps.project_id = p.id
            WHERE pd.user_id = %s AND pd.status = 'completed'
            ORDER BY pd.paid_at DESC
        """, (uid,))
        profit_distributions = cur.fetchall()
        
        # Calcola totali
        total_profit_share = sum(Decimal(str(d['profit_share'])) for d in profit_distributions)
        total_referral_bonus = sum(Decimal(str(d['referral_bonus'])) for d in profit_distributions)
        total_payouts = sum(Decimal(str(d['total_payout'])) for d in profit_distributions)
    
    return jsonify({
        'total_profits': float(total_profits),
        'active_investments': active_investments,
        'profit_distributions': profit_distributions,
        'summary': {
            'total_profit_share': float(total_profit_share),
            'total_referral_bonus': float(total_referral_bonus),
            'total_payouts': float(total_payouts)
        }
    })

@profits_bp.route('/investments/<int:investment_id>/roi', methods=['GET'])
@can_access_portfolio
def get_investment_roi(investment_id):
    """Ottiene i dettagli ROI di un investimento specifico"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica proprietà investimento
        cur.execute("""
            SELECT i.id, i.amount, i.percentage, i.status, i.investment_date,
                   p.name as project_name, p.code as project_code, p.roi, p.total_amount
            FROM investments i
            JOIN projects p ON i.project_id = p.id
            WHERE i.id = %s AND i.user_id = %s
        """, (investment_id, uid))
        investment = cur.fetchone()
        
        if not investment:
            return jsonify({'error': 'Investimento non trovato'}), 404
        
        # Calcola ROI potenziale
        potential_roi = investment['amount'] * investment['roi'] / 100
        
        # Ottieni rendimenti già ricevuti
        cur.execute("""
            SELECT amount, period_start, period_end, created_at
            FROM investment_yields 
            WHERE investment_id = %s
            ORDER BY period_end DESC
        """, (investment_id,))
        yields = cur.fetchall()
        
        total_yields = sum(Decimal(str(y['amount'])) for y in yields)
        
        # Calcola ROI realizzato vs potenziale
        roi_realized = total_yields
        roi_pending = potential_roi - total_yields if potential_roi > total_yields else Decimal('0.00')
    
    return jsonify({
        'investment': investment,
        'roi_calculation': {
            'potential_roi': float(potential_roi),
            'realized_roi': float(roi_realized),
            'pending_roi': float(roi_pending),
            'roi_percentage': float(investment['roi'])
        },
        'yields': yields,
        'total_yields': float(total_yields)
    })

@profits_bp.route('/distributions', methods=['GET'])
@can_access_portfolio
def get_profit_distributions():
    """Ottiene tutte le distribuzioni profitti dell'utente"""
    uid = session.get("user_id")
    
    # Parametri di filtro
    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 50)), 100)  # Max 100
    offset = int(request.args.get('offset', 0))
    
    with get_conn() as conn, conn.cursor() as cur:
        # Costruisci query con filtri
        where_conditions = ["pd.user_id = %s"]
        params = [uid]
        
        if status:
            where_conditions.append("pd.status = %s")
            params.append(status)
        
        where_clause = " AND ".join(where_conditions)
        
        # Conta totale distribuzioni
        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM profit_distributions pd
            WHERE {where_clause}
        """, params)
        total_count = cur.fetchone()['total']
        
        # Ottieni distribuzioni paginate
        cur.execute(f"""
            SELECT pd.id, pd.profit_share, pd.referral_bonus, pd.total_payout,
                   pd.status, pd.created_at, pd.paid_at,
                   p.name as project_name, p.code as project_code,
                   ps.sale_price, ps.sale_date
            FROM profit_distributions pd
            JOIN project_sales ps ON pd.project_sale_id = ps.id
            JOIN projects p ON ps.project_id = p.id
            WHERE {where_clause}
            ORDER BY pd.created_at DESC 
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        distributions = cur.fetchall()
    
    return jsonify({
        'distributions': distributions,
        'pagination': {
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count
        }
    })

@profits_bp.route('/distributions/<int:distribution_id>', methods=['GET'])
@can_access_portfolio
def get_profit_distribution_detail(distribution_id):
    """Ottiene i dettagli di una distribuzione profitti specifica"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT pd.id, pd.profit_share, pd.referral_bonus, pd.total_payout,
                   pd.status, pd.created_at, pd.paid_at,
                   p.name as project_name, p.code as project_code,
                   ps.sale_price, ps.sale_date
            FROM profit_distributions pd
            JOIN project_sales ps ON pd.project_sale_id = ps.id
            JOIN projects p ON ps.project_id = p.id
            WHERE pd.id = %s AND pd.user_id = %s
        """, (distribution_id, uid))
        distribution = cur.fetchone()
        
        if not distribution:
            return jsonify({'error': 'Distribuzione non trovata'}), 404
    
    return jsonify({'distribution': distribution})

@profits_bp.route('/referral-bonuses', methods=['GET'])
@can_access_portfolio
def get_referral_bonuses():
    """Ottiene i bonus referral dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni bonus referral dal portfolio
        cur.execute("""
            SELECT referral_bonus FROM user_portfolios WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        total_referral_bonus = portfolio['referral_bonus'] if portfolio else Decimal('0.00')
        
        # Ottieni dettagli bonus referral
        cur.execute("""
            SELECT pd.referral_bonus, pd.created_at,
                   p.name as project_name, p.code as project_code,
                   u.full_name as referred_user_name, u.email as referred_user_email
            FROM profit_distributions pd
            JOIN project_sales ps ON pd.project_sale_id = ps.id
            JOIN projects p ON ps.project_id = p.id
            JOIN investments i ON pd.investment_id = i.id
            JOIN users u ON i.user_id = u.id
            WHERE pd.user_id = %s AND pd.referral_bonus > 0
            ORDER BY pd.created_at DESC
        """, (uid,))
        referral_details = cur.fetchall()
        
        # Ottieni statistiche referral
        cur.execute("""
            SELECT COUNT(*) as total_referrals,
                   COUNT(CASE WHEN u.kyc_status = 'verified' THEN 1 END) as verified_referrals
            FROM users u WHERE u.referred_by = %s
        """, (uid,))
        referral_stats = cur.fetchone()
    
    return jsonify({
        'total_referral_bonus': float(total_referral_bonus),
        'referral_details': referral_details,
        'referral_stats': referral_stats
    })

# =====================================================
# ENDPOINT ADMIN (richiedono ruolo admin)
# =====================================================

@profits_bp.route('/test-sale', methods=['POST'])
def test_project_sale():
    """ENDPOINT TEMPORANEO - Test vendita progetto senza autenticazione"""
    try:
        data = request.get_json() or {}
        return jsonify({
            'success': True,
            'message': 'Test endpoint funzionante',
            'received_data': data,
            'note': 'Questo è un endpoint di test - rimuovere in produzione'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore test endpoint: {str(e)}'
        }), 500

@profits_bp.route('/admin/project-sale', methods=['POST'])
def admin_create_project_sale():
    """Admin crea una vendita progetto per calcolare rendimenti - VERSIONE TEST"""
    
    try:
        data = request.get_json() or {}
        
        # TEST: Verifica che i dati arrivino correttamente
        project_id = data.get('project_id')
        sale_price = data.get('sale_price')
        sale_date = data.get('sale_date')
        
        if not project_id or not sale_price or not sale_date:
            return jsonify({
                'success': False,
                'error': 'Dati mancanti: project_id, sale_price, sale_date sono richiesti'
            }), 400
        
        # Per ora, restituisci successo per testare la connettività
        return jsonify({
            'success': True,
            'message': f'VENDITA SIMULATA COMPLETATA per progetto {project_id}',
            'project_id': project_id,
            'sale_price': sale_price,
            'sale_date': sale_date,
            'investors_count': 4,  # Simulato
            'note': 'Questa è una simulazione - la vendita reale sarà implementata dopo i test'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore endpoint: {str(e)}'
        }), 500

@profits_bp.route('/admin/distributions/pay/<int:distribution_id>', methods=['POST'])
@admin_required
def admin_pay_profit_distribution(distribution_id):
    """Admin marca una distribuzione profitti come pagata"""
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica distribuzione esiste e è pending
        cur.execute("""
            SELECT id, status FROM profit_distributions 
            WHERE id = %s
        """, (distribution_id,))
        distribution = cur.fetchone()
        
        if not distribution:
            return jsonify({'error': 'Distribuzione non trovata'}), 404
        
        if distribution['status'] != 'pending':
            return jsonify({'error': 'Distribuzione già processata'}), 400
        
        # Marca come pagata
        cur.execute("""
            UPDATE profit_distributions 
            SET status = 'completed', paid_at = NOW()
            WHERE id = %s
        """, (distribution_id,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Distribuzione profitti marcata come pagata'
    })
