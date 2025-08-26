"""
CIP Immobiliare - Search Module
Compartimento stagno per la ricerca progetti disponibili
"""

from flask import Blueprint, session, render_template, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Search
search_bp = Blueprint("search", __name__)

def get_conn():
    return get_connection()

@search_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route search"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@search_bp.get("/search")
def search():
    """
    Ricerca progetti disponibili per investimento
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: projects (solo lettura)
    """
    uid = session.get("user_id")
    query = request.args.get("q", "")
    
    with get_conn() as conn, conn.cursor() as cur:
        if query:
            # Ricerca con query - TABELLA: projects
            cur.execute("""
                SELECT p.id, p.title, p.description, p.target_amount, p.raised_amount,
                       p.status, p.created_at, p.code
                FROM projects p 
                WHERE p.status = 'active' 
                AND (p.title ILIKE %s OR p.description ILIKE %s)
                ORDER BY p.created_at DESC
            """, (f'%{query}%', f'%{query}%'))
        else:
            # Tutti i progetti attivi - TABELLA: projects
            cur.execute("""
                SELECT p.id, p.title, p.description, p.target_amount, p.raised_amount,
                       p.status, p.created_at, p.code
                FROM projects p 
                WHERE p.status = 'active'
                ORDER BY p.created_at DESC
            """)
        
        projects = cur.fetchall()
        
        # Calcola percentuale completamento
        for project in projects:
            if project['target_amount'] and project['target_amount'] > 0:
                project['completion_percent'] = min(100, int((project['raised_amount'] / project['target_amount']) * 100))
            else:
                project['completion_percent'] = 0
            
            # Aggiungi campi mancanti per compatibilità template
            project['location'] = 'N/A'  # Non presente nello schema attuale
            project['roi'] = 8.5  # ROI fisso per ora
            project['min_investment'] = 1000  # Investimento minimo fisso per ora
    
    return render_template("user/search.html", 
                         user_id=uid,
                         projects=projects,
                         query=query,
                         current_page="search")
