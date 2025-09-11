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
        cur.execute("""
            INSERT INTO project_sales (project_id, sale_price, sale_date, admin_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (project_id, sale_price, sale_date, session.get('user_id')))
        
        sale_id = cur.fetchone()['id']
        
        # Ottieni tutti gli investimenti nel progetto
        cur.execute("""
            SELECT i.id, i.user_id, i.amount, i.percentage
            FROM investments i
            WHERE i.project_id = %s AND i.status = 'active'
        """, (project_id,))
        investments = cur.fetchall()
        
        # Calcola profitti totali
        total_invested = sum(Decimal(str(inv['amount'])) for inv in investments)
        total_profit = sale_price - total_invested
        
        # Crea distribuzioni profitti per ogni investitore
        for investment in investments:
            # Calcola quota profitto proporzionale
            if total_invested > 0:
                profit_share = (investment['amount'] / total_invested) * total_profit
            else:
                profit_share = Decimal('0.00')
            
            # Calcola bonus referral (1% del profitto)
            referral_bonus = profit_share * Decimal('0.01') if profit_share > 0 else Decimal('0.00')
            
            total_payout = profit_share + referral_bonus
            
            # Crea distribuzione profitti
            cur.execute("""
                INSERT INTO profit_distributions 
                (project_sale_id, user_id, investment_id, original_investment, 
                 profit_share, referral_bonus, total_payout, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (sale_id, investment['user_id'], investment['id'], 
                  investment['amount'], profit_share, referral_bonus, total_payout, 'pending'))
            
            # Aggiorna portfolio utente
            if total_profit >= 0:
                # Vendita profittevole: profitti + capitale investito
                cur.execute("""
                    UPDATE user_portfolios 
                    SET profits = profits + %s, 
                        free_capital = free_capital + %s,
                        invested_capital = GREATEST(invested_capital - %s, 0),
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (profit_share, investment['amount'], investment['amount'], investment['user_id']))
            else:
                # Vendita in perdita: solo capitale investito in capitale libero
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = free_capital + %s,
                        invested_capital = GREATEST(invested_capital - %s, 0),
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (investment['amount'], investment['amount'], investment['user_id']))
            
            # Crea transazione portfolio (profitto solo se positivo)
            if total_profit >= 0 and profit_share > 0:
                cur.execute("""
                    INSERT INTO portfolio_transactions 
                    (user_id, type, amount, balance_before, balance_after, description, 
                     reference_id, reference_type, status)
                    SELECT 
                        %s, 'roi', %s, 
                        (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                        (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                        'Rendimento progetto venduto', %s, 'profit_distribution', 'completed'
                    FROM user_portfolios WHERE user_id = %s
                """, (investment['user_id'], profit_share, 
                      investment['user_id'], investment['user_id'],
                      sale_id, investment['user_id']))

            # Transazione portfolio (rilascio capitale investito => capitale libero)
            transaction_description = 'Rilascio capitale investito alla vendita' if total_profit >= 0 else 'Rilascio capitale investito (vendita in perdita)'
            cur.execute("""
                INSERT INTO portfolio_transactions 
                (user_id, type, amount, balance_before, balance_after, description, 
                 reference_id, reference_type, status)
                SELECT 
                    %s, 'capital_release', %s, 
                    (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                    (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                    %s, %s, 'project_sale', 'completed'
                FROM user_portfolios WHERE user_id = %s
            """, (investment['user_id'], investment['amount'], investment['user_id'], investment['user_id'], 
                  transaction_description, sale_id, investment['user_id']))
            
            # Se c'è bonus referral, assegnalo a chi ha invitato l'utente
            if referral_bonus > 0:
                cur.execute("""
                    SELECT referred_by FROM users WHERE id = %s
                """, (investment['user_id'],))
                referrer = cur.fetchone()
                
                if referrer and referrer['referred_by']:
                    # Aggiorna portfolio referrer
                    cur.execute("""
                        UPDATE user_portfolios 
                        SET referral_bonus = referral_bonus + %s, updated_at = NOW()
                        WHERE user_id = %s
                    """, (referral_bonus, referrer['referred_by']))
                    
                    # Crea transazione portfolio referrer
                    cur.execute("""
                        INSERT INTO portfolio_transactions 
                        (user_id, type, amount, balance_before, balance_after, description, 
                         reference_id, reference_type, status)
                        SELECT 
                            %s, 'referral', %s, 
                            (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                            (SELECT free_capital + referral_bonus + profits FROM user_portfolios WHERE user_id = %s),
                            'Bonus referral progetto venduto', %s, 'profit_distribution', 'completed'
                        FROM user_portfolios WHERE user_id = %s
                    """, (referrer['referred_by'], referral_bonus, 
                          referrer['referred_by'], referrer['referred_by'],
                          sale_id, referrer['referred_by']))
        
        # Aggiorna stato progetto a sold e aggiungi dati vendita
        cur.execute("""
            UPDATE projects SET 
                status = 'sold', 
                sale_price = %s,
                sale_date = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (sale_price, sale_date, project_id))
        
        # Aggiorna tutti gli investimenti a completed
        cur.execute("""
            UPDATE investments SET status = 'completed', completion_date = NOW(), updated_at = NOW()
            WHERE project_id = %s AND status = 'active'
        """, (project_id,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'sale_id': sale_id,
        'total_profit': float(total_profit),
        'investors_count': len(investments),
        'message': 'Vendita progetto registrata e profitti distribuiti con successo'
    })
"""

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
            return jsonify({'error': 'Solo le distribuzioni in attesa possono essere pagate'}), 400
        
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

@profits_bp.route('/admin/stats', methods=['GET'])
@admin_required
def admin_get_profits_stats():
    """Admin ottiene statistiche sui rendimenti"""
    
    with get_conn() as conn, conn.cursor() as cur:
        # Statistiche vendite progetti
        cur.execute("""
            SELECT COUNT(*) as total_sales,
                   COALESCE(SUM(sale_price), 0) as total_sale_amount
            FROM project_sales
        """)
        sales_stats = cur.fetchone()
        
        # Statistiche distribuzioni profitti
        cur.execute("""
            SELECT status, COUNT(*) as count, 
                   COALESCE(SUM(profit_share), 0) as total_profit_share,
                   COALESCE(SUM(referral_bonus), 0) as total_referral_bonus
            FROM profit_distributions 
            GROUP BY status
        """)
        distribution_stats = cur.fetchall()
        
        # Statistiche portfolio utenti
        cur.execute("""
            SELECT COUNT(*) as total_users,
                   COALESCE(SUM(profits), 0) as total_profits,
                   COALESCE(SUM(referral_bonus), 0) as total_referral_bonus
            FROM user_portfolios
        """)
        portfolio_stats = cur.fetchone()
    
    return jsonify({
        'sales_stats': sales_stats,
        'distribution_stats': distribution_stats,
        'portfolio_stats': portfolio_stats
    })

@profits_bp.route('/admin/complete-project-sale', methods=['POST'])
@admin_required
def complete_project_sale():
    """Admin completa la vendita di un progetto e distribuisce profitti + referral"""
    data = request.get_json() or {}
    project_id = data.get('project_id')
    sale_price = data.get('sale_price')
    
    if not project_id or not sale_price:
        return jsonify({'error': 'Project ID e sale price richiesti'}), 400

    try:
        sale_price = Decimal(str(sale_price))
    except (ValueError, TypeError):
        return jsonify({'error': 'Sale price non valido'}), 400
    
    try:
            with get_conn() as conn, conn.cursor() as cur:
                # Verifica progetto esiste e ha investimenti
                cur.execute("""
                    SELECT id, name, total_amount, funded_amount
                    FROM projects 
                    WHERE id = %s AND status = 'active'
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({'error': 'Progetto non trovato o non attivo'}), 404
                
                # Ottieni tutti gli investimenti attivi per questo progetto
                cur.execute("""
                    SELECT i.id, i.user_id, i.amount, i.percentage,
                           u.referred_by, u.referral_code
                    FROM investments i
                    JOIN users u ON i.user_id = u.id
                    WHERE i.project_id = %s AND i.status = 'active'
                """, (project_id,))
                investments = cur.fetchall()
                
                if not investments:
                    return jsonify({'error': 'Nessun investimento attivo trovato'}), 400
                
                # Calcola profitti totali
                total_invested = sum(Decimal(str(inv['amount'])) for inv in investments)
                total_profit = sale_price - total_invested
                
                if total_profit < 0:
                    total_profit = Decimal('0.00')  # Non ci sono profitti se la vendita è in perdita
                
                # Registra la vendita
                cur.execute("""
                    INSERT INTO project_sales (project_id, sale_price, sale_date, admin_id)
                    VALUES (%s, %s, NOW(), %s)
                    RETURNING id
                """, (project_id, sale_price, session.get('user_id')))
                
                sale_id = cur.fetchone()['id']
                
                # Distribuisci profitti e referral per ogni investimento
                for investment in investments:
                    user_id = investment['user_id']
                    invested_amount = Decimal(str(investment['amount']))
                    user_percentage = Decimal(str(investment['percentage']))
                    referred_by = investment['referred_by']
                
                # Calcola profitto per questo utente
                user_profit_share = (invested_amount / total_invested) * total_profit if total_invested > 0 else Decimal('0.00')
                
                # Calcola commissione referral (1% del profitto)
                referral_bonus = user_profit_share * Decimal('0.01') if user_profit_share > 0 else Decimal('0.00')
                
                # Calcola payout totale
                total_payout = user_profit_share + referral_bonus
                
                # Registra distribuzione profitti
                cur.execute("""
                    INSERT INTO profit_distributions (
                        project_sale_id, user_id, investment_id, original_investment,
                        profit_share, referral_bonus, total_payout, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (sale_id, user_id, investment['id'], invested_amount, 
                      user_profit_share, referral_bonus, total_payout, 'completed'))
                
                # Aggiorna portfolio utente
                cur.execute("""
                    UPDATE user_portfolios 
                    SET profits = profits + %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (user_profit_share, user_id))
                
                # Se c'è un referral, distribuisci il bonus
                if referred_by and referral_bonus > 0:
                    # Aggiorna portfolio di chi ha fatto il referral
                    cur.execute("""
                        UPDATE user_portfolios 
                        SET referral_bonus = referral_bonus + %s,
                            updated_at = NOW()
                        WHERE user_id = %s
                    """, (referral_bonus, referred_by))
                    
                    # Registra commissione referral
                    cur.execute("""
                        INSERT INTO referral_commissions (
                            referral_id, referrer_id, referred_user_id, investment_id,
                            project_id, investment_amount, commission_amount, status
                        ) VALUES (
                            (SELECT id FROM referrals WHERE referrer_id = %s AND referred_user_id = %s LIMIT 1),
                            %s, %s, %s, %s, %s, %s, 'completed'
                        )
                    """, (referred_by, user_id, referred_by, user_id, investment['id'], 
                          project_id, invested_amount, referral_bonus))
                
                # Aggiorna stato investimento
                cur.execute("""
                    UPDATE investments 
                    SET status = 'completed', completion_date = NOW(), roi_earned = %s
                    WHERE id = %s
                """, (user_profit_share, investment['id']))
            
            # Aggiorna stato progetto
            cur.execute("""
                UPDATE projects 
                SET status = 'completed', end_date = NOW()
                WHERE id = %s
            """, (project_id,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'sale_id': sale_id,
                'total_profit': float(total_profit),
                'investments_processed': len(investments),
                'message': 'Vendita completata e profitti distribuiti con successo'
            })
            
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'Errore durante la distribuzione: {str(e)}'}), 500
