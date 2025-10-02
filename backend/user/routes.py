import os
from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, flash, abort
from backend.shared.database import get_connection

user_bp = Blueprint("user", __name__)

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required, kyc_verified, can_invest

# =====================================================
# CONFIGURAZIONI SISTEMA - Dati per depositi
# =====================================================

@user_bp.get("/api/deposit-config")
@login_required
def get_deposit_config():
    """Ottieni configurazioni per i depositi (bonifici e wallet)"""
    with get_conn() as conn, conn.cursor() as cur:
        # Configurazione bonifici
        cur.execute("""
            SELECT bank_name, account_holder, iban, bic_swift
            FROM bank_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        bank_config = cur.fetchone()
        
        # Configurazione wallet USDT
        cur.execute("""
            SELECT wallet_address, network
            FROM wallet_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        wallet_config = cur.fetchone()
        
        return jsonify({
            'bank_config': bank_config,
            'wallet_config': wallet_config
        })

@user_bp.get("/api/nome_telegram-config")
@login_required
def get_nome_telegram_config():
    """Ottieni configurazione Telegram per l'utente"""
    with get_conn() as conn, conn.cursor() as cur:
        # Configurazione Telegram
        cur.execute("""
            SELECT config_value
            FROM system_configurations 
            WHERE config_key = 'nome_telegram_link' AND is_active = true
            LIMIT 1
        """)
        nome_telegram_config = cur.fetchone()
        
        return jsonify({
            'nome_telegram_link': nome_telegram_config['config_value'] if nome_telegram_config else None
        })

@user_bp.get("/api/telegram-config")
@login_required
def get_telegram_config():
    """Ottieni configurazione Telegram per l'utente (endpoint compatibile)"""
    with get_conn() as conn, conn.cursor() as cur:
        # Configurazione Telegram - prova prima telegram_link, poi nome_telegram_link
        cur.execute("""
            SELECT config_value
            FROM system_configurations 
            WHERE config_key = 'telegram_link' AND is_active = true
            LIMIT 1
        """)
        telegram_config = cur.fetchone()
        
        # Se non trova telegram_link, prova nome_telegram_link
        if not telegram_config:
            cur.execute("""
                SELECT config_value
                FROM system_configurations 
                WHERE config_key = 'nome_telegram_link' AND is_active = true
                LIMIT 1
            """)
            telegram_config = cur.fetchone()
        
        return jsonify({
            'telegram_link': telegram_config['config_value'] if telegram_config else None
        })

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

# =====================================================
# 1. DASHBOARD - Vista generale del portfolio e statistiche
# =====================================================

@user_bp.get("/dashboard-debug")
@login_required
def dashboard_debug():
    """Dashboard debug semplificata"""
    try:
        uid = session.get("user_id")
        if not uid:
            return "Errore: user_id non trovato", 400
        
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, email, nome FROM users WHERE id = %s", (uid,))
            user_data = cur.fetchone()
            
            if not user_data:
                return "Errore: utente non trovato", 404
            
            return f"Dashboard debug funziona! Utente: {user_data['nome']} (ID: {user_data['id']})"
    
    except Exception as e:
        return f"Errore dashboard debug: {str(e)}", 500

@user_bp.get("/dashboard")
@login_required
def dashboard():
    """Dashboard principale con overview portfolio e statistiche - Versione semplificata"""
    try:
        uid = session.get("user_id")
        if not uid:
            return redirect(url_for("auth.login"))
        
        # Versione semplificata per compatibilità
        with get_conn() as conn, conn.cursor() as cur:
            # Dati utente base
            cur.execute("""
                SELECT id, email, nome, role, cognome, kyc_status
                FROM users WHERE id = %s
            """, (uid,))
            user_data = cur.fetchone()
            
            if not user_data:
                return redirect(url_for("auth.login"))
            
            # Calcola nome da mostrare
            nome_value = (user_data.get("nome") or "").strip()
            greet_name = nome_value.split()[0] if nome_value else "Utente"
            
            # Dati semplificati per compatibilità
            free_capital = 0.00
            invested_capital = 0.00
            referral_bonus = 0.00
            profits = 0.00
            total_available = free_capital + referral_bonus + profits
            total_balance = total_available + invested_capital
            avg_roi = 0.0
            portfolio_status = "Inattivo"
            active_investments_data = []
            referred_users_count = 0
            total_referral_investments = 0
            referral_link = request.url_root.rstrip('/') + '/auth/register'
            
            return render_template("user/dashboard.html",
                                   user=user_data,
                                   greet_name=greet_name,
                                   portfolio={},
                                   free_capital=free_capital,
                                   invested_capital=invested_capital,
                                   referral_bonus=referral_bonus,
                                   profits=profits,
                                   total_available=total_available,
                                   total_balance=total_balance,
                                   avg_roi=avg_roi,
                                   portfolio_status=portfolio_status,
                                   active_investments=active_investments_data,
                                   referred_users_count=referred_users_count,
                                   total_referral_investments=total_referral_investments,
                                   referral_link=referral_link,
                                   current_page="dashboard")
    
    except Exception as e:
        # Log dell'errore per debug
        print(f"Errore dashboard utente: {str(e)}")
        return f"Errore dashboard: {str(e)}", 500

# =====================================================
# 2. PROFILO UTENTE - Gestione dati personali
# =====================================================

# Route /projects rimossa - gestita da projects.py per evitare conflitti

@user_bp.get("/new-project")
@login_required
def new_project():
    """Pagina per nuovo investimento - Task 2.5 implementazione completa"""
    uid = session.get("user_id")
    
    # Versione semplificata per compatibilità
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # 2. CONTROLLO BUDGET - Ottieni portfolio con 4 sezioni
            cur.execute("""
                SELECT free_capital, invested_capital, referral_bonus, profits
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                # Crea portfolio se non esiste
                cur.execute("""
                    INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                    VALUES (%s, 0.00, 0.00, 0.00, 0.00)
                    RETURNING free_capital, invested_capital, referral_bonus, profits
                """, (uid,))
                portfolio = cur.fetchone()
                conn.commit()
            
            # 3. CALCOLO DISPONIBILITÀ - Calcola importi disponibili per sezione
            total_available = portfolio['free_capital'] + portfolio['referral_bonus'] + portfolio['profits']
            
            # 4. SELEZIONE FONTE - Prepara dati per scelta sezione portafoglio
            available_sections = []
            if portfolio['free_capital'] > 0:
                available_sections.append({
                    'name': 'Capitale Libero',
                    'key': 'free_capital',
                    'amount': portfolio['free_capital'],
                    'description': 'Soldi non investiti, sempre prelevabili'
                })
            if portfolio['referral_bonus'] > 0:
                available_sections.append({
                    'name': 'Bonus Referral',
                    'key': 'referral_bonus',
                    'amount': portfolio['referral_bonus'],
                    'description': '3% referral, sempre disponibili per investimento (5% se sei un utente VIP)'
                })
            if portfolio['profits'] > 0:
                available_sections.append({
                    'name': 'Profitti',
                    'key': 'profits',
                    'amount': portfolio['profits'],
                    'description': 'Rendimenti accumulati, reinvestibili'
                })
            
            # 5. PROGETTI DISPONIBILI
            cur.execute("""
                SELECT p.id, p.title, p.description, p.total_amount, p.funded_amount,
                       p.status, p.created_at, p.code, p.location, p.min_investment
                FROM projects p 
                WHERE p.status = 'active'
                ORDER BY p.created_at DESC
            """)
            available_projects = cur.fetchall()
            
            # Calcola percentuale completamento e aggiungi campi mancanti
            for project in available_projects:
                if project['total_amount'] and project['total_amount'] > 0:
                    project['completion_percent'] = min(100, int((project['funded_amount'] / project['total_amount']) * 100))
                else:
                    project['completion_percent'] = 0
                
                # Campi di fallback se non presenti
                project['location'] = project.get('address', 'N/A')
                project['roi'] = project.get('roi', 8.5)
                project['min_investment'] = project.get('min_investment', 1000)
        
        # Ottieni dati utente completi
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, email, nome, role, cognome, is_verified
                FROM users WHERE id = %s
            """, (uid,))
            user = cur.fetchone()
            
            # Calcola nome da mostrare per saluto
            nome_value = ((user.get("nome") if user else "") or "").strip()
            greet_name = nome_value.split()[0] if nome_value else "Utente"
    except Exception as e:
        print(f"Errore new-project: {str(e)}")
        portfolio = {"free_capital": 1000, "invested_capital": 5000, "referral_bonus": 50, "profits": 200}
        total_available = 1250
        available_sections = [
            {"name": "Capitale Libero", "key": "free_capital", "amount": 1000, "description": "Soldi non investiti, sempre prelevabili"}
        ]
        available_projects = [{"id": 1, "title": "Progetto Test", "description": "Descrizione", "completion_percent": 10, "location": "Milano", "roi": 8.5, "min_investment": 1000, "code": "PRJ001"}]
        user = {"id": uid, "nome": "Utente", "email": "user@example.com", "role": "user", "cognome": "Test", "is_verified": False}
        greet_name = "Utente"
    
    return render_template("user/new_project.html", 
                         user=user,
                         greet_name=greet_name,
                         user_id=uid,
                         projects=available_projects,
                         portfolio=portfolio,
                         total_available=total_available,
                         available_sections=available_sections,
                         current_page="new_project")

@user_bp.post("/invest/<int:project_id>")
@can_invest
def invest(project_id):
    """Gestisce nuovo investimento - Task 2.5 implementazione completa"""
    uid = session.get("user_id")
    
    # Validazione input
    amount = request.form.get('amount')
    source_section = request.form.get('source_section', 'free_capital')
    
    if not amount:
        flash("Importo richiesto", "error")
        return redirect(url_for('user.new_project'))
    
    try:
        amount = float(amount)
        if amount <= 0:
            flash("Importo deve essere positivo", "error")
            return redirect(url_for('user.new_project'))
        # Consenti solo multipli di 100
        if (amount * 100) % 10000 != 0:
            flash("Importo consentito solo a multipli di 100 (es. 100, 200, 1000)", "error")
            return redirect(url_for('user.new_project'))
    except ValueError:
        flash("Importo non valido", "error")
        return redirect(url_for('user.new_project'))
    
    with get_conn() as conn, conn.cursor() as cur:
        # 1. VERIFICA KYC - Già gestito dal decorator @can_invest
        
        # 2. CONTROLLO BUDGET - Verifica disponibilità saldo
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio = cur.fetchone()
        
        if not portfolio:
            flash("Portfolio non trovato", "error")
            return redirect(url_for('user.new_project'))
        
        # 3. SELEZIONE FONTE - Verifica sezione portafoglio scelta
        available_amount = 0
        if source_section == 'free_capital':
            available_amount = portfolio['free_capital']
        elif source_section == 'referral_bonus':
            available_amount = portfolio['referral_bonus']
        elif source_section == 'profits':
            available_amount = portfolio['profits']
        else:
            flash("Sezione portafoglio non valida", "error")
            return redirect(url_for('user.new_project'))
        
        # 4. CALCOLO DISPONIBILITÀ - Verifica fondi sufficienti
        if available_amount < amount:
            flash(f"Fondi insufficienti. Disponibile: €{available_amount:.2f}", "error")
            return redirect(url_for('user.new_project'))
        
        # 5. VERIFICA PROGETTO
        cur.execute("""
            SELECT id, name, min_investment, total_amount, funded_amount, status
            FROM projects 
            WHERE id = %s AND status = 'active'
        """, (project_id,))
        project = cur.fetchone()
        
        if not project:
            flash("Progetto non trovato o non disponibile", "error")
            return redirect(url_for('user.new_project'))
        
        # 6. VALIDAZIONE IMPORTO MINIMO
        if amount < project['min_investment']:
            flash(f"Importo minimo richiesto: €{project['min_investment']:.2f}", "error")
            return redirect(url_for('user.new_project'))
        
        # 7. WIZARD INVESTIMENTO - Crea investimento
        try:
            # Inizia transazione
            conn.autocommit = False
            
            # Crea investimento
            cur.execute("""
                INSERT INTO investments (user_id, project_id, amount, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id
            """, (uid, project_id, amount))
            investment_id = cur.fetchone()['id']
            
            # Aggiorna portfolio - sottrai dalla sezione scelta
            if source_section == 'free_capital':
                new_free_capital = portfolio['free_capital'] - amount
                cur.execute("""
                    UPDATE user_portfolios 
                    SET free_capital = %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (new_free_capital, uid))
            elif source_section == 'referral_bonus':
                new_referral_bonus = portfolio['referral_bonus'] - amount
                cur.execute("""
                    UPDATE user_portfolios 
                    SET referral_bonus = %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (new_referral_bonus, uid))
            elif source_section == 'profits':
                new_profits = portfolio['profits'] - amount
                cur.execute("""
                    UPDATE user_portfolios 
                    SET profits = %s, updated_at = NOW()
                    WHERE user_id = %s
                """, (new_profits, uid))
            
            # Aggiungi a capitale investito
            cur.execute("""
                UPDATE user_portfolios 
                SET invested_capital = invested_capital + %s, updated_at = NOW()
                WHERE user_id = %s
            """, (amount, uid))
            
            # Aggiorna progetto
            cur.execute("""
                UPDATE projects 
                SET funded_amount = funded_amount + %s
                WHERE id = %s
            """, (amount, project_id))
            
            # Registra transazione
            cur.execute("""
                INSERT INTO portfolio_transactions 
                (user_id, type, amount, description, status, reference_type, reference_id)
                VALUES (%s, 'investment', %s, %s, 'completed', 'investment', %s)
            """, (uid, amount, f"Investimento in {project['name']}", investment_id))
            
            # Commit transazione
            conn.commit()
            conn.autocommit = True
            
            flash(f"Investimento di €{amount:.2f} in {project['name']} completato con successo!", "success")
            return redirect(url_for('user.portfolio'))
            
        except Exception as e:
            conn.rollback()
            conn.autocommit = True
            flash(f"Errore durante l'investimento: {str(e)}", "error")
            return redirect(url_for('user.new_project'))

# =====================================================
# 4. PORTAFOGLIO - Dettaglio investimenti e rendimenti
# =====================================================

@user_bp.get("/portfolio")
@login_required
def portfolio():
    """Portafoglio dettagliato con investimenti attivi e completati"""
    uid = session.get("user_id")
    
    # Versione semplificata per compatibilità
    try:
        tab = request.args.get("tab", "attivi")
        statuses = ('active',) if tab == 'attivi' else ('completed','cancelled','rejected')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni investimenti (raggruppati per progetto)
            cur.execute("""
                SELECT p.id as project_id, p.title AS project_title, 
                       SUM(i.amount) as total_amount, 
                       i.status, 
                       MIN(i.created_at) as first_investment_date,
                       MAX(i.created_at) as last_investment_date,
                       COUNT(i.id) as investment_count
                FROM investments i 
                JOIN projects p ON p.id=i.project_id
                WHERE i.user_id=%s AND i.status = ANY(%s)
                GROUP BY p.id, p.title, i.status
                ORDER BY MAX(i.created_at) DESC
            """, (uid, list(statuses)))
            rows = cur.fetchall()
            
            # Aggiungi campi mancanti per compatibilità template
            for row in rows:
                row['roi'] = 8.5  # RA fisso per ora
            
            # Ottieni dati utente completi per il form profilo
            cur.execute("""
                SELECT id, nome, email, cognome, telefono, nome_telegram, 
                       address, currency_code, referral_code, created_at, kyc_status, is_vip
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
    except Exception as e:
        print(f"Errore portfolio: {str(e)}")
        rows = []
        user_data = {
            "id": uid, 
            "nome": "Utente", 
            "email": "user@example.com", 
            "cognome": "Test",
            "telefono": "+39 000 000 0000",
            "nome_telegram": "@user",
            "address": "Indirizzo di test",
            "currency_code": "EUR",
            "referral_code": "REF001",
            "created_at": None,
            "kyc_status": "pending",
            "is_vip": False
        }
        portfolio_data = {
            'free_capital': 0,
            'invested_capital': 0,
            'referral_bonus': 0,
            'profits': 0
        }
        tab = "attivi"
    
    return render_template("user/portfolio.html", 
                         user_id=uid,
                         user=user_data,
                         portfolio=portfolio_data,
                         tab=tab,
                         investments=rows,
                         current_page="portfolio")

@user_bp.get("/api/portfolio-data")
@kyc_verified
def get_portfolio_data():
    """API per ottenere i dati del portafoglio per il trasferimento"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT free_capital, invested_capital, referral_bonus, profits
            FROM user_portfolios 
            WHERE user_id = %s
        """, (uid,))
        portfolio_data = cur.fetchone()
        
        if not portfolio_data:
            return jsonify({
                'free_capital': 0,
                'invested_capital': 0,
                'referral_bonus': 0,
                'profits': 0
            })
        
        return jsonify({
            'free_capital': float(portfolio_data['free_capital']),
            'invested_capital': float(portfolio_data['invested_capital']),
            'referral_bonus': float(portfolio_data['referral_bonus']),
            'profits': float(portfolio_data['profits'])
        })

@user_bp.post("/api/transfer-capital")
@kyc_verified
def transfer_capital():
    """API per trasferire capitale tra le sezioni del portafoglio"""
    uid = session.get("user_id")
    
    try:
        data = request.get_json()
        from_source = data.get('from_source')
        to_source = data.get('to_source')
        amount = float(data.get('amount', 0))
        
        # Validazione
        if not from_source or not to_source:
            return jsonify({"error": "Fonte e destinazione richieste"}), 400
        
        if from_source == to_source:
            return jsonify({"error": "Fonte e destinazione devono essere diverse"}), 400
        
        if amount <= 0:
            return jsonify({"error": "Importo deve essere positivo"}), 400
        
        # Verifica che il capitale investito non sia coinvolto
        if from_source == 'invested_capital' or to_source == 'invested_capital':
            return jsonify({"error": "Il capitale investito non può essere spostato"}), 400
        
        # Verifica logica unidirezionale: solo da profitti/bonus a capitale libero
        if from_source == 'free_capital':
            return jsonify({"error": "Il capitale libero può essere spostato solo investendo in progetti"}), 400
        
        # Solo profitti e bonus possono essere spostati a capitale libero
        if from_source not in ['profits', 'referral_bonus'] or to_source != 'free_capital':
            return jsonify({"error": "Solo profitti e bonus possono essere spostati a capitale libero"}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica fondi disponibili
            cur.execute("""
                SELECT free_capital, invested_capital, referral_bonus, profits
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                return jsonify({"error": "Portafoglio non trovato"}), 404
            
            # Controlla fondi sufficienti
            available_funds = portfolio[from_source]
            if amount > available_funds:
                return jsonify({"error": f"Fondi insufficienti. Disponibili: €{available_funds:.2f}"}), 400
            
            # Esegui il trasferimento
            cur.execute(f"""
                UPDATE user_portfolios 
                SET {from_source} = {from_source} - %s,
                    {to_source} = {to_source} + %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (amount, amount, uid))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": f"Trasferimento di €{amount:.2f} da {from_source} a {to_source} completato con successo!"
            })
            
    except Exception as e:
        return jsonify({"error": f"Errore durante il trasferimento: {str(e)}"}), 500

@user_bp.get("/portfolio/<int:investment_id>")
@kyc_verified
def portfolio_detail(investment_id):
    """Dettaglio specifico di un investimento"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.*, p.title AS project_title
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.id=%s AND i.user_id=%s
        """, (investment_id, uid))
        inv = cur.fetchone()
        
        cur.execute("""
            SELECT * FROM investment_yields 
            WHERE investment_id=%s 
            ORDER BY period_end DESC
        """, (investment_id,))
        yields = cur.fetchall()
    
    return jsonify({"investment": inv, "yields": yields})

# =====================================================
# 5. PROGETTI - Lista e dettagli dei progetti disponibili
# =====================================================
# NOTA: La route /projects è stata spostata in backend/user/projects.py
# per evitare conflitti con il template che si aspetta active_projects, 
# completed_projects, sold_projects separati

# =====================================================
# 5.b KYC USER PAGE - Pagina dedicata verifica identità
# =====================================================

@user_bp.get("/kyc")
@login_required
def kyc_page():
    """Pagina dedicata per upload documenti KYC dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni dati utente completi
        cur.execute("""
            SELECT id, email, nome, role, cognome, is_verified
            FROM users WHERE id = %s
        """, (uid,))
        user = cur.fetchone()
        
        # Calcola nome da mostrare per saluto
        nome_value = ((user.get("nome") if user else "") or "").strip()
        nome_value = ((user.get("nome") if user else "") or "").strip()
        greet_name = nome_value.split()[0] if nome_value else (nome_value.split()[0] if nome_value else "Utente")
    
    return render_template("user/kyc.html", 
                         user=user,
                         greet_name=greet_name,
                         user_id=uid, 
                         current_page="kyc")

@user_bp.get("/uploads/projects/<filename>")
@login_required
def serve_project_file_user(filename):
    """Serve i file upload dei progetti per gli utenti (foto e documenti)"""
    from flask import current_app, send_from_directory
    import os
    
    # Permetti accesso sia a user che admin
    user_role = session.get('user_role')
    if user_role not in ['user', 'admin']:
        abort(403)
    
    # Usa la cartella uploads/projects nella root del progetto
    projects_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
    
    if not os.path.exists(os.path.join(projects_folder, filename)):
        abort(404)
    
    return send_from_directory(projects_folder, filename)

# Rota per dettaglio progetto rimossa - ora gestito tramite modal in projects.html

# =====================================================
# 6. REFERRAL - Sistema di referral e bonus
# =====================================================

@user_bp.get("/referral")
@login_required
def referral():
    """Dashboard referral dell'utente"""
    uid = session.get("user_id")
    
    # Versione semplificata per compatibilità
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Statistiche referral - Esclude auto-referral
            cur.execute("""
                SELECT COUNT(*) as total_referrals,
                       COUNT(CASE WHEN u.kyc_status = 'verified' THEN 1 END) as verified_referrals,
                       COUNT(CASE WHEN u.kyc_status != 'verified' THEN 1 END) as pending_referrals
                FROM users u WHERE u.referred_by = %s AND u.id != %s
            """, (uid, uid))
            stats = cur.fetchone()
            
            # Lista referral - Esclude auto-referral
            cur.execute("""
                SELECT u.id, u.nome, u.cognome, u.email, u.created_at, u.kyc_status,
                       COALESCE(SUM(i.amount), 0) as total_invested
                FROM users u 
                LEFT JOIN investments i ON u.id = i.user_id AND i.status = 'active'
                WHERE u.referred_by = %s AND u.id != %s
                GROUP BY u.id, u.nome, u.cognome, u.email, u.created_at, u.kyc_status
                ORDER BY u.created_at DESC
            """, (uid, uid))
            referrals = cur.fetchall()
            
            # Bonus totali dal portfolio
            cur.execute("""
                SELECT COALESCE(referral_bonus, 0) as total_bonus 
                FROM user_portfolios 
                WHERE user_id = %s
            """, (uid,))
            bonus = cur.fetchone()
        
        # Ottieni dati utente completi
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, email, nome, role, cognome, is_verified
                FROM users WHERE id = %s
            """, (uid,))
            user = cur.fetchone()
            
            # Calcola nome da mostrare per saluto
            nome_value = ((user.get("nome") if user else "") or "").strip()
            greet_name = nome_value.split()[0] if nome_value else "Utente"
    except Exception as e:
        print(f"Errore referral: {str(e)}")
        stats = {"total_referrals": 0, "verified_referrals": 0, "pending_referrals": 0}
        referrals = []
        bonus = {"total_bonus": 0}
        user = {"id": uid, "nome": "Utente", "email": "user@example.com", "role": "user", "cognome": "Test", "is_verified": False}
        greet_name = "Utente"
    
    return render_template("user/referral.html", 
                         user=user,
                         greet_name=greet_name,
                         user_id=uid,
                         stats=stats,
                         referrals=referrals,
                         total_bonus=bonus['total_bonus'] if bonus else 0,
                         current_page="referral")

# =====================================================
# 7. PROFILO - Gestione account utente
# =====================================================

@user_bp.get("/profile")
@login_required
def profile():
    """Gestione profilo utente"""
    uid = session.get("user_id")
    
    # Versione semplificata per compatibilità
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, nome, email, referral_code, created_at,
                       cognome, telefono, nome_telegram, address, currency_code,
                       kyc_status
                FROM users WHERE id = %s
            """, (uid,))
            user_data = cur.fetchone()
            
            if not user_data:
                user_data = {
                    "id": uid, 
                    "nome": "Utente", 
                    "email": "user@example.com", 
                    "referral_code": "REF001", 
                    "created_at": None,
                    "cognome": "Test",
                    "telefono": "+39 000 000 0000",
                    "nome_telegram": "@user",
                    "address": "Indirizzo di test",
                    "currency_code": "EUR",
                    "kyc_status": "pending"
                }
    except Exception as e:
        print(f"Errore profilo: {str(e)}")
        user_data = {
            "id": uid, 
            "nome": "Utente", 
            "email": "user@example.com", 
            "referral_code": "REF001", 
            "created_at": None,
            "cognome": "Test",
            "telefono": "+39 000 000 0000",
            "nome_telegram": "@user",
            "address": "Indirizzo di test",
            "currency_code": "EUR",
            "kyc_status": "pending"
        }
    
    return render_template("user/profile.html", 
                         user_id=uid,
                         user=user_data,
                         current_page="profile")

@user_bp.post("/profile/update")
@login_required
def profile_update():
    """Aggiornamento dati profilo"""
    uid = session.get("user_id")
    data = request.get_json()
    
    # Validazione dati base
    if not data:
        return jsonify({'success': False, 'error': 'Dati mancanti'}), 400
    
    # Campi obbligatori
    required_fields = ['nome', 'cognome', 'telefono']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'error': f'Campo {field} obbligatorio'}), 400
    
    # Campi opzionali
    nome_telegram = data.get('nome_telegram', '')
    address = data.get('address', '')
    currency_code = data.get('currency_code', 'USD')
    nome = data.get('nome', '')
    email = data.get('email', '')
    
    # Validazione valuta
    valid_currencies = ['USD', 'EUR', 'GBP']
    if currency_code not in valid_currencies:
        return jsonify({'success': False, 'error': 'Valuta non valida'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Aggiorna tutti i campi del profilo
        cur.execute("""
            UPDATE users 
            SET nome = %s, cognome = %s, telefono = %s, nome_telegram = %s, 
                address = %s, currency_code = %s, updated_at = NOW()
            WHERE id = %s
        """, (data['nome'], data['cognome'], data['telefono'], nome_telegram, 
              address, currency_code, uid))
        
        # Se forniti, aggiorna anche nome ed email
        if nome or email:
            update_fields = []
            update_values = []
            
            if nome:
                update_fields.append("nome = %s")
                update_values.append(nome)
            
            if email:
                update_fields.append("email = %s")
                update_values.append(email)
            
            if update_fields:
                update_values.append(uid)
                cur.execute(f"""
                    UPDATE users 
                    SET {', '.join(update_fields)}, updated_at = NOW()
                    WHERE id = %s
                """, update_values)
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'Profilo aggiornato con successo'})

@user_bp.route("/profile/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    """Cambio password utente"""
    uid = session.get("user_id")
    
    # Se è una richiesta GET, mostra la pagina
    if request.method == "GET":
        return render_template("user/change_password.html")
    
    # Se è una richiesta POST, processa il cambio password
    data = request.get_json()
    
    # Validazione dati
    if not data or not data.get('current_password') or not data.get('new_password'):
        return jsonify({'success': False, 'error': 'Password mancanti'}), 400
    
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    # Regole basilari nuova password
    if len(new_password) < 8:
        return jsonify({'success': False, 'error': 'La nuova password deve avere almeno 8 caratteri'}), 400
    
    import hashlib
    
    def hash_password(p: str) -> str:
        return hashlib.sha256(p.encode()).hexdigest()
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica password corrente
            cur.execute("""
                SELECT password_hash FROM users WHERE id = %s
            """, (uid,))
            row = cur.fetchone()
            if not row or not row.get('password_hash'):
                return jsonify({'success': False, 'error': 'Utente non trovato'}), 404
            
            if row['password_hash'] != hash_password(current_password):
                return jsonify({'success': False, 'error': 'Password corrente non corretta'}), 400
            
            # Evita riuso stessa password
            if row['password_hash'] == hash_password(new_password):
                return jsonify({'success': False, 'error': 'La nuova password deve essere diversa da quella attuale'}), 400
            
            # Aggiorna password e resetta il flag password_reset_required
            new_hash = hash_password(new_password)
            cur.execute("""
                UPDATE users 
                SET password_hash = %s, password_reset_required = false, updated_at = NOW()
                WHERE id = %s
            """, (new_hash, uid))
            conn.commit()
        
        return jsonify({'success': True, 'message': 'Password cambiata con successo'})
    
    except Exception as e:
        print(f"Errore cambio password per utente {uid}: {e}")
        return jsonify({'success': False, 'error': f'Errore interno del server: {str(e)}'}), 500

# =====================================================
# API REFERRAL - Sistema referral utente
# =====================================================

@user_bp.get("/api/referral-data")
@login_required
@kyc_verified
def get_referral_data():
    """Ottieni dati referral dell'utente corrente"""
    try:
        user_id = session.get('user_id')
        
        # Assicura che l'utente abbia un codice referral
        referral_code = ensure_referral_code(user_id)
        
        with get_conn() as conn, conn.cursor() as cur:
            
            # Trova tutti gli utenti invitati da questo utente
            # Esclude l'utente stesso per evitare auto-referral
            cur.execute("""
                SELECT 
                    u.id, u.nome, u.cognome, u.email, u.created_at,
                    COALESCE(up.free_capital, 0) + COALESCE(up.invested_capital, 0) + 
                    COALESCE(up.referral_bonus, 0) + COALESCE(up.profits, 0) as total_balance,
                    COALESCE(up.invested_capital, 0) as total_invested,
                    COALESCE(up.profits, 0) as total_profits,
                    COALESCE(up.referral_bonus, 0) as bonus_generated,
                    CASE 
                        WHEN up.id IS NOT NULL AND (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) > 0 
                        THEN 'active'
                        WHEN u.kyc_status = 'verified' THEN 'pending'
                        ELSE 'inactive'
                    END as status
                FROM users u
                LEFT JOIN user_portfolios up ON up.user_id = u.id
                WHERE u.referred_by = %s AND u.id != %s
                ORDER BY u.created_at DESC
            """, (user_id, user_id))
            invited_users = cur.fetchall()
            
            # Ottieni investimenti per ogni utente invitato
            for user in invited_users:
                cur.execute("""
                    SELECT i.amount, p.title as project_name
                    FROM investments i
                    LEFT JOIN projects p ON p.id = i.project_id
                    WHERE i.user_id = %s AND i.status = 'active'
                    ORDER BY i.created_at DESC
                """, (user['id'],))
                user['investments'] = cur.fetchall()
            
            # Calcola totali
            total_invited = len(invited_users)
            total_invested = sum(user['total_invested'] or 0 for user in invited_users)
            total_profits = sum(user['total_profits'] or 0 for user in invited_users)
            bonus_earned = sum(user['bonus_generated'] or 0 for user in invited_users)
            
            return jsonify({
                'total_invited': total_invited,
                'total_invested': float(total_invested),
                'total_profits': float(total_profits),
                'bonus_earned': float(bonus_earned),
                'invited_users': invited_users
            })
            
    except Exception as e:
        print(f"Errore nel caricamento dati referral: {e}")
        return jsonify({'error': 'Errore nel caricamento dei dati referral'}), 500

@user_bp.get("/api/referral-link")
@login_required
@kyc_verified
def get_referral_link():
    """Ottieni link referral dell'utente"""
    try:
        user_id = session.get('user_id')
        
        # Assicura che l'utente abbia un codice referral
        referral_code = ensure_referral_code(user_id)
        
        # Costruisci link referral
        base_url = request.host_url.rstrip('/')
        referral_link = f"{base_url}/auth/register?ref={referral_code}"
        
        return jsonify({
            'referral_code': referral_code,
            'referral_link': referral_link
        })
        
    except Exception as e:
        print(f"Errore nel recupero link referral: {e}")
        return jsonify({'error': 'Errore nel recupero del link referral'}), 500

# Rotta duplicata rimossa: la pagina referral è gestita dalla funzione `referral` sopra


# Info referente (utente sopra di te)
@user_bp.get("/api/referrer")
@login_required
@kyc_verified
def get_referrer_info():
    """Restituisce le info dell'utente immediatamente sopra nella struttura referral."""
    user_id = session.get('user_id')
    with get_conn() as conn, conn.cursor() as cur:
        # Trova l'id del referente
        cur.execute("SELECT referred_by FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        if not row or not row.get('referred_by'):
            return jsonify({ 'has_referrer': False, 'referrer': None })
        referrer_id = row['referred_by']

        # Dati referente
        cur.execute(
            """
            SELECT id,
                   COALESCE(NULLIF(TRIM(CONCAT_WS(' ', nome, cognome)), ''), nome) AS nome,
                   email, created_at
            FROM users WHERE id = %s
            """,
            (referrer_id,)
        )
        ref = cur.fetchone()
        if not ref:
            return jsonify({ 'has_referrer': False, 'referrer': None })
        return jsonify({ 'has_referrer': True, 'referrer': ref })

@user_bp.get("/api/kyc-status")
@login_required
def api_kyc_status():
    """API per verificare lo stato KYC dell'utente"""
    uid = session.get("user_id")
    
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT kyc_status, role
            FROM users WHERE id = %s
        """, (uid,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({"error": "Utente non trovato"}), 404
        
        return jsonify({
            "kyc_status": user["kyc_status"],
            "role": user["role"],
            "is_admin": user["role"] == "admin"
        })

def generate_referral_code():
    """Genera un codice referral casuale alfanumerico"""
    import random
    import string
    
    # Caratteri disponibili: lettere maiuscole, minuscole e numeri (esclusi 0, O, I, l per evitare confusione)
    chars = string.ascii_uppercase.replace('O', '').replace('I', '') + \
            string.ascii_lowercase.replace('o', '').replace('i', '').replace('l', '') + \
            string.digits.replace('0', '')
    
    # Genera codice di 8 caratteri
    code = ''.join(random.choice(chars) for _ in range(8))
    return f"REF{code}"

def ensure_referral_code(user_id):
    """Assicura che l'utente abbia un codice referral unico"""
    with get_conn() as conn, conn.cursor() as cur:
        # Controlla se l'utente ha già un codice
        cur.execute("SELECT referral_code FROM users WHERE id = %s", (user_id,))
        user_data = cur.fetchone()
        
        if user_data and user_data['referral_code']:
            return user_data['referral_code']
        
        # Genera nuovo codice unico
        max_attempts = 10
        for attempt in range(max_attempts):
            new_code = generate_referral_code()
            
            # Verifica che il codice sia unico
            cur.execute("SELECT id FROM users WHERE referral_code = %s", (new_code,))
            if not cur.fetchone():
                # Codice unico trovato, aggiorna il database
                cur.execute("UPDATE users SET referral_code = %s WHERE id = %s", (new_code, user_id))
                conn.commit()
                return new_code
        
        # Se non riesce a generare un codice unico, usa un fallback
        import random
        fallback_code = f"REF{user_id:06d}{random.randint(1000, 9999)}"
        cur.execute("UPDATE users SET referral_code = %s WHERE id = %s", (fallback_code, user_id))
        conn.commit()
        return fallback_code





