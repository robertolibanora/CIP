"""
CIP Immobiliare - Portfolio Module
Compartimento stagno per il portafoglio investimenti utente
"""

from flask import Blueprint, session, render_template, jsonify, request, redirect, url_for
from backend.shared.database import get_connection

# Blueprint isolato per Portfolio
portfolio_bp = Blueprint("portfolio", __name__)

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

@portfolio_bp.before_request
def require_login():
    """Verifica che l'utente sia autenticato per tutte le route portfolio"""
    # Skip login check for API endpoints
    if request.endpoint and 'api' in request.endpoint:
        return
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@portfolio_bp.get("/portfolio")
def portfolio():
    """
    Portafoglio dettagliato con investimenti attivi e completati
    ACCESSO: Solo tramite navbar mobile-nav.html
    TABELLE: investments, projects, investment_yields, user_portfolios
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
            row['roi'] = 8.5  # RA fisso per ora
        
        # Dati utente completi per il form profilo - TABELLA: users
        cur.execute("""
            SELECT id, nome, email, nome, cognome, telefono, telegram, 
                   address, currency_code, referral_code, created_at
            FROM users WHERE id = %s
        """, (uid,))
        user_data = cur.fetchone()
        
        # Dati portafoglio - TABELLA: user_portfolios
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio_data = cur.fetchone()
        
        # Se non esiste portfolio, creane uno
        if not portfolio_data:
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                VALUES (%s, 0, 0, 0, 0)
            """, (uid,))
            conn.commit()
            portfolio_data = {
                'free_capital': 0,
                'invested_capital': 0,
                'referral_bonus': 0,
                'profits': 0
            }
    
    return render_template("user/portfolio.html", 
                         user_id=uid,
                         tab=tab,
                         investments=rows,
                         user=user_data,
                         portfolio=portfolio_data,
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

# =====================================================
# API PER 4 SEZIONI PORTFOLIO
# =====================================================

@portfolio_bp.route('/api/portfolio/4-sections', methods=['GET'])
def get_portfolio_4_sections():
    """API per ottenere le 4 sezioni del portafoglio utente"""
    uid = session.get("user_id")
    
    if not uid:
        return jsonify({'error': 'Non autorizzato'}), 401
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni portafoglio utente con 4 sezioni
        cur.execute("""
            SELECT 
                free_capital,
                invested_capital,
                referral_bonus,
                profits,
                created_at,
                updated_at
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        
        portfolio = cur.fetchone()
        
        if not portfolio:
            # Crea portafoglio vuoto se non esiste
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                VALUES (%s, 0.00, 0.00, 0.00, 0.00)
                RETURNING free_capital, invested_capital, referral_bonus, profits, created_at, updated_at
            """, (uid,))
            portfolio = cur.fetchone()
            conn.commit()
        
        # Calcola totale
        total_balance = float(portfolio['free_capital']) + float(portfolio['invested_capital']) + float(portfolio['referral_bonus']) + float(portfolio['profits'])
        
        # Serializza datetime per JSON
        portfolio_data = dict(portfolio)
        if portfolio_data.get('created_at'):
            try:
                portfolio_data['created_at'] = portfolio_data['created_at'].isoformat()
            except Exception:
                portfolio_data['created_at'] = str(portfolio_data['created_at'])
        if portfolio_data.get('updated_at'):
            try:
                portfolio_data['updated_at'] = portfolio_data['updated_at'].isoformat()
            except Exception:
                portfolio_data['updated_at'] = str(portfolio_data['updated_at'])
        
        portfolio_data['total_balance'] = total_balance
        
        return jsonify({'portfolio': portfolio_data})
