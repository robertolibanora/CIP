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
from backend.auth.decorators import login_required, kyc_verified, admin_required

@profits_bp.route('/admin/project-sale', methods=['POST'])
@admin_required
def admin_create_project_sale():
    """Admin crea una vendita progetto e distribuisce i fondi secondo la logica richiesta:
    - Vendita in profitto: denaro investito torna in capitale libero + profitti in sezione profitti
    - Vendita in perdita: tutto il denaro rimasto va in capitale libero
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
                # 1. Verifica che il progetto esista e sia attivo
                cur.execute("""
                    SELECT id, name, total_amount, funded_amount, status
                    FROM projects 
                    WHERE id = %s AND status = 'active'
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({
                        'success': False,
                        'error': 'Progetto non trovato o non attivo'
                    }), 404
                
                # 2. Ottieni tutti gli investimenti attivi per questo progetto
                cur.execute("""
                    SELECT i.id, i.user_id, i.amount, i.status,
                           u.nome, u.cognome, u.email
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
                
                # 3. Calcola la distribuzione del denaro
                total_invested = sum(Decimal(str(inv['amount'])) for inv in investments)
                total_profit = Decimal(str(sale_price)) - total_invested
                
                # 4. Crea record di vendita
                cur.execute("""
                    INSERT INTO project_sales (project_id, sale_amount, sale_date, roi_distributed)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (project_id, sale_price, sale_date, 0))
                sale_record = cur.fetchone()
                sale_id = sale_record['id']
                
                investors_processed = 0
                
                if total_profit >= 0:  # Vendita in profitto
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        profit_share = (invested_amount / total_invested) * total_profit
                        
                        # Ottieni portfolio attuale
                        cur.execute("""
                            SELECT free_capital, profits, invested_capital
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (user_id,))
                        portfolio = cur.fetchone()
                        
                        if portfolio:
                            # Aggiorna portfolio
                            new_free_capital = portfolio['free_capital'] + invested_amount
                            new_profits = portfolio['profits'] + profit_share
                            new_invested_capital = portfolio['invested_capital'] - invested_amount
                            
                            cur.execute("""
                                UPDATE user_portfolios 
                                SET free_capital = %s, profits = %s, invested_capital = %s
                                WHERE user_id = %s
                            """, (new_free_capital, new_profits, new_invested_capital, user_id))
                            
                            # Registra transazioni
                            cur.execute("""
                                INSERT INTO portfolio_transactions 
                                (user_id, type, amount, balance_before, balance_after, description, reference_type, reference_id, status)
                                VALUES (%s, 'investment', %s, %s, %s, %s, 'project_sale', %s, 'completed')
                            """, (user_id, invested_amount, portfolio['free_capital'], new_free_capital, 
                                  f"Restituzione capitale investito - Vendita {project['name']}", sale_id))
                            
                            if profit_share > 0:
                                cur.execute("""
                                    INSERT INTO portfolio_transactions 
                                    (user_id, type, amount, balance_before, balance_after, description, reference_type, reference_id, status)
                                    VALUES (%s, 'roi', %s, %s, %s, %s, 'project_sale', %s, 'completed')
                                """, (user_id, profit_share, portfolio['profits'], new_profits, 
                                      f"Profitto vendita progetto - {project['name']}", sale_id))
                            
                            # Registra distribuzione profitti
                            cur.execute("""
                                INSERT INTO profit_distributions 
                                (project_sale_id, user_id, investment_id, roi_amount, referral_bonus, total_distributed, distribution_date)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (sale_id, user_id, investment['id'], profit_share, 0, 
                                  invested_amount + profit_share, sale_date))
                            
                            investors_processed += 1
                
                else:  # Vendita in perdita
                    for investment in investments:
                        user_id = investment['user_id']
                        invested_amount = Decimal(str(investment['amount']))
                        loss_ratio = Decimal(str(sale_price)) / total_invested
                        returned_amount = invested_amount * loss_ratio
                        
                        # Ottieni portfolio attuale
                        cur.execute("""
                            SELECT free_capital, invested_capital
                            FROM user_portfolios 
                            WHERE user_id = %s
                        """, (user_id,))
                        portfolio = cur.fetchone()
                        
                        if portfolio:
                            # Aggiorna portfolio
                            new_free_capital = portfolio['free_capital'] + returned_amount
                            new_invested_capital = portfolio['invested_capital'] - invested_amount
                            
                            cur.execute("""
                                UPDATE user_portfolios 
                                SET free_capital = %s, invested_capital = %s
                                WHERE user_id = %s
                            """, (new_free_capital, new_invested_capital, user_id))
                            
                            # Registra transazione
                            cur.execute("""
                                INSERT INTO portfolio_transactions 
                                (user_id, type, amount, balance_before, balance_after, description, reference_type, reference_id, status)
                                VALUES (%s, 'investment', %s, %s, %s, %s, 'project_sale', %s, 'completed')
                            """, (user_id, returned_amount, portfolio['free_capital'], new_free_capital, 
                                  f"Restituzione parziale capitale - Vendita in perdita {project['name']}", sale_id))
                            
                            # Registra distribuzione profitti
                            cur.execute("""
                                INSERT INTO profit_distributions 
                                (project_sale_id, user_id, investment_id, roi_amount, referral_bonus, total_distributed, distribution_date)
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (sale_id, user_id, investment['id'], 0, 0, returned_amount, sale_date))
                            
                            investors_processed += 1
                
                # 5. Aggiorna lo stato del progetto
                cur.execute("""
                    UPDATE projects 
                    SET status = 'sold', 
                        sale_price = %s,
                        sale_date = %s,
                        sold_by_admin_id = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (sale_price, sale_date, session.get('user_id'), project_id))
                
                # 6. Marca tutti gli investimenti come completati
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
                    'project_id': project_id,
                    'sale_price': sale_price,
                    'sale_date': sale_date,
                    'investors_count': investors_processed,
                    'total_invested': float(total_invested),
                    'total_profit': float(total_profit),
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
                    SELECT id, name, total_amount, funded_amount, status
                    FROM projects 
                    WHERE id = %s AND status = 'active'
                """, (project_id,))
                project = cur.fetchone()
                
                if not project:
                    return jsonify({
                        'success': False,
                        'error': 'Progetto non trovato o non attivo'
                    }), 404
                
                # 2. Ottieni tutti gli investimenti attivi per questo progetto
                cur.execute("""
                    SELECT i.id, i.user_id, i.amount, i.status,
                           u.nome, u.cognome, u.email
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
                
                # 3. Restituisci tutti i fondi al capitale libero
                investors_processed = 0
                total_refunded = Decimal('0')
                
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
                    
                    if portfolio:
                        # Aggiorna portfolio: restituisci al capitale libero
                        new_free_capital = portfolio['free_capital'] + invested_amount
                        new_invested_capital = portfolio['invested_capital'] - invested_amount
                        
                        cur.execute("""
                            UPDATE user_portfolios 
                            SET free_capital = %s, invested_capital = %s
                            WHERE user_id = %s
                        """, (new_free_capital, new_invested_capital, user_id))
                        
                        # Registra transazione
                        cur.execute("""
                            INSERT INTO portfolio_transactions 
                            (user_id, type, amount, balance_before, balance_after, description, reference_type, reference_id, status)
                            VALUES (%s, 'investment', %s, %s, %s, %s, 'project_cancel', %s, 'completed')
                        """, (user_id, invested_amount, portfolio['free_capital'], new_free_capital, 
                              f"Restituzione capitale investito - Annullamento {project['name']}", project_id))
                        
                        investors_processed += 1
                
                # 4. Aggiorna lo stato del progetto a 'cancelled'
                cur.execute("""
                    UPDATE projects 
                    SET status = 'cancelled', 
                        updated_at = NOW()
                    WHERE id = %s
                """, (project_id,))
                
                # 5. Marca tutti gli investimenti come cancellati
                cur.execute("""
                    UPDATE investments 
                    SET status = 'cancelled', 
                        completed_at = NOW()
                    WHERE project_id = %s AND status = 'active'
                """, (project_id,))
                
                # Commit della transazione
                conn.commit()
                conn.autocommit = True
                
                return jsonify({
                    'success': True,
                    'message': f'Progetto annullato con successo! Restituiti €{total_refunded} a {investors_processed} investitori.',
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
                    SELECT id, name, status
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
                
                # Elimina transazioni portfolio correlate
                cur.execute("""
                    DELETE FROM portfolio_transactions 
                    WHERE reference_type = 'project_sale' AND reference_id = %s
                """, (project_id,))
                
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
                    'message': f'Progetto "{project["name"]}" eliminato permanentemente dal sistema.',
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
