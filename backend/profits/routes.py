"""
Profits API routes - NUOVO SISTEMA VENDITA
API per gestione vendite progetti con logica corretta
"""

from datetime import datetime
from decimal import Decimal
from flask import Blueprint, request, session, jsonify
from backend.shared.database import get_connection
from backend.shared.models import TransactionStatus

profits_bp = Blueprint("profits", __name__, url_prefix="/api")

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, kyc_verified, admin_required

# ============================================================================
# FUNZIONI HELPER
# ============================================================================

def get_default_referral_user_id():
    """
    Restituisce l'ID dell'utente che riceve i bonus referral di default
    """
    return 2  # ID di Cip nel database

@profits_bp.route('/admin/project-sale', methods=['POST'])
@admin_required
def admin_create_project_sale():
    """
    NUOVO SISTEMA VENDITA PROGETTO
    
    Logica:
    1. Trova tutti gli investimenti attivi per il progetto
    2. Calcola profitto totale (prezzo vendita - totale investito)
    3. Per ogni investitore:
       - Capitale investito → Capitale libero
       - Profitto → Profitti
    4. Applica logica referral (5% totale):
       - Se referrer VIP: riceve 5%
       - Se referrer normale: riceve 3%, default riceve 2%
       - Se nessun referrer: default riceve 5%
    5. Aggiorna progetto a "sold"
    6. Marca investimenti come "completed"
    """
    
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        sale_price = float(data.get('sale_price', 0))
        sale_date = data.get('sale_date')
        
        if not project_id or not sale_price or not sale_date:
            return jsonify({
                'success': False,
                'error': 'Parametri mancanti: project_id, sale_price, sale_date'
            }), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # 1. Verifica che il progetto esista e sia vendibile
            cur.execute("""
                SELECT id, title, status, funded_amount
                FROM projects 
                WHERE id = %s
            """, (project_id,))
            project = cur.fetchone()
            
            if not project:
                return jsonify({
                    'success': False,
                    'error': 'Progetto non trovato'
                }), 404
            
            if project['status'] == 'cancelled':
                return jsonify({
                    'success': False,
                    'error': 'Progetto cancellato, non può essere venduto'
                }), 400
            
            # 2. Trova tutti gli investimenti attivi per questo progetto
            cur.execute("""
                SELECT i.id, i.user_id, i.amount, i.status,
                       u.nome, u.cognome, u.email, u.referred_by, u.is_vip
                FROM investments i
                JOIN users u ON u.id = i.user_id
                WHERE i.project_id = %s AND i.status = 'active'
                ORDER BY i.created_at ASC
            """, (project_id,))
            investments = cur.fetchall()
            
            if not investments:
                return jsonify({
                    'success': False,
                    'error': 'Nessun investimento attivo trovato per questo progetto'
                }), 400
            
            # 3. Calcola totali
            total_invested = sum(Decimal(str(inv['amount'])) for inv in investments)
            total_profit = Decimal(str(sale_price)) - total_invested
            
            # 4. Crea record di vendita
            cur.execute("""
                INSERT INTO project_sales (project_id, sale_amount, roi_distributed)
                VALUES (%s, %s, %s)
                RETURNING id
            """, (project_id, sale_price, True))
            sale_record = cur.fetchone()
            sale_id = sale_record['id']
            
            # 5. Distribuisci fondi per ogni investitore
            investors_processed = 0
            referral_bonuses = {}
            default_user_id = get_default_referral_user_id()
            
            for investment in investments:
                user_id = investment['user_id']
                invested_amount = Decimal(str(investment['amount']))
                profit_share = (invested_amount / total_invested) * total_profit if total_invested > 0 else Decimal('0')
                
                # Calcola profitto finale (dopo deduzione referral)
                referral_deduction = profit_share * Decimal('0.05')  # 5% per referral
                final_profit = profit_share - referral_deduction
                
                # Aggiorna portafoglio utente
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = free_capital + %s + %s,
                        profits = profits + %s,
                        invested_capital = invested_capital - %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (invested_amount, final_profit, final_profit, invested_amount, user_id))
                
                # Registra transazione
                cur.execute("""
                    INSERT INTO portfolio_transactions (
                        user_id, type, amount, balance_before, balance_after,
                        description, reference_id, reference_type, status, created_at
                    ) VALUES (
                        %s, 'sale_profit', %s, 0, 0,
                        'Vendita progetto - Capitale restituito + Profitto', %s, 'project_sale', 'completed', NOW()
                    )
                """, (user_id, invested_amount + final_profit, sale_id))
                
                # Gestisci referral bonus
                if investment['referred_by']:
                    referrer_id = investment['referred_by']
                    
                    # Verifica se referrer è VIP
                    cur.execute("SELECT is_vip FROM users WHERE id = %s", (referrer_id,))
                    referrer = cur.fetchone()
                    is_vip = referrer['is_vip'] if referrer else False
                    
                    if is_vip:
                        # Referrer VIP riceve 5% completo
                        referrer_bonus = referral_deduction
                        default_bonus = Decimal('0')
                    else:
                        # Referrer normale riceve 3%, default riceve 2%
                        referrer_bonus = profit_share * Decimal('0.03')
                        default_bonus = profit_share * Decimal('0.02')
                    
                    # Aggiorna referrer
                    if referrer_bonus > 0:
                        if referrer_id not in referral_bonuses:
                            referral_bonuses[referrer_id] = Decimal('0')
                        referral_bonuses[referrer_id] += referrer_bonus
                    
                    # Aggiorna default user
                    if default_bonus > 0:
                        if default_user_id not in referral_bonuses:
                            referral_bonuses[default_user_id] = Decimal('0')
                        referral_bonuses[default_user_id] += default_bonus
                else:
                    # Nessun referrer: default riceve 5% completo
                    if default_user_id not in referral_bonuses:
                        referral_bonuses[default_user_id] = Decimal('0')
                    referral_bonuses[default_user_id] += referral_deduction
                
                # Crea record distribuzione profitti
                cur.execute("""
                    INSERT INTO profit_distributions (
                        user_id, investment_id, project_sale_id, 
                        roi_amount, referral_bonus, total_distributed, distribution_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (user_id, investment['id'], sale_id, final_profit, Decimal('0'), final_profit, sale_date))
                
                investors_processed += 1
            
            # 6. Distribuisci referral bonuses
            for bonus_user_id, bonus_amount in referral_bonuses.items():
                if bonus_amount > 0:
                    # Aggiorna portafoglio referrer
                    cur.execute("""
                        UPDATE user_portfolios 
                        SET referral_bonus = referral_bonus + %s,
                            updated_at = NOW()
                        WHERE user_id = %s
                    """, (bonus_amount, bonus_user_id))
                    
                    # Registra transazione referral
                    cur.execute("""
                        INSERT INTO portfolio_transactions (
                            user_id, type, amount, balance_before, balance_after,
                            description, reference_id, reference_type, status, created_at
                        ) VALUES (
                            %s, 'referral_bonus', %s, 0, 0,
                            'Bonus referral da vendita progetto', %s, 'project_sale', 'completed', NOW()
                        )
                    """, (bonus_user_id, bonus_amount, sale_id))
            
            # 7. Aggiorna progetto a "sold"
            cur.execute("""
                UPDATE projects 
                SET status = 'sold', 
                    sale_price = %s,
                    sale_date = %s,
                    profit_percentage = %s,
                    sold_by_admin_id = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (sale_price, sale_date, 
                  float((total_profit / total_invested) * 100) if total_invested > 0 else 0,
                  session.get('user_id'), project_id))
            
            # 8. Marca investimenti come completati
            cur.execute("""
                UPDATE investments 
                SET status = 'completed', 
                    completed_at = NOW()
                WHERE project_id = %s AND status = 'active'
            """, (project_id,))
            
            # Commit della transazione
            conn.commit()
            conn.autocommit = True
            
            return jsonify({
                'success': True,
                'message': f'Vendita completata con successo!',
                'data': {
                    'project_id': project_id,
                    'sale_price': float(sale_price),
                    'total_invested': float(total_invested),
                    'total_profit': float(total_profit),
                    'investors_count': investors_processed,
                    'profit_percentage': float((total_profit / total_invested) * 100) if total_invested > 0 else 0
                }
            })
            
        except Exception as e:
            conn.rollback()
            conn.autocommit = True
            raise e
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore durante la vendita: {str(e)}'
        }), 500

@profits_bp.route('/admin/project-cancel', methods=['POST'])
@admin_required
def admin_cancel_project():
    """
    Annulla progetto e restituisce tutto il denaro investito
    """
    
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'Project ID mancante'
            }), 400
        
        conn = get_conn()
        cur = conn.cursor()
        
        try:
            # Trova investimenti attivi
            cur.execute("""
                SELECT i.id, i.user_id, i.amount
                FROM investments i
                WHERE i.project_id = %s AND i.status = 'active'
            """, (project_id,))
            investments = cur.fetchall()
            
            # Restituisci fondi a ogni investitore
            for investment in investments:
                user_id = investment['user_id']
                amount = Decimal(str(investment['amount']))
                
                # Aggiorna portafoglio
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = free_capital + %s,
                        invested_capital = invested_capital - %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (amount, amount, user_id))
                
                # Registra transazione
                cur.execute("""
                    INSERT INTO portfolio_transactions (
                        user_id, type, amount, balance_before, balance_after,
                        description, reference_id, reference_type, status, created_at
                    ) VALUES (
                        %s, 'project_cancelled', %s, 0, 0,
                        'Progetto annullato - Capitale restituito', %s, 'project', 'completed', NOW()
                    )
                """, (user_id, amount, project_id))
            
            # Aggiorna progetto
            cur.execute("""
                UPDATE projects 
                SET status = 'cancelled',
                    updated_at = NOW()
                WHERE id = %s
            """, (project_id,))
            
            # Marca investimenti come cancellati
            cur.execute("""
                UPDATE investments 
                SET status = 'cancelled'
                WHERE project_id = %s AND status = 'active'
            """, (project_id,))
            
            conn.commit()
            conn.autocommit = True
            
            return jsonify({
                'success': True,
                'message': 'Progetto annullato con successo',
                'investors_refunded': len(investments)
            })
            
        except Exception as e:
            conn.rollback()
            conn.autocommit = True
            raise e
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore durante l\'annullamento: {str(e)}'
        }), 500