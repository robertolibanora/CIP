"""
CIP Immobiliare - Portfolio Module
Compartimento stagno per il portafoglio investimenti utente
"""

from flask import Blueprint, session, render_template, jsonify, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Portfolio
portfolio_bp = Blueprint("portfolio", __name__)

def get_conn():
    return get_connection()

@portfolio_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route portfolio"""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@portfolio_bp.get("/portfolio")
def portfolio():
    """
    Portafoglio dettagliato con investimenti attivi e completati
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: investments, projects, investment_yields
    """
    uid = session.get("user_id")
    tab = request.args.get("tab", "attivi")
    statuses = ('active',) if tab == 'attivi' else ('completed','cancelled','rejected')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Investimenti per tab - TABELLE: investments + projects
        cur.execute("""
            SELECT i.id, p.name AS project_title, i.amount, i.status, i.created_at
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.user_id=%s AND i.status = ANY(%s)
            ORDER BY i.created_at DESC
        """, (uid, list(statuses)))
        rows = cur.fetchall()
        
        # Aggiungi campi mancanti per compatibilità template
        for row in rows:
            row['roi'] = 8.5  # ROI fisso per ora
        
        # Dati utente completi per il form profilo - TABELLA: users
        cur.execute("""
            SELECT id, full_name, email, nome, cognome, telefono, nome_telegram, 
                   address, currency_code, referral_code, created_at
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
    
    return render_template("user/portfolio.html", 
                         user_id=uid,
                         tab=tab,
                         investments=rows,
                         user=user_data,
                         current_page="portfolio")

@portfolio_bp.get("/portfolio/<int:investment_id>")
def portfolio_detail(investment_id):
    """
    Dettaglio specifico di un investimento
    ACCESSO: Solo tramite portfolio.html (non accessibile direttamente)
    TABELLE: investments, projects, investment_yields
    """
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Dettaglio investimento - TABELLE: investments + projects
        cur.execute("""
            SELECT i.*, p.name AS project_title
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.id=%s AND i.user_id=%s
        """, (investment_id, uid))
        inv = cur.fetchone()
        
        # Rendimenti investimento - TABELLA: investment_yields
        cur.execute("""
            SELECT * FROM investment_yields 
            WHERE investment_id=%s 
            ORDER BY period_end DESC
        """, (investment_id,))
        yields = cur.fetchall()
    
    return jsonify({"investment": inv, "yields": yields})
