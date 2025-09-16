"""
CIP Immobiliare - New Project Module
Compartimento stagno per nuovi investimenti
"""

from flask import Blueprint, session, render_template, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per New Project
new_project_bp = Blueprint("new_project", __name__)

def get_conn():
    return get_connection()

@new_project_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route new_project"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@new_project_bp.get("/new-project")
def new_project():
    """
    Pagina per nuovo investimento
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: projects (solo lettura)
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Progetti disponibili - TABELLA: projects
        cur.execute("""
            SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                   p.status, p.created_at, p.code, p.end_date
            FROM projects p 
            WHERE p.status = 'active' AND p.end_date >= CURRENT_DATE
            ORDER BY p.created_at DESC
        """)
        available_projects = cur.fetchall()
        
        # Calcola percentuale completamento
        for project in available_projects:
            if project['total_amount'] and project['total_amount'] > 0:
                project['completion_percent'] = min(100, int((project['funded_amount'] / project['total_amount']) * 100))
            else:
                project['completion_percent'] = 0
            
            project['location'] = 'N/A'
            project['roi'] = 8.5
            project['min_investment'] = 1000
    
    return render_template("user/new_project.html", 
                         user_id=uid,
                         projects=available_projects,
                         current_page="new_project")
