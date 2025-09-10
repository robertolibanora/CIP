"""
CIP Immobiliare - Projects Module
Compartimento stagno per i progetti disponibili per investimento
"""

from flask import Blueprint, session, render_template, request, redirect, url_for, jsonify, flash
from backend.shared.database import get_connection
from backend.auth.decorators import can_invest

# Blueprint isolato per Projects
projects_bp = Blueprint("user_projects", __name__)

def get_conn():
    return get_connection()

@projects_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route projects"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@projects_bp.get("/projects")
def projects():
    """
    Lista progetti divisi in 3 sezioni: Attivi, Completati, Venduti
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: projects, investments (solo lettura)
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # 1. VERIFICA STATO KYC UTENTE
        cur.execute("""
            SELECT kyc_status FROM users WHERE id = %s
        """, (uid,))
        user = cur.fetchone()
        
        is_kyc_verified = user and user['kyc_status'] == 'verified'
        
        # 2. PROGETTI ATTIVI (dove si può investire)
        cur.execute("""
            SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                   p.status, p.created_at, p.code, p.location, p.roi, p.min_investment,
                   p.image_url,
                   CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                   COALESCE(i.amount, 0) as user_investment_amount,
                   COALESCE(i.status, 'none') as user_investment_status
            FROM projects p 
            LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
            WHERE p.status = 'active'
            ORDER BY p.created_at DESC
        """, (uid,))
        
        active_projects = cur.fetchall()
        
        # 3. PROGETTI COMPLETATI (non si può più investire, in attesa vendita)
        cur.execute("""
            SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                   p.status, p.created_at, p.code, p.location, p.roi, p.min_investment,
                   p.image_url,
                   CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                   COALESCE(i.amount, 0) as user_investment_amount,
                   COALESCE(i.status, 'none') as user_investment_status
            FROM projects p 
            LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
            WHERE p.status = 'completed'
            ORDER BY p.created_at DESC
        """, (uid,))
        
        completed_projects = cur.fetchall()
        
        # 4. PROGETTI VENDUTI (con informazioni sui profitti)
        cur.execute("""
            SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                   p.status, p.created_at, p.code, p.location, p.roi, p.min_investment,
                   p.image_url, ps.sale_amount as sale_price, ps.sale_date,
                   CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                   COALESCE(i.amount, 0) as user_investment_amount,
                   COALESCE(i.status, 'none') as user_investment_status
            FROM projects p 
            LEFT JOIN project_sales ps ON p.id = ps.project_id
            LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
            WHERE p.status = 'sold'
            ORDER BY ps.sale_date DESC
        """, (uid,))
        
        sold_projects = cur.fetchall()
        
        # 5. ELABORAZIONE DATI PROGETTI
        def process_projects(projects_list):
            for project in projects_list:
                # Calcola percentuale completamento
                if project['total_amount'] and project['total_amount'] > 0:
                    project['completion_percent'] = min(100, int((project['funded_amount'] / project['total_amount']) * 100))
                else:
                    project['completion_percent'] = 0
                
                # Aggiungi campi mancanti per compatibilità template
                project['location'] = project.get('location') or 'N/A'
                project['roi'] = project.get('roi') or 8.5
                project['min_investment'] = project.get('min_investment') or 1000
                project['description'] = project.get('description') or 'Nessuna descrizione disponibile'
                
                # GESTIONE IMMAGINI - Struttura per galleria
                project['has_images'] = bool(project.get('image_url'))
                project['photo_filename'] = project.get('image_url')  # Per compatibilità con template
                project['gallery_count'] = 1 if project.get('image_url') else 0
                
                # Calcola informazioni profitto per progetti venduti
                if project['status'] == 'sold' and project.get('sale_price'):
                    project['profit_amount'] = project['sale_price'] - project['total_amount']
                    if project['total_amount'] > 0:
                        project['profit_percentage'] = (project['profit_amount'] / project['total_amount']) * 100
                    else:
                        project['profit_percentage'] = 0
                else:
                    project['profit_amount'] = 0
                    project['profit_percentage'] = 0
            
            return projects_list
        
        # Processa tutte le liste
        active_projects = process_projects(active_projects)
        completed_projects = process_projects(completed_projects)
        sold_projects = process_projects(sold_projects)
    
    return render_template("user/projects.html", 
                         user_id=uid,
                         active_projects=active_projects,
                         completed_projects=completed_projects,
                         sold_projects=sold_projects,
                         is_kyc_verified=is_kyc_verified,
                         current_page="projects")

@projects_bp.post("/projects/invest")
@can_invest
def invest_in_project():
    """
    Gestisce l'investimento in un progetto
    """
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Utente non autenticato"}), 401
    
    try:
        data = request.get_json()
        project_id = data.get('project_id')
        amount = float(data.get('amount', 0))
        fund_source = data.get('fund_source')  # 'free_capital', 'profits', 'referral_bonus'
        
        if not project_id or not amount or not fund_source:
            return jsonify({"error": "Dati mancanti"}), 400
        
        if amount < 100:
            return jsonify({"error": "Importo minimo €100"}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # 1. Verifica che il progetto esista e sia attivo
            cur.execute("""
                SELECT id, name, total_amount, funded_amount, min_investment
                FROM projects 
                WHERE id = %s AND status = 'active'
            """, (project_id,))
            project = cur.fetchone()
            
            if not project:
                return jsonify({"error": "Progetto non trovato o non attivo"}), 404
            
            # 2. Verifica che l'importo sia sufficiente
            if amount < project['min_investment']:
                return jsonify({"error": f"Importo minimo €{project['min_investment']}"}), 400
            
            # 3. Verifica che il progetto non sia già completamente finanziato
            if project['funded_amount'] >= project['total_amount']:
                return jsonify({"error": "Progetto già completamente finanziato"}), 400
            
            # 4. Verifica che l'utente abbia fondi sufficienti
            cur.execute("""
                SELECT free_capital, profits, referral_bonus
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                return jsonify({"error": "Portfolio utente non trovato"}), 404
            
            # Controlla fondi disponibili in base alla fonte
            available_funds = 0
            if fund_source == 'free_capital':
                available_funds = portfolio['free_capital']
            elif fund_source == 'profits':
                available_funds = portfolio['profits']
            elif fund_source == 'referral_bonus':
                available_funds = portfolio['referral_bonus']
            else:
                return jsonify({"error": "Fonte fondi non valida"}), 400
            
            if available_funds < amount:
                return jsonify({"error": f"Fondi insufficienti. Disponibili: €{available_funds:.2f}"}), 400
            
            # 5. Verifica che l'investimento non superi il limite del progetto
            remaining_capacity = project['total_amount'] - project['funded_amount']
            if amount > remaining_capacity:
                return jsonify({"error": f"Importo troppo alto. Capacità rimanente: €{remaining_capacity:.2f}"}), 400
            
            # 6. Esegui l'investimento
            # 6a. Crea il record di investimento
            cur.execute("""
                INSERT INTO investments (user_id, project_id, amount, status, activated_at)
                VALUES (%s, %s, %s, 'active', CURRENT_TIMESTAMP)
                RETURNING id
            """, (uid, project_id, amount))
            
            investment_id = cur.fetchone()['id']
            
            # 6b. Aggiorna il portfolio dell'utente
            if fund_source == 'free_capital':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = free_capital - %s,
                        invested_capital = invested_capital + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (amount, amount, uid))
            elif fund_source == 'profits':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET profits = profits - %s,
                        invested_capital = invested_capital + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (amount, amount, uid))
            elif fund_source == 'referral_bonus':
                cur.execute("""
                    UPDATE user_portfolios 
                    SET referral_bonus = referral_bonus - %s,
                        invested_capital = invested_capital + %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                """, (amount, amount, uid))
            
            # 6c. Aggiorna il progetto
            cur.execute("""
                UPDATE projects 
                SET funded_amount = funded_amount + %s
                WHERE id = %s
            """, (amount, project_id))
            
            # 6d. Ottieni le informazioni aggiornate del progetto per la barra di progresso
            cur.execute("""
                SELECT total_amount, funded_amount, status
                FROM projects 
                WHERE id = %s
            """, (project_id,))
            updated_project = cur.fetchone()
            
            # Calcola la percentuale di completamento aggiornata
            if updated_project['total_amount'] and updated_project['total_amount'] > 0:
                completion_percent = min(100, int((updated_project['funded_amount'] / updated_project['total_amount']) * 100))
            else:
                completion_percent = 0
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": f"Investimento di €{amount:.2f} effettuato con successo!",
                "investment_id": investment_id,
                "fund_source": fund_source,
                "project_update": {
                    "funded_amount": float(updated_project['funded_amount']),
                    "completion_percent": completion_percent,
                    "remaining_amount": float(updated_project['total_amount'] - updated_project['funded_amount']),
                    "is_funded": updated_project['funded_amount'] >= updated_project['total_amount']
                }
            })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Errore durante investimento: {str(e)}")
        print(f"Traceback: {error_details}")
        return jsonify({"error": f"Errore durante l'investimento: {str(e)}"}), 500

@projects_bp.get("/projects/<int:project_id>/funds")
def get_user_funds(project_id):
    """
    Restituisce i fondi disponibili dell'utente per l'investimento
    """
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "Utente non autenticato"}), 401
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni i fondi dell'utente
            cur.execute("""
                SELECT free_capital, profits, referral_bonus, invested_capital
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                return jsonify({"error": "Portfolio utente non trovato"}), 404
            
            # Ottieni i dettagli del progetto
            cur.execute("""
                SELECT id, name, total_amount, funded_amount, min_investment
                FROM projects 
                WHERE id = %s AND status = 'active'
            """, (project_id,))
            project = cur.fetchone()
            
            if not project:
                return jsonify({"error": "Progetto non trovato o non attivo"}), 404
            
            remaining_capacity = project['total_amount'] - project['funded_amount']
            
            return jsonify({
                "funds": {
                    "free_capital": float(portfolio['free_capital']),
                    "profits": float(portfolio['profits']),
                    "referral_bonus": float(portfolio['referral_bonus']),
                    "invested_capital": float(portfolio['invested_capital'])
                },
                "project": {
                    "id": project['id'],
                    "name": project['name'],
                    "min_investment": float(project['min_investment']),
                    "remaining_capacity": float(remaining_capacity)
                }
            })
            
    except Exception as e:
        return jsonify({"error": f"Errore nel recupero fondi: {str(e)}"}), 500
