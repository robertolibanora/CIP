"""
CIP Immobiliare - Projects Module
Compartimento stagno per i progetti disponibili per investimento
"""

from flask import Blueprint, session, render_template, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Projects
projects_bp = Blueprint("projects", __name__)

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
                   p.sale_price, p.sale_date, p.profit_percentage,
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
                   p.sale_price, p.sale_date, p.profit_percentage,
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
                   p.sale_price, p.sale_date, p.profit_percentage,
                   CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                   COALESCE(i.amount, 0) as user_investment_amount,
                   COALESCE(i.status, 'none') as user_investment_status
            FROM projects p 
            LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
            WHERE p.status = 'sold'
            ORDER BY p.sale_date DESC
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
                project['location'] = project.get('location', 'N/A')
                project['roi'] = project.get('roi', 8.5)
                project['min_investment'] = project.get('min_investment', 1000)
                
                # PLACEHOLDER IMMAGINI - Struttura per galleria
                project['has_images'] = False
                project['image_url'] = None
                project['gallery_count'] = 0
                
                # Calcola informazioni profitto per progetti venduti
                if project['status'] == 'sold' and project['sale_price']:
                    project['profit_amount'] = project['sale_price'] - project['total_amount']
                    project['profit_percentage'] = project.get('profit_percentage', 0)
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
