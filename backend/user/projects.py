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
    Lista progetti disponibili per investimento
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: projects (solo lettura)
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Progetti disponibili - TABELLA: projects
        cur.execute("""
            SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                   p.status, p.created_at, p.code
            FROM projects p 
            WHERE p.status = 'active'
            ORDER BY p.created_at DESC
        """)
        projects = cur.fetchall()
        
        # Calcola percentuale completamento
        for project in projects:
            if project['total_amount'] and project['total_amount'] > 0:
                project['completion_percent'] = min(100, int((project['funded_amount'] / project['total_amount']) * 100))
            else:
                project['completion_percent'] = 0
            
            # Aggiungi campi mancanti per compatibilità template
            project['location'] = 'N/A'  # Non presente nello schema attuale
            project['roi'] = 8.5  # ROI fisso per ora
            project['min_investment'] = 1000  # Investimento minimo fisso per ora
    
    return render_template("user/projects.html", 
                         user_id=uid,
                         projects=projects,
                         current_page="projects")
