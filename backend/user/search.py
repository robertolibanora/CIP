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
    TABELLE: projects, users, investments (solo lettura)
    
    TASK 2.6 - Nuove funzionalità:
    - Filtro KYC: Mostra solo progetti per utenti verificati
    - Stato Investimenti: Indicatori se progetto già investito  
    - Placeholder Immagini: Gestione galleria foto progetti
    - Mobile Optimization: Ricerca ottimizzata per mobile
    """
    uid = session.get("user_id")
    query = request.args.get("q", "")
    
    with get_conn() as conn, conn.cursor() as cur:
        # 1. VERIFICA STATO KYC UTENTE
        cur.execute("""
            SELECT kyc_status FROM users WHERE id = %s
        """, (uid,))
        user = cur.fetchone()
        
        is_kyc_verified = user and user['kyc_status'] == 'verified'
        
        # 2. RICERCA PROGETTI CON INFORMAZIONI INVESTIMENTI
        if query:
            # Ricerca con query - TABELLA: projects + investments
            cur.execute("""
                SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                       p.status, p.created_at, p.code,
                       CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                       COALESCE(i.amount, 0) as user_investment_amount,
                       COALESCE(i.status, 'none') as user_investment_status
                FROM projects p 
                LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
                WHERE p.status = 'active' 
                AND (p.name ILIKE %s OR p.description ILIKE %s)
                ORDER BY p.created_at DESC
            """, (uid, f'%{query}%', f'%{query}%'))
        else:
            # Tutti i progetti attivi - TABELLA: projects + investments
            cur.execute("""
                SELECT p.id, p.name, p.description, p.total_amount, p.funded_amount,
                       p.status, p.created_at, p.code,
                       CASE WHEN i.id IS NOT NULL THEN true ELSE false END as user_invested,
                       COALESCE(i.amount, 0) as user_investment_amount,
                       COALESCE(i.status, 'none') as user_investment_status
                FROM projects p 
                LEFT JOIN investments i ON p.id = i.project_id AND i.user_id = %s AND i.status = 'active'
                WHERE p.status = 'active'
                ORDER BY p.created_at DESC
            """, (uid,))
        
        projects = cur.fetchall()
        
        # 3. ELABORAZIONE DATI PROGETTI
        for project in projects:
            # Calcola percentuale completamento
            if project['total_amount'] and project['total_amount'] > 0:
                project['completion_percent'] = min(100, int((project['funded_amount'] / project['total_amount']) * 100))
            else:
                project['completion_percent'] = 0
            
            # Aggiungi campi mancanti per compatibilità template
            project['location'] = 'N/A'  # Non presente nello schema attuale
            project['roi'] = 8.5  # ROI fisso per ora
            project['min_investment'] = 1000  # Investimento minimo fisso per ora
            
            # 4. PLACEHOLDER IMMAGINI - Struttura per galleria
            project['has_images'] = False  # Placeholder per ora
            project['image_url'] = None    # Sarà implementato con upload immagini
            project['gallery_count'] = 0   # Numero foto in galleria
    
    return render_template("user/search.html", 
                         user_id=uid,
                         projects=projects,
                         query=query,
                         is_kyc_verified=is_kyc_verified,
                         current_page="search")
