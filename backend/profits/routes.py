"""
Profits API routes - VERSIONE CORRETTA
API per gestione rendimenti: Calcoli e distribuzioni
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

def get_first_code_user_id():
    """
    Restituisce l'ID di Mark Trapella (primo codice) che riceve i bonus
    quando non ci sono referrer o quando i referrer non sono VIP
    """
    return 3  # ID di Mark Trapella nel database

@profits_bp.route('/admin/project-sale', methods=['POST'])
@admin_required
def admin_create_project_sale():
    """
    Vendita progetto con distribuzione fondi secondo la logica richiesta:
    - Vendita in profitto: denaro investito torna in capitale libero + profitti in sezione profitti
    - Vendita in perdita: tutto il denaro rimasto va in capitale libero
    - NUOVO SISTEMA VIP: Sempre 5% viene sottratto dai profitti
      * Se referrer è VIP: riceve il 5% completo
      * Se referrer è normale: riceve 3%, Mark Trapella riceve 2%
      * Se nessun referrer: Mark Trapella riceve il 5% completo
    """
    
    try:
        data = request.get_json() or {}
        
        project_id = data.get('project_id')
        sale_price = float(data.get('sale_price', 0))
        sale_date = data.get('sale_date')
        
        if not project_id or not sale_price or not sale_date:
            return jsonify({
                'success': False,
                'error': 'Dati mancanti: project_id, sale_price, sale_date sono richiesti'
            }), 400
        
        if sale_price <= 0:
            return jsonify({
                'success': False,
                'error': 'Il prezzo di vendita deve essere maggiore di zero'
            }), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Inizia transazione
            conn.autocommit = False
            
            try:
                # 1. Verifica che il progetto esista (può essere active, sold o completed)
                cur.execute("""
                    SELECT id, title, total_amount, funded_amount, status
                    FROM projects 
                    WHERE id = %s
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({
                        'success': False,
                        'error': 'Progetto non trovato'
                    }), 404
                
                # Verifica che il progetto non sia già stato cancellato
                if project['status'] == 'cancelled':
                    return jsonify({
                        'success': False,
                        'error': 'Progetto cancellato, non può essere venduto'
                    }), 400
                
                # 2. Ottieni tutti gli investimenti per questo progetto (esclusi completed e cancelled)
                cur.execute("""
                    SELECT i.id, i.user_id, i.amount, i.status,
                           u.nome, u.cognome, u.email, u.referred_by
                    FROM investments i
                    JOIN users u ON u.id = i.user_id
                    WHERE i.project_id = %s AND i.status NOT IN ('completed', 'cancelled')
                    ORDER BY i.created_at ASC
                """, (project_id,))
                investments = cur.fetchall()
                
                if not investments:
                    return jsonify({
                        'success': False,
                        'error': 'Nessun investimento valido trovato per questo progetto'
                    }), 400
                
                # 3. Calcola la distribuzione del denaro
                total_invested = sum(Decimal(str(inv['amount'])) for inv in investments)
                total_profit = Decimal(str(sale_price)) - total_invested
                
                # 4. Crea record di vendita
                cur.execute("""
                    INSERT INTO project_sales (project_id, sale_amount, roi_distributed)
                    VALUES (%s, %s, %s)
                    RETURNING id
                """, (project_id, sale_price, 0))
                sale_record = cur.fetchone()
                sale_id = sale_record['id']
                
                investors_processed = 0
                referral_bonuses = {}  # Dizionario per accumulare i bonus referral
                
                if total_profit >= 0:  # Vendita in profitto
                    # PRIMA FASE: Calcola tutti i bonus referral secondo la nuova logica
                    # Sempre 5% viene sottratto, distribuito tra referrer e Mark Trapella
                    mark_trapella_id = get_first_code_user_id()
                    mark_trapella_bonus = Decimal('0')
                    
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        profit_share = (invested_amount / total_invested) * total_profit
                        
                        # Sempre sottrai il 5% dai profitti
                        total_referral_deduction = profit_share * Decimal('0.05')
                        
                        if investment['referred_by']:
                            # Controlla se il referrer è VIP
                            cur.execute("SELECT is_vip FROM users WHERE id = %s", (investment['referred_by'],))
                            referrer_data = cur.fetchone()
                            is_vip = referrer_data['is_vip'] if referrer_data else False
                            
                            if is_vip:
                                # VIP riceve il 5% completo
                                referrer_bonus = total_referral_deduction
                                if investment['referred_by'] not in referral_bonuses:
                                    referral_bonuses[investment['referred_by']] = Decimal('0')
                                referral_bonuses[investment['referred_by']] += referrer_bonus
                            else:
                                # Referrer normale riceve 3%, Mark Trapella riceve 2%
                                referrer_bonus = profit_share * Decimal('0.03')
                                mark_bonus = profit_share * Decimal('0.02')
                                
                                if investment['referred_by'] not in referral_bonuses:
                                    referral_bonuses[investment['referred_by']] = Decimal('0')
                                referral_bonuses[investment['referred_by']] += referrer_bonus
                                mark_trapella_bonus += mark_bonus
                        else:
                            # Nessun referrer: Mark Trapella riceve il 5% completo
                            mark_trapella_bonus += total_referral_deduction
                    
                    # SECONDA FASE: Distribuisci profitti e bonus
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        profit_share = (invested_amount / total_invested) * total_profit
                        
                        # Sempre deduci il 5% dai profitti (nuova logica)
                        referral_bonus_to_deduct = profit_share * Decimal('0.05')
                        
                        # Calcola profitto finale DEDUCENDO sempre il 5%
                        final_profit = profit_share - referral_bonus_to_deduct
                        
                        # Ottieni portfolio attuale
                        cur.execute("""
                            SELECT free_capital, profits, invested_capital, referral_bonus
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (user_id,))
                        portfolio = cur.fetchone()
                        
                        if not portfolio:
                            # Crea portfolio se non esiste
                            cur.execute("""
                                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                                VALUES (%s, 0, 0, 0, 0)
                            """, (user_id,))
                            portfolio = {'free_capital': 0, 'profits': 0, 'invested_capital': 0, 'referral_bonus': 0}
                        
                        # Aggiorna portfolio: capitale investito torna in capitale libero + profitti (dopo deduzione bonus)
                        new_free_capital = Decimal(str(portfolio['free_capital'])) + invested_amount
                        new_profits = Decimal(str(portfolio['profits'])) + final_profit
                        new_invested_capital = Decimal(str(portfolio['invested_capital'])) - invested_amount
                        
                        cur.execute("""
                            UPDATE user_portfolios 
                            SET free_capital = %s, 
                                profits = %s, 
                                invested_capital = %s,
                                updated_at = NOW()
                            WHERE user_id = %s
                        """, (new_free_capital, new_profits, new_invested_capital, user_id))
                        
                        # Crea record di distribuzione profitti (con profitto finale dopo deduzione)
                        cur.execute("""
                            INSERT INTO profit_distributions (
                                user_id, investment_id, project_sale_id, 
                                roi_amount, referral_bonus, total_distributed, distribution_date
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (user_id, investment['id'], sale_id, final_profit, referral_bonus_to_deduct, final_profit, sale_date))
                        
                        investors_processed += 1
                
                else:  # Vendita in perdita
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        
                        # Calcola la perdita proporzionale
                        loss_share = (invested_amount / total_invested) * abs(total_profit)
                        returned_amount = invested_amount - loss_share
                        
                        # Ottieni portfolio attuale
                        cur.execute("""
                            SELECT free_capital, invested_capital
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (user_id,))
                        portfolio = cur.fetchone()
                        
                        if not portfolio:
                            # Crea portfolio se non esiste
                            cur.execute("""
                                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                                VALUES (%s, 0, 0, 0, 0)
                            """, (user_id,))
                            portfolio = {'free_capital': 0, 'invested_capital': 0}
                        
                        # Aggiorna portfolio: solo il capitale rimanente torna in capitale libero
                        new_free_capital = Decimal(str(portfolio['free_capital'])) + returned_amount
                        new_invested_capital = Decimal(str(portfolio['invested_capital'])) - invested_amount
                        
                        cur.execute("""
                            UPDATE user_portfolios 
                            SET free_capital = %s, 
                                invested_capital = %s,
                                updated_at = NOW()
                            WHERE user_id = %s
                        """, (new_free_capital, new_invested_capital, user_id))
                        
                        # Crea record di distribuzione (con perdita)
                        cur.execute("""
                            INSERT INTO profit_distributions (
                                user_id, investment_id, project_sale_id, 
                                roi_amount, referral_bonus, total_distributed, distribution_date
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (user_id, investment['id'], sale_id, -loss_share, 0, returned_amount, sale_date))
                        
                        investors_processed += 1
                
                # 5. Distribuisci bonus referral (solo per vendite in profitto)
                if total_profit >= 0 and referral_bonuses:
                    for referrer_id, bonus_amount in referral_bonuses.items():
                        # Ottieni portfolio del referrer
                        cur.execute("""
                            SELECT referral_bonus
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (referrer_id,))
                        referrer_portfolio = cur.fetchone()
                        
                        if referrer_portfolio:
                            new_referral_bonus = Decimal(str(referrer_portfolio['referral_bonus'])) + bonus_amount
                            cur.execute("""
                                UPDATE user_portfolios 
                                SET referral_bonus = %s,
                                    updated_at = NOW()
                                WHERE user_id = %s
                            """, (new_referral_bonus, referrer_id))
                        else:
                            # Crea portfolio se non esiste
                            cur.execute("""
                                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                                VALUES (%s, 0, 0, 0, %s)
                            """, (referrer_id, bonus_amount))
                
                # 6. Distribuisci bonus a Mark Trapella (primo codice)
                if total_profit >= 0 and mark_trapella_bonus > 0:
                    # Ottieni portfolio di Mark Trapella
                    cur.execute("""
                        SELECT referral_bonus
                        FROM user_portfolios 
                        WHERE user_id = %s
                    """, (mark_trapella_id,))
                    mark_portfolio = cur.fetchone()
                    
                    if mark_portfolio:
                        new_referral_bonus = Decimal(str(mark_portfolio['referral_bonus'])) + mark_trapella_bonus
                        cur.execute("""
                            UPDATE user_portfolios 
                            SET referral_bonus = %s,
                                updated_at = NOW()
                            WHERE user_id = %s
                        """, (new_referral_bonus, mark_trapella_id))
                    else:
                        # Crea portfolio se non esiste
                        cur.execute("""
                            INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                            VALUES (%s, 0, 0, 0, %s)
                        """, (mark_trapella_id, mark_trapella_bonus))
                
                # 7. Aggiorna lo stato del progetto
                profit_percentage = ((sale_price - float(total_invested)) / float(total_invested)) * 100 if total_invested > 0 else 0
                cur.execute("""
                    UPDATE projects 
                    SET status = 'sold', 
                        sale_price = %s,
                        sale_date = %s,
                        profit_percentage = %s,
                        sold_by_admin_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (sale_price, sale_date, profit_percentage, session.get('user_id'), project_id))
                
                # 8. Marca tutti gli investimenti come completati
                cur.execute("""
                    UPDATE investments 
                    SET status = 'completed', 
                        completed_at = NOW()
                    WHERE project_id = %s AND status NOT IN ('completed', 'cancelled')
                """, (project_id,))
                
                # Commit della transazione
                conn.commit()
                conn.autocommit = True
                
                return jsonify({
                    'success': True,
                    'message': f'Vendita completata con successo!',
                    'project_id': project_id,
                    'sale_price': sale_price,
                    'sale_date': sale_date,
                    'investors_count': investors_processed,
                    'total_invested': float(total_invested),
                    'total_profit': float(total_profit),
                    'profit_percentage': round(profit_percentage, 2),
                    'referral_bonuses_distributed': len(referral_bonuses),
                    'sale_type': 'profit' if total_profit >= 0 else 'loss'
                })
                
            except Exception as e:
                # Rollback in caso di errore
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
    """Admin annulla un progetto attivo e restituisce tutti i fondi al capitale libero"""
    
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'ID progetto richiesto'
            }), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Inizia transazione
            conn.autocommit = False
            
            try:
                # 1. Verifica che il progetto esista e sia attivo
                cur.execute("""
                    SELECT id, title, total_amount, funded_amount, status
                    FROM projects 
                    WHERE id = %s AND status = 'active'
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({
                        'success': False,
                        'error': 'Progetto non trovato o non attivo'
                    }), 404
                
                # 2. Ottieni tutti gli investimenti per questo progetto (esclusi completed e cancelled)
                cur.execute("""
                    SELECT i.id, i.user_id, i.amount, i.status,
                           u.nome, u.cognome, u.email
                    FROM investments i
                    JOIN users u ON u.id = i.user_id
                    WHERE i.project_id = %s AND i.status NOT IN ('completed', 'cancelled')
                    ORDER BY i.created_at ASC
                """, (project_id,))
                investments = cur.fetchall()
                
                # Se non ci sono investimenti attivi, procedi comunque con l'annullamento
                
                # 3. Restituisci tutti i fondi al capitale libero (solo se ci sono investimenti)
                investors_processed = 0
                total_refunded = Decimal('0')
                
                if investments:
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        total_refunded += invested_amount
                        
                        # Ottieni portfolio attuale
                        cur.execute("""
                            SELECT free_capital, invested_capital
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (user_id,))
                        portfolio = cur.fetchone()
                        
                        if not portfolio:
                            # Crea portfolio se non esiste
                            cur.execute("""
                                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                                VALUES (%s, 0, 0, 0, 0)
                            """, (user_id,))
                            portfolio = {'free_capital': 0, 'invested_capital': 0}
                        
                        # Aggiorna portfolio: restituisci al capitale libero
                        new_free_capital = Decimal(str(portfolio['free_capital'])) + invested_amount
                        new_invested_capital = Decimal(str(portfolio['invested_capital'])) - invested_amount
                        
                        cur.execute("""
                            UPDATE user_portfolios 
                            SET free_capital = %s, invested_capital = %s
                            WHERE user_id = %s
                        """, (new_free_capital, new_invested_capital, user_id))
                        
                        investors_processed += 1
                
                # 4. Aggiorna lo stato del progetto a 'cancelled'
                cur.execute("""
                    UPDATE projects 
                    SET status = 'cancelled'
                    WHERE id = %s
                """, (project_id,))
                
                # 5. Marca tutti gli investimenti come cancellati
                cur.execute("""
                    UPDATE investments 
                    SET status = 'cancelled'
                    WHERE project_id = %s AND status NOT IN ('completed', 'cancelled')
                """, (project_id,))
                
                # Commit della transazione
                conn.commit()
                conn.autocommit = True
                
                if investors_processed > 0:
                    message = f'Progetto annullato con successo! Restituiti €{total_refunded} a {investors_processed} investitori.'
                else:
                    message = 'Progetto annullato con successo! Nessun investimento attivo da restituire.'
                
                return jsonify({
                    'success': True,
                    'message': message,
                    'project_id': project_id,
                    'investors_count': investors_processed,
                    'total_refunded': float(total_refunded)
                })
                
            except Exception as e:
                # Rollback in caso di errore
                conn.rollback()
                conn.autocommit = True
                raise e
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore durante l\'annullamento: {str(e)}'
        }), 500

@profits_bp.route('/admin/project-delete', methods=['POST'])
@admin_required
def admin_delete_project():
    """Admin elimina permanentemente un progetto venduto"""
    
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        
        if not project_id:
            return jsonify({
                'success': False,
                'error': 'ID progetto richiesto'
            }), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Inizia transazione
            conn.autocommit = False
            
            try:
                # 1. Verifica che il progetto esista e sia venduto
                cur.execute("""
                    SELECT id, title, status
                    FROM projects 
                    WHERE id = %s AND status = 'sold'
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({
                        'success': False,
                        'error': 'Progetto non trovato o non venduto'
                    }), 404
                
                # 2. Elimina tutti i record correlati (in ordine per evitare errori di foreign key)
                
                # Elimina distribuzioni profitti
                cur.execute("""
                    DELETE FROM profit_distributions 
                    WHERE project_sale_id IN (
                        SELECT id FROM project_sales WHERE project_id = %s
                    )
                """, (project_id,))
                
                # Elimina vendite progetto
                cur.execute("""
                    DELETE FROM project_sales 
                    WHERE project_id = %s
                """, (project_id,))
                
                # Elimina investimenti
                cur.execute("""
                    DELETE FROM investments 
                    WHERE project_id = %s
                """, (project_id,))
                
                # 3. Elimina il progetto stesso
                cur.execute("""
                    DELETE FROM projects 
                    WHERE id = %s
                """, (project_id,))
                
                # Commit della transazione
                conn.commit()
                conn.autocommit = True
                
                return jsonify({
                    'success': True,
                    'message': f'Progetto "{project["title"]}" eliminato permanentemente dal sistema.',
                    'project_id': project_id
                })
                
            except Exception as e:
                # Rollback in caso di errore
                conn.rollback()
                conn.autocommit = True
                raise e
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Errore durante l\'eliminazione: {str(e)}'
        }), 500
