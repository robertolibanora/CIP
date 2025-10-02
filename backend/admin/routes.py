import os
import uuid
import time
import logging
import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, redirect, url_for, session, abort, send_from_directory, jsonify, render_template, send_file, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

# Setup logger
logger = logging.getLogger(__name__)

# -----------------------------
# DB
# -----------------------------

def get_conn():
    from backend.shared.database import get_connection
    return get_connection()

def get_upload_folder():
    """Ottiene la cartella upload dalla configurazione Flask"""
    from flask import current_app
    return current_app.config.get('UPLOAD_FOLDER', 'uploads')

def ensure_admin_actions_table(cur):
    """Crea la tabella admin_actions se non esiste."""
    try:
        # Verifica se la tabella esiste già
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'admin_actions'
            )
        """)
        exists = cur.fetchone()[0]
        
        if not exists:
            cur.execute(
                """
                CREATE TABLE admin_actions (
                id SERIAL PRIMARY KEY,
                admin_id INT REFERENCES users(id) ON DELETE SET NULL,
                action TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_id INT NOT NULL,
                details TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
            )
    except Exception as e:
        # Log dell'errore ma non bloccare l'esecuzione
        print(f"Warning: Could not create admin_actions table: {e}")
        # Rollback della transazione per evitare errori
        try:
            cur.connection.rollback()
        except:
            pass

# -----------------------------
# ADMIN BLUEPRINT (protected)
# -----------------------------
admin_bp = Blueprint("admin", __name__)

# Importa decoratori di autorizzazione
from backend.auth.decorators import admin_required

# Route temporanea per notifiche rimosse - restituisce 404 pulito
@admin_bp.get("/api/notifications/unread-count")
@admin_required
def notifications_unread_count():
    """Route temporanea per notifiche rimosse - restituisce 404"""
    return jsonify({'error': 'Notifiche rimosse'}), 404

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione admin

@admin_bp.get("/")
def admin_dashboard():
    # Controllo manuale se l'utente è admin
    from flask import session
    if 'user_id' not in session:
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    
    from backend.auth.middleware import is_admin
    if not is_admin():
        from flask import redirect, url_for, flash
        flash("Accesso negato. Solo gli amministratori possono accedere a questa pagina", "error")
        return redirect(url_for('user.dashboard'))
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_admin_metrics")
        m = cur.fetchone()
    
    # Renderizza il template admin
    return render_template("admin/dashboard.html", metrics=m or {})

# Alias esplicito per la dashboard admin su /admin/dashboard
@admin_bp.get("/dashboard")
@admin_required
def admin_dashboard_alias():
    """Alias di comodo per accedere alla dashboard admin.
    Garantisce che i link a /admin/dashboard funzionino sempre."""
    return admin_dashboard()

@admin_bp.get("/metrics")
@admin_required
def metrics():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_admin_metrics")
        m = cur.fetchone()
    return jsonify(m or {})

# ---- Gestione Progetti ----
@admin_bp.get("/projects")
@admin_required
def projects_list():
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        status = request.args.get('status')
        q = []
        params = []
        if status:
            q.append("status=%s"); params.append(status)
        where = ("WHERE "+" AND ".join(q)) if q else ""
        sql = f"""SELECT * FROM projects {where} ORDER BY 
            CASE 
                WHEN status = 'active' THEN 1
                WHEN status = 'completed' THEN 2
                WHEN status = 'sold' THEN 3
                WHEN status = 'cancelled' THEN 4
                ELSE 5
            END,
            created_at DESC"""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            
            # Aggiungi photo_filename per compatibilit con template
            for row in rows:
                if row.get('photo_filename'):
                    row['photo_filename'] = row['photo_filename']
                else:
                    row['photo_filename'] = None
                    
        return jsonify(rows)
    
    # Altrimenti restituisce il template HTML con metriche
    
    # Ottieni metriche progetti per il sidebar
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM projects")
        projects_total = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as active FROM projects WHERE status = 'active'")
        projects_active = cur.fetchone()['active']
        
        cur.execute("SELECT COUNT(*) as draft FROM projects WHERE status = 'draft'")
        projects_draft = cur.fetchone()['draft']
        
        cur.execute("SELECT COUNT(*) as completed FROM projects WHERE status = 'completed'")
        projects_completed = cur.fetchone()['completed']
        
        cur.execute("SELECT COUNT(*) as sold FROM projects WHERE status = 'sold'")
        projects_sold = cur.fetchone()['sold']
    
    metrics = {
        'projects_total': projects_total,
        'projects_active': projects_active,
        'projects_draft': projects_draft,
        'projects_completed': projects_completed,
        'projects_sold': projects_sold,
        'projects_active': projects_active  # Per compatibilit con sidebar
    }
    
    return render_template("admin/projects/list.html", metrics=metrics)

@admin_bp.post("/projects/new")
@admin_required
def projects_new():
    try:
        # Gestisce sia form data che JSON
        if request.is_json:
            data = request.json or {}
            logger.info(f"Received JSON data: {data}")
        else:
            data = request.form.to_dict()
            logger.info(f"Received form data: {data}")
            logger.info(f"Received files: {list(request.files.keys())}")
        
        # Validazione di base dei campi numerici
        try:
            if 'target_amount' in data and data['target_amount']:
                float(data['target_amount'])
            if 'min_investment' in data and data['min_investment']:
                float(data['min_investment'])
            if 'roi' in data and data['roi']:
                float(data['roi'])
        except (ValueError, TypeError) as ve:
            return jsonify({
                "success": False,
                "error": f"Valore numerico non valido: {str(ve)}",
                "message": f"Valore numerico non valido: {str(ve)}"
            }), 400
        
        # Valori di default per campi obbligatori (genera code_value una sola volta)
        code_value = data.get('code') or f'PRJ{int(time.time())}'
        
        # Gestione file upload
        photo = request.files.get('photo') or request.files.get('main_image')
        documents = request.files.get('documents')
        
        # Debug: Log dei file ricevuti
        logger.info(f"File ricevuti: {list(request.files.keys())}")
        if photo:
            logger.info(f"Photo file: {photo.filename}, Content-Type: {photo.content_type}")
        else:
            logger.warning("Nessun file photo trovato!")
        
        # Salva i file (in uploads/projects)
        photo_filename = None
        documents_filename = None
        
        try:
            if photo and photo.filename:
                # Validazione formato file
                allowed_extensions = {'.jpg', '.jpeg', '.png'}
                ext = os.path.splitext(photo.filename)[1].lower()
                if ext not in allowed_extensions:
                    return jsonify({
                        "success": False,
                        "error": "Formato immagine non supportato. Usa JPG o PNG",
                        "message": "Formato immagine non supportato. Usa JPG o PNG"
                    }), 400
                
                # Validazione dimensione file (max 5MB)
                photo.seek(0, os.SEEK_END)
                file_size = photo.tell()
                photo.seek(0)
                if file_size > 5 * 1024 * 1024:  # 5MB
                    return jsonify({
                        "success": False,
                        "error": "File troppo grande. Massimo 5MB",
                        "message": "File troppo grande. Massimo 5MB"
                    }), 400
                
                # Genera nome file sicuro
                photo_filename = secure_filename(f"{code_value}_{int(time.time())}{ext}")
                
                # Usa la cartella uploads/projects nella root del progetto
                projects_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
                photo_path = os.path.join(projects_dir, photo_filename)
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                
                # Salva il file
                photo.save(photo_path)
                logger.info(f"Immagine salvata con successo: {photo_path}")
                
                # Verifica che il file sia stato effettivamente salvato
                if not os.path.exists(photo_path):
                    logger.error(f"File non trovato dopo il salvataggio: {photo_path}")
                    return jsonify({
                        "success": False,
                        "error": "Errore nel salvataggio dell'immagine",
                        "message": "Errore nel salvataggio dell'immagine"
                    }), 500
            
            # Documenti non più richiesti
        
        except Exception as e:
            logger.error(f"Errore nel salvataggio dei file: {e}")
            import traceback
            logger.error(f"Traceback completo: {traceback.format_exc()}")
            return jsonify({
                "success": False,
                "error": f"Errore nel salvataggio dell'immagine: {str(e)}",
                "message": f"Errore nel salvataggio dell'immagine: {str(e)}"
            }), 500
        
        # Mappa address -> location (compatibilit schema) con valori di default
        location_value = data.get('address') or data.get('location') or 'Indirizzo non specificato'
        status_value = data.get('status', 'draft')
        
        # Validazione campi obbligatori
        name_value = data.get('title', '').strip()
        if not name_value:
            return jsonify({
                "error": "Il titolo del progetto è obbligatorio",
                "message": "Inserisci un titolo per il progetto"
            }), 400
        
        # Campi opzionali schema esteso con valori di default
        roi_value = float(data.get('roi', 8.0))
        project_type = data.get('type', 'residential')
        description_value = data.get('description') or 'Descrizione non fornita'
        total_amount_value = float(data.get('target_amount', 100000))
        min_investment_value = float(data.get('min_investment', 1000))
        
        # Data di inizio - usa data di default se non fornita
        start_date_value = data.get('start_date') or date.today().isoformat()
        
        # Inserisci nel database (schema con location, image_url, senza documents)
        logger.info(f"Salvando progetto nel database - image_url: {photo_filename}")
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO projects (
                    code, name, title, description, status, total_amount, start_date,
                    location, min_investment, image_url, roi, type, funded_amount, duration
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
                """,
                (
                    code_value, name_value, name_value, description_value, status_value,
                    total_amount_value, start_date_value,
                    location_value, min_investment_value, 
                    photo_filename if photo_filename else None,
                    roi_value, project_type, 0.0, 365
                )
            )
            pid = cur.fetchone()['id']
            logger.info(f"Progetto creato con ID: {pid}, image_url: {photo_filename}")
            
            conn.commit()
        
        return jsonify({"id": pid, "message": "Progetto creato con successo"})
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Errore nella creazione del progetto: {e}")
        logger.error(f"Traceback completo: {error_details}")
        return jsonify({
            "success": False,
            "error": f"Errore interno del server: {str(e)}",
            "message": f"Errore interno del server: {str(e)}"
        }), 500

@admin_bp.get("/uploads/projects/<filename>")
@admin_required
def serve_project_file(filename):
    """Serve i file upload dei progetti (foto e documenti)"""
    # Usa la cartella uploads/projects nella root del progetto
    projects_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
    
    if not os.path.exists(os.path.join(projects_folder, filename)):
        abort(404)
    
    return send_from_directory(projects_folder, filename)


@admin_bp.get("/projects/<int:pid>/cancel-data")
@admin_required
def project_cancel_data(pid):
    """Ottiene i dati necessari per l'annullamento di un progetto"""
    with get_conn() as conn, conn.cursor() as cur:
        # Dettagli progetto (solo se attivo)
        cur.execute("""
            SELECT id, code, title, description, total_amount, funded_amount, 
                   min_investment, status, created_at
            FROM projects 
            WHERE id = %s AND status = 'active'
        """, (pid,))
        project = cur.fetchone()
        
        if not project:
            return jsonify({'error': 'Progetto non trovato o non attivo'}), 404
        
        # Investimenti attivi per questo progetto
        cur.execute("""
            SELECT i.id, i.amount, i.status, i.created_at,
                   u.id as user_id, u.nome, u.cognome, u.email,
                   CONCAT(u.nome, ' ', u.cognome) as user_name
            FROM investments i
            JOIN users u ON u.id = i.user_id
            WHERE i.project_id = %s AND i.status = 'active'
            ORDER BY i.created_at DESC
        """, (pid,))
        investments = cur.fetchall()
        
        return jsonify({
            'project': project,
            'investments': investments
        })


@admin_bp.get("/projects/<int:pid>")
@admin_required
def project_detail(pid):
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        with get_conn() as conn, conn.cursor() as cur:
            # Dettagli progetto
            cur.execute("SELECT * FROM projects WHERE id=%s", (pid,))
            project = cur.fetchone()
            if not project:
                abort(404)
            
            # Investimenti collegati
            cur.execute("""
                SELECT i.id, i.amount, i.status, i.created_at,
                       u.id as user_id, u.nome, u.cognome, u.email, u.kyc_status,
                       CONCAT(u.nome, ' ', u.cognome) as full_name
                FROM investments i
                JOIN users u ON u.id = i.user_id
                WHERE i.project_id = %s
                ORDER BY i.created_at DESC
            """, (pid,))
            investments = cur.fetchall()
            
            # Documenti/immagini del progetto (TODO: implementare con project_id)
            documents = []
            
            # Statistiche
            cur.execute("""
                SELECT 
                    COUNT(*) as investors_count,
                    COALESCE(SUM(amount), 0) as total_invested,
                    AVG(amount) as avg_investment
                FROM investments 
                WHERE project_id = %s AND status IN ('active', 'completed')
            """, (pid,))
            stats = cur.fetchone()
            
            return jsonify({
                "project": project,
                "investments": investments,
                "documents": documents,
                "stats": stats
            })
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    return render_template("admin/projects/detail.html", project_id=pid)

@admin_bp.post("/projects/<int:pid>/edit")
@admin_required
def projects_edit(pid):
    # Ottieni i dati dalla richiesta
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict()
    
    # Se non ci sono dati, restituisci errore
    if not data:
        if request.headers.get('Content-Type') == 'application/json':
            return jsonify({"error": "Nessun dato ricevuto"}), 400
        else:
            return redirect(url_for('admin.projects_detail', pid=pid))
    
    # Aggiorna il progetto con i dati ricevuti
    with get_conn() as conn, conn.cursor() as cur:
        # Costruisci la query SQL direttamente
        update_fields = []
        params = []
        
        if 'code' in data and data['code']:
            update_fields.append("code = %s")
            params.append(data['code'])
        
        if 'title' in data and data['title']:
            update_fields.append("title = %s")
            params.append(data['title'])
        
        if 'description' in data and data['description']:
            update_fields.append("description = %s")
            params.append(data['description'])
        
        if 'project_details' in data:
            update_fields.append("project_details = %s")
            params.append(data['project_details'])
        
        if 'status' in data and data['status']:
            update_fields.append("status = %s")
            params.append(data['status'])
        
        if 'total_amount' in data and data['total_amount']:
            update_fields.append("total_amount = %s")
            params.append(float(data['total_amount']))
        
        # start_date rimosso - non modificabile, sempre uguale alla data di creazione
        
        
        if not update_fields:
            if request.headers.get('Content-Type') == 'application/json':
                return jsonify({"error": "Nessun campo valido da aggiornare"}), 400
            else:
                return redirect(url_for('admin.projects_detail', pid=pid))
        
        # Esegui l'aggiornamento
        params.append(pid)
        sql = f"UPDATE projects SET {', '.join(update_fields)} WHERE id = %s"
        
        cur.execute(sql, params)
        
        
        conn.commit()
    
    # Restituisci risposta di successo
    if request.headers.get('Content-Type') == 'application/json':
        return jsonify({"updated": True, "message": "Progetto aggiornato con successo"})
    else:
        return redirect(url_for('admin.projects_detail', pid=pid))

@admin_bp.post("/projects/<int:pid>/cancel")
@admin_required
def projects_cancel(pid):
    """Annulla un progetto e rimborsa gli investitori"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il progetto esista e sia attivo
            cur.execute("""
                SELECT id, name, funded_amount, status 
                FROM projects 
                WHERE id = %s AND status = 'active'
            """, (pid,))
            project = cur.fetchone()
            
            if not project:
                return jsonify({"error": "Progetto non trovato o non attivo"}), 404
            
            # Ottieni tutti gli investimenti attivi per questo progetto
            cur.execute("""
                SELECT i.id, i.user_id, i.amount, u.email
                FROM investments i
                JOIN users u ON u.id = i.user_id
                WHERE i.project_id = %s AND i.status = 'active'
            """, (pid,))
            investments = cur.fetchall()
            
            # Rimborsa tutti gli investimenti attivi
            for investment in investments:
                user_id = investment['user_id']
                amount = investment['amount']
                
                # Aggiorna il portfolio dell'utente: rimuovi da invested_capital e aggiungi a free_capital
                cur.execute("""
                    UPDATE user_portfolios 
                    SET invested_capital = invested_capital - %s,
                        free_capital = free_capital + %s
                    WHERE user_id = %s
                """, (amount, amount, user_id))
                
                # Se il portfolio non esiste, crealo
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                        VALUES (%s, %s, 0, 0, 0)
                    """, (user_id, amount))
                
                # Aggiorna lo status dell'investimento a cancelled
                cur.execute("""
                    UPDATE investments 
                    SET status = 'cancelled'
                    WHERE id = %s
                """, (investment['id'],))
            
            # Aggiorna lo status del progetto a cancelled (rimuovi updated_at che non esiste)
            cur.execute("""
                UPDATE projects 
                SET status = 'cancelled'
                WHERE id = %s
            """, (pid,))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "message": f"Progetto annullato con successo. Rimborsati {len(investments)} investimenti per un totale di €{project['funded_amount']:,.2f}",
                "refunded_investments": len(investments),
                "total_refunded": float(project['funded_amount'])
            })
            
    except Exception as e:
        return jsonify({"error": f"Errore durante l'annullamento: {str(e)}"}), 500

def process_referral_bonus(cur, user_id, profit_amount, project_id):
    """Processa i bonus referral per un utente che ha ricevuto profitti"""
    try:
        # Assicurati che profit_amount sia un float
        profit_amount = float(profit_amount)
        
        # Trova chi ha invitato questo utente
        cur.execute("""
            SELECT u.referred_by as referrer_id, r.is_vip
            FROM users u
            JOIN users r ON r.id = u.referred_by
            WHERE u.id = %s AND u.referred_by IS NOT NULL
        """, (user_id,))
        referral_data = cur.fetchone()
        
        if not referral_data:
            # Nessun referral trovato, il 2% va all'utente ID 2
            bonus_amount = profit_amount * 0.02
            
            # Usa UPSERT per evitare problemi di concorrenza
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                VALUES (2, 0, 0, 0, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET referral_bonus = user_portfolios.referral_bonus + %s
            """, (bonus_amount, bonus_amount))
            
            return {"referrer_id": 2, "bonus_amount": float(bonus_amount), "is_vip": False, "source": "default"}
        
        referrer_id = referral_data['referrer_id']
        is_vip = referral_data['is_vip']
        
        # Calcola bonus: 5% per VIP, 3% per non-VIP
        bonus_percentage = 0.05 if is_vip else 0.03
        bonus_amount = float(profit_amount) * bonus_percentage
        
        # Usa UPSERT per il referrer
        cur.execute("""
            INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
            VALUES (%s, 0, 0, 0, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET referral_bonus = user_portfolios.referral_bonus + %s
        """, (referrer_id, bonus_amount, bonus_amount))
        
        # Se non è VIP, il 2% va all'utente ID 2
        if not is_vip:
            additional_bonus = float(profit_amount) * 0.02
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                VALUES (2, 0, 0, 0, %s)
                ON CONFLICT (user_id) 
                DO UPDATE SET referral_bonus = user_portfolios.referral_bonus + %s
            """, (additional_bonus, additional_bonus))
        
        return {
            "referrer_id": referrer_id, 
            "bonus_amount": float(bonus_amount), 
            "is_vip": is_vip,
            "source": "referral"
        }
        
    except Exception as e:
        logger.error(f"Errore nel processare referral bonus per user {user_id}: {e}")
        return None


# ============ PROGETTI: VENDITA SEMPLIFICATA ======================
@admin_bp.post("/projects/<int:pid>/sell")
@admin_required
def projects_sell(pid):
    """Imposta il progetto come 'sold', distribuisce i profitti agli investitori e calcola i bonus referral.

    Input JSON: { "sale_price": number }
    """
    try:
        data = request.get_json() or {}
        sale_price = float(data.get("sale_price", 0))
        if sale_price <= 0:
            return jsonify({"error": "Inserisci un prezzo di vendita valido"}), 400

        with get_conn() as conn, conn.cursor() as cur:
            conn.autocommit = False

            # Blocco il progetto e leggo i dati essenziali
            cur.execute(
                """
                SELECT id, status, COALESCE(funded_amount, 0) AS funded_amount
                FROM projects
                WHERE id = %s
                """,
                (pid,),
            )
            project = cur.fetchone()
            if not project:
                return jsonify({"error": "Progetto non trovato"}), 404

            # dict_row: accedi per chiave
            project_status = project.get('status') if isinstance(project, dict) else project[1]
            if project_status != "completed":
                return jsonify({"error": "Il progetto deve essere in stato 'completed'"}), 400

            # Recupero investimenti attivi
            cur.execute(
                """
                SELECT id, user_id, amount
                FROM investments
                WHERE project_id = %s AND status = 'active'
                """,
                (pid,),
            )
            investments = cur.fetchall() or []

            # Calcolo totale investito (fallback a somma investimenti se funded_amount non affidabile)
            funded_amount_value = project.get('funded_amount') if isinstance(project, dict) else project[2]
            total_invested = float(funded_amount_value or 0)
            if total_invested <= 0 and investments:
                total_invested = sum(float(inv.get('amount') if isinstance(inv, dict) else inv[2]) for inv in investments)

            if total_invested <= 0:
                return jsonify({"error": "Nessun investimento registrato per il progetto"}), 400

            total_profit = float(sale_price) - total_invested

            # Calcola profit_percentage e aggiorna progetto a 'sold'
            profit_percentage = (total_profit / total_invested) * 100 if total_invested > 0 else 0
            cur.execute(
                """
                UPDATE projects
                SET status = 'sold', sale_price = %s, sold_at = NOW(), profit_percentage = %s
                WHERE id = %s
                """,
                (sale_price, profit_percentage, pid),
            )

            # Imposto tutti gli investimenti a completed
            cur.execute(
                """
                UPDATE investments SET status = 'completed' WHERE project_id = %s AND status = 'active'
                """,
                (pid,),
            )

            # Distribuzione profitti proporzionale e bonus referral
            for inv in investments:
                investment_amount = float(inv.get('amount') if isinstance(inv, dict) else inv[2])
                if investment_amount <= 0:
                    continue
                user_id = int(inv.get('user_id') if isinstance(inv, dict) else inv[1])
                profit_share = (investment_amount / total_invested) * total_profit

                # Upsert su user_portfolios: aggiungo ai profits
                cur.execute(
                    """
                    INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                    VALUES (%s, 0, 0, 0, %s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET profits = user_portfolios.profits + EXCLUDED.profits
                    """,
                    (user_id, profit_share),
                )

                # Calcola i bonus referral in base al profitto generato
                process_referral_bonus(cur, user_id, profit_share, pid)

            conn.commit()
            return jsonify(
                {
                    "success": True,
                    "message": "Vendita completata. Profitti e referral distribuiti.",
                    "total_profit": total_profit,
                }
            )

    except Exception as e:
        return jsonify({"error": f"Errore durante la vendita: {str(e)}"}), 500

@admin_required
def projects_delete(pid):
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni dettagli progetto
            cur.execute("SELECT id, name as title, funded_amount FROM projects WHERE id=%s", (pid,))
            project = cur.fetchone()
            
            if not project:
                return jsonify({"error": "Progetto non trovato"}), 404
            
            # Ottieni tutti gli investimenti attivi per questo progetto
            cur.execute("""
                SELECT i.id, i.user_id, i.amount, u.email
                FROM investments i
                JOIN users u ON u.id = i.user_id
                WHERE i.project_id = %s AND i.status = 'active'
            """, (pid,))
            investments = cur.fetchall()
            
            # Rimborsa tutti gli investimenti attivi
            for investment in investments:
                user_id = investment['user_id']
                amount = investment['amount']
                
                # Aggiorna il portfolio dell'utente: rimuovi da invested_capital e aggiungi a free_capital
                cur.execute("""
                    UPDATE user_portfolios 
                    SET invested_capital = invested_capital - %s,
                        free_capital = free_capital + %s
                    WHERE user_id = %s
                """, (amount, amount, user_id))
                
                # Se il portfolio non esiste, crealo
                if cur.rowcount == 0:
                    cur.execute("""
                        INSERT INTO user_portfolios (user_id, free_capital, invested_capital, profits, referral_bonus)
                        VALUES (%s, %s, 0, 0, 0)
                    """, (user_id, amount))
            
            # Elimina tutti gli investimenti per questo progetto (per rispettare il vincolo di chiave esterna)
            cur.execute("DELETE FROM investments WHERE project_id = %s", (pid,))
            
            # Ora elimina il progetto
            cur.execute("DELETE FROM projects WHERE id=%s", (pid,))
            
            if cur.rowcount == 0:
                return jsonify({"error": "Progetto non trovato"}), 404
            
            return jsonify({
                "deleted": True, 
                "message": f"Progetto eliminato. Rimborsati {len(investments)} investimenti per un totale di €{project['funded_amount']:,.2f}"
            })
            
    except Exception as e:
        return jsonify({"error": f"Errore durante l'eliminazione: {str(e)}"}), 500

@admin_bp.post("/projects/<int:pid>/image")
@admin_required
def project_upload_image(pid):
    """Upload dell'immagine principale del progetto"""
    try:
        if 'image' not in request.files:
            return jsonify({"error": "Nessuna immagine selezionata"}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "Nessuna immagine selezionata"}), 400
        
        # Verifica tipo file
        allowed_extensions = {'png', 'jpg', 'jpeg'}
        if not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in allowed_extensions):
            return jsonify({"error": "Formato non supportato. Usa JPG o PNG"}), 400
        
        # Verifica dimensione file (max 5MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        if file_size > 5 * 1024 * 1024:  # 5MB
            return jsonify({"error": "File troppo grande. Massimo 5MB"}), 400
        
        # Genera nome file sicuro
        ext = os.path.splitext(file.filename)[1].lower() or '.jpg'
        timestamp = int(time.time())
        filename = secure_filename(f"project_{pid}_main_{timestamp}{ext}")
        
        # Salva file
        projects_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
        os.makedirs(projects_dir, exist_ok=True)
        file_path = os.path.join(projects_dir, filename)
        file.save(file_path)
        
        # Aggiorna database - cambia l'immagine principale
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il progetto esista
            cur.execute("SELECT id, image_url FROM projects WHERE id = %s", (pid,))
            result = cur.fetchone()
            
            if not result:
                return jsonify({"error": "Progetto non trovato"}), 404
            
            # Aggiorna l'immagine principale
            cur.execute("""
                UPDATE projects 
                SET image_url = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (filename, pid))
            
            conn.commit()
        
        logger.info(f"Immagine principale aggiornata per progetto {pid}: {filename}")
        return jsonify({
            "success": True, 
            "filename": filename, 
            "message": "Immagine principale aggiornata con successo"
        })
        
    except Exception as e:
        logger.error(f"Errore nell'upload dell'immagine: {e}")
        return jsonify({"error": f"Errore interno del server: {str(e)}"}), 500

@admin_bp.post("/projects/<int:pid>/upload")
@admin_required
def project_upload_file(pid):
    if 'file' not in request.files:
        return jsonify({"error": "Nessun file selezionato"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nessun file selezionato"}), 400
    
    # Verifica tipo file
    allowed_extensions = {'jpg', 'jpeg', 'png', 'pdf'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({"error": "Tipo file non supportato. Usa JPG, PNG o PDF"}), 400
    
    # Verifica dimensione (max 10MB)
    if len(file.read()) > 10 * 1024 * 1024:
        return jsonify({"error": "File troppo grande. Massimo 10MB"}), 400
    
    file.seek(0)  # Reset file pointer
    
    filename = secure_filename(file.filename)
    unique_filename = f"{uuid.uuid4()}-{filename}"
    file_path = os.path.join(get_upload_folder(), unique_filename)
    
    # Crea cartella se non esiste
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    file.save(file_path)
    
    # TODO: Salva nel database con project_id (richiede modifica schema)
    # Per ora salvo solo il file fisicamente
    doc_id = 1  # Mock ID
    
    return jsonify({
        "success": True,
        "document_id": doc_id,
        "filename": unique_filename,
        "original_name": filename
    })

# ---- Gestione Immagini Progetti ----
@admin_bp.get("/projects/images/<filename>")
def serve_project_images(filename):
    """Serve le immagini dei progetti"""
    try:
        from flask import send_from_directory
        import os
        
        # Percorso della cartella uploads/projects (stesso percorso usato per il salvataggio)
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
        logger.info(f"Serving image: {filename} from directory: {upload_dir}")
        
        # Verifica che il file esista
        file_path = os.path.join(upload_dir, filename)
        if not os.path.exists(file_path):
            logger.error(f"Image not found: {file_path}")
            from flask import abort
            abort(404)
        
        logger.info(f"Image found, serving: {file_path}")
        
        return send_from_directory(upload_dir, filename)
    except Exception as e:
        logger.error(f"Errore nel servire immagine {filename}: {e}")
        from flask import abort
        abort(404)

@admin_bp.post("/projects/<int:pid>/gallery/upload")
@admin_required
def project_upload_gallery_image(pid):
    """Carica una nuova immagine nella galleria del progetto"""
    logger.info(f"=== GALLERY UPLOAD START === Project ID: {pid}")
    
    if 'file' not in request.files:
        logger.error("No file in request.files")
        return jsonify({"error": "Nessun file selezionato"}), 400
    
    file = request.files['file']
    logger.info(f"File received: {file.filename}, content_type: {file.content_type}")
    
    if file.filename == '':
        logger.error("Empty filename")
        return jsonify({"error": "Nessun file selezionato"}), 400
    
    # Verifica tipo file
    allowed_extensions = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    logger.info(f"File extension: {file_ext}")
    
    if file_ext not in allowed_extensions:
        logger.error(f"Invalid file extension: {file_ext}")
        return jsonify({"error": "Tipo file non supportato. Usa JPG, PNG, GIF o WebP"}), 400
    
    # Verifica dimensione (max 5MB per immagine)
    file.seek(0, 2)  # Vai alla fine del file
    file_size = file.tell()
    file.seek(0)  # Torna all'inizio
    logger.info(f"File size: {file_size} bytes")
    
    if file_size > 5 * 1024 * 1024:
        logger.error(f"File too large: {file_size} bytes")
        return jsonify({"error": "File troppo grande. Massimo 5MB"}), 400
    
    try:
        # Genera nome file unico
        filename = secure_filename(file.filename)
        unique_filename = f"project_{pid}_{int(time.time())}_{filename}"
        logger.info(f"Generated filename: {unique_filename}")
        
        # Salva file nella cartella uploads/projects/ (cartella corretta per nginx)
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads', 'projects')
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)
        logger.info(f"Saving file to: {file_path}")
        
        file.save(file_path)
        logger.info(f"File saved successfully: {file_path}")
        
        # Verifica che il file sia stato salvato
        if not os.path.exists(file_path):
            logger.error(f"File not found after save: {file_path}")
            return jsonify({"error": "Errore nel salvataggio del file"}), 500
        
        # Aggiorna la galleria nel database
        logger.info(f"Saving to database: {unique_filename}")
        
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni la galleria attuale
            cur.execute("SELECT gallery FROM projects WHERE id = %s", (pid,))
            result = cur.fetchone()
            
            if not result:
                logger.error(f"Project {pid} not found in database")
                return jsonify({"error": "Progetto non trovato"}), 404
            
            current_gallery = result['gallery'] or []
            if not isinstance(current_gallery, list):
                current_gallery = []
            
            logger.info(f"Current gallery: {current_gallery}")
            
            # Aggiungi la nuova immagine
            current_gallery.append(unique_filename)
            logger.info(f"New gallery: {current_gallery}")
            
            # Aggiorna il database
            cur.execute("""
                UPDATE projects 
                SET gallery = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (json.dumps(current_gallery), pid))
            
            conn.commit()
            logger.info(f"Database updated successfully for project {pid}")
            
            # Verifica che l'aggiornamento sia andato a buon fine
            cur.execute("SELECT gallery FROM projects WHERE id = %s", (pid,))
            verify_result = cur.fetchone()
            logger.info(f"Verification - Gallery in DB: {verify_result['gallery']}")
            
            return jsonify({
                "success": True,
                "filename": unique_filename,
                "gallery": current_gallery,
                "message": f"Immagine {unique_filename} aggiunta alla galleria"
            })
            
    except Exception as e:
        logger.error(f"Errore durante upload immagine galleria: {str(e)}")
        return jsonify({"error": f"Errore durante l'upload: {str(e)}"}), 500

@admin_bp.delete("/projects/<int:pid>/gallery/<filename>")
@admin_required
def project_delete_gallery_image(pid, filename):
    """Elimina un'immagine dalla galleria del progetto"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni la galleria attuale
            cur.execute("SELECT gallery FROM projects WHERE id = %s", (pid,))
            result = cur.fetchone()
            
            if not result:
                return jsonify({"error": "Progetto non trovato"}), 404
            
            current_gallery = result['gallery'] or []
            if not isinstance(current_gallery, list):
                current_gallery = []
            
            # Rimuovi l'immagine dalla galleria
            if filename in current_gallery:
                current_gallery.remove(filename)
                
                # Aggiorna il database
                cur.execute("""
                    UPDATE projects 
                    SET gallery = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (json.dumps(current_gallery), pid))
                
                conn.commit()
                
                # Elimina il file fisico
                file_path = os.path.join(get_upload_folder(), 'projects', filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                
                return jsonify({
                    "success": True,
                    "gallery": current_gallery
                })
            else:
                return jsonify({"error": "Immagine non trovata nella galleria"}), 404
                
    except Exception as e:
        logger.error(f"Errore durante eliminazione immagine galleria: {str(e)}")
        return jsonify({"error": f"Errore durante l'eliminazione: {str(e)}"}), 500

@admin_bp.put("/projects/<int:pid>/gallery/reorder")
@admin_required
def project_reorder_gallery(pid):
    """Riordina le immagini nella galleria del progetto"""
    try:
        data = request.get_json()
        new_order = data.get('gallery', [])
        
        if not isinstance(new_order, list):
            return jsonify({"error": "Formato galleria non valido"}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il progetto esista
            cur.execute("SELECT id FROM projects WHERE id = %s", (pid,))
            if not cur.fetchone():
                return jsonify({"error": "Progetto non trovato"}), 404
            
            # Aggiorna l'ordine della galleria
            cur.execute("""
                UPDATE projects 
                SET gallery = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (json.dumps(new_order), pid))
            
            conn.commit()
            
            return jsonify({
                "success": True,
                "gallery": new_order
            })
            
    except Exception as e:
        logger.error(f"Errore durante riordinamento galleria: {str(e)}")
        return jsonify({"error": f"Errore durante il riordinamento: {str(e)}"}), 500


# ---- Portfolio Admin ----
@admin_bp.get("/portfolio")
@admin_required
def portfolio_dashboard():
    """Dashboard portfolio admin"""
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(get_portfolio_overview())
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    
    # Ottieni metriche utenti per il sidebar
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM users")
        users_total = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as active FROM users WHERE kyc_status = 'verified'")
        users_active = cur.fetchone()['active']
        
        cur.execute("SELECT COUNT(*) as verified FROM users WHERE kyc_status = 'verified'")
        users_verified = cur.fetchone()['verified']
        
        cur.execute("SELECT COUNT(*) as pending FROM users WHERE kyc_status = 'pending'")
        kyc_pending = cur.fetchone()['pending']
        
        cur.execute("SELECT COUNT(*) as suspended FROM users WHERE kyc_status = 'rejected'")
        users_suspended = cur.fetchone()['suspended']
    
    metrics = {
        'users_total': users_total,
        'users_active': users_active,
        'users_verified': users_verified,
        'kyc_pending': kyc_pending,
        'users_suspended': users_suspended,
        'total_users': users_total  # Per compatibilit con sidebar
    }
    
    return render_template("admin/portfolio/dashboard.html", metrics=metrics)

@admin_bp.get("/portfolio/overview")
@admin_required
def portfolio_overview():
    """Ottiene overview completa portfolio per dashboard"""
    return jsonify(get_portfolio_overview())

def get_portfolio_overview():
    """Helper per ottenere dati overview portfolio"""
    with get_conn() as conn, conn.cursor() as cur:
        # Overview generale
        cur.execute("""
            SELECT 
                COALESCE(SUM(free_capital), 0) as total_free_capital,
                COALESCE(SUM(invested_capital), 0) as total_invested_capital,
                COALESCE(SUM(referral_bonus), 0) as total_bonus,
                COALESCE(SUM(profits), 0) as total_profits,
                COUNT(*) as total_users
            FROM user_portfolios
        """)
        overview = cur.fetchone()
        
        # Calcoli aggiuntivi
        total_capital = (overview['total_free_capital'] + overview['total_invested_capital'] + 
                        overview['total_bonus'] + overview['total_profits'])
        
        # Transazioni recenti
        cur.execute("""
            SELECT pt.*, u.nome as user_name, u.email as user_email
            FROM portfolio_transactions pt
            JOIN users u ON u.id = pt.user_id
            ORDER BY pt.created_at DESC
            LIMIT 20
        """)
        transactions = cur.fetchall()
        
        # Top utenti per portfolio
        cur.execute("""
            SELECT 
                u.id, u.nome as name, u.email,
                (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) as total_balance,
                COUNT(i.id) as active_investments
            FROM users u
            JOIN user_portfolios up ON up.user_id = u.id
            LEFT JOIN investments i ON i.user_id = u.id AND i.status = 'active'
            GROUP BY u.id, u.nome, u.email, up.free_capital, up.invested_capital, up.referral_bonus, up.profits
            ORDER BY total_balance DESC
            LIMIT 10
        """)
        top_users = cur.fetchall()
        
        # Timeline crescita (ultimi 30 giorni)
        cur.execute("""
            SELECT 
                DATE(pt.created_at) as date,
                SUM(CASE WHEN pt.amount > 0 THEN pt.amount ELSE 0 END) as daily_inflow,
                SUM(CASE WHEN pt.amount < 0 THEN ABS(pt.amount) ELSE 0 END) as daily_outflow
            FROM portfolio_transactions pt
            WHERE pt.created_at >= NOW() - INTERVAL '30 days'
            GROUP BY DATE(pt.created_at)
            ORDER BY date
        """)
        timeline_data = cur.fetchall()
        
        # Processa timeline per chart
        labels = []
        total_capital_timeline = []
        invested_capital_timeline = []
        
        running_total = 0
        running_invested = 0
        
        for day in timeline_data:
            labels.append(day['date'].strftime('%d/%m'))
            running_total += (day['daily_inflow'] - day['daily_outflow'])
            total_capital_timeline.append(running_total)
            invested_capital_timeline.append(running_invested)  # Simplified
        
        return {
            "overview": {
                "total_capital": total_capital,
                "free_capital": overview['total_free_capital'],
                "invested_capital": overview['total_invested_capital'],
                "bonus_total": overview['total_bonus'],
                "profits_total": overview['total_profits'],
                "total_users": overview['total_users'],
                "capital_change": 5.2,  # Mock data
                "bonus_users": 45,      # Mock data
                "average_roi": 8.5      # Mock data
            },
            "transactions": transactions,
            "topUsers": top_users,
            "timeline": {
                "labels": labels,
                "total_capital": total_capital_timeline,
                "invested_capital": invested_capital_timeline
            }
        }

@admin_bp.get("/portfolio/timeline")
@admin_required
def portfolio_timeline():
    """Timeline crescita portfolio per periodo specifico"""
    period = int(request.args.get('period', 30))
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                DATE(pt.created_at) as date,
                SUM(CASE WHEN pt.amount > 0 THEN pt.amount ELSE 0 END) as daily_inflow,
                SUM(CASE WHEN pt.amount < 0 THEN ABS(pt.amount) ELSE 0 END) as daily_outflow
            FROM portfolio_transactions pt
            WHERE pt.created_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(pt.created_at)
            ORDER BY date
        """, (period,))
        
        timeline_data = cur.fetchall()
        
        labels = []
        total_capital_timeline = []
        invested_capital_timeline = []
        
        for day in timeline_data:
            labels.append(day['date'].strftime('%d/%m'))
            total_capital_timeline.append(day['daily_inflow'] - day['daily_outflow'])
            invested_capital_timeline.append(day['daily_inflow'] * 0.7)  # Simplified
        
        return jsonify({
            "labels": labels,
            "total_capital": total_capital_timeline,
            "invested_capital": invested_capital_timeline
        })

@admin_bp.get("/projects/export")
@admin_required
def projects_export():
    """Esporta progetti in CSV"""
    format_type = request.args.get('format', 'csv')
    project_ids = request.args.get('ids')
    
    with get_conn() as conn, conn.cursor() as cur:
        if project_ids:
            # Esporta progetti selezionati
            ids = project_ids.split(',')
            placeholders = ','.join(['%s'] * len(ids))
            query = f"SELECT * FROM projects WHERE id IN ({placeholders}) ORDER BY created_at DESC"
            cur.execute(query, ids)
        else:
            # Esporta tutti i progetti
            cur.execute("SELECT * FROM projects ORDER BY created_at DESC")
        
        projects = cur.fetchall()
    
    if format_type == 'csv':
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow([
            'ID', 'Codice', 'Nome', 'Descrizione', 'Localit', 'Tipologia',
            'Importo Totale', 'Min Investment', 'RA', 'Stato',
            'Data Inizio', 'Data Fine', 'Data Creazione'
        ])
        
        # Dati progetti
        for project in projects:
            writer.writerow([
                project.get('id', ''),
                project.get('code', ''),
                project.get('name', ''),
                project.get('description', ''),
                project.get('location', ''),
                project.get('type', ''),
                project.get('total_amount', ''),
                project.get('min_investment', ''),
                project.get('roi', ''),
                project.get('status', ''),
                project.get('start_date', ''),
                project.get('created_at', '')
            ])
        
        output.seek(0)
        
        filename = f"progetti_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    
    return jsonify(projects)

# ---- KYC Management ----
@admin_bp.get("/kyc")
@admin_required
def kyc_dashboard():
    """Dashboard KYC admin"""
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(get_kyc_requests())
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    
    # Ottieni metriche utenti per il sidebar
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM users")
        users_total = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as active FROM users WHERE kyc_status = 'verified'")
        users_active = cur.fetchone()['active']
        
        cur.execute("SELECT COUNT(*) as verified FROM users WHERE kyc_status = 'verified'")
        users_verified = cur.fetchone()['verified']
        
        cur.execute("SELECT COUNT(*) as pending FROM users WHERE kyc_status = 'pending'")
        kyc_pending = cur.fetchone()['pending']
        
        cur.execute("SELECT COUNT(*) as suspended FROM users WHERE kyc_status = 'rejected'")
        users_suspended = cur.fetchone()['suspended']
    
    metrics = {
        'users_total': users_total,
        'users_active': users_active,
        'users_verified': users_verified,
        'kyc_pending': kyc_pending,
        'users_suspended': users_suspended,
        'total_users': users_total  # Per compatibilit con sidebar
    }
    
    return render_template("admin/kyc/dashboard.html", metrics=metrics)

@admin_bp.get("/api/kyc-requests")
@admin_required
def kyc_requests():
    """Lista richieste KYC"""
    return jsonify(get_kyc_requests())

@admin_bp.get("/api/kyc-requests/<int:user_id>")
@admin_required
def kyc_request_detail(user_id):
    """Dettaglio richiesta KYC specifica"""
    with get_conn() as conn, conn.cursor() as cur:
        # Dati utente
        cur.execute("""
            SELECT id, nome, email, telefono, address, kyc_status, 
                   created_at, kyc_notes
            FROM users WHERE id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            abort(404)
        
        # Documenti KYC
        cur.execute("""
            SELECT d.*, dc.name as category_name
            FROM documents d
            JOIN doc_categories dc ON dc.id = d.category_id
            WHERE d.user_id = %s AND dc.is_kyc = true
            ORDER BY d.uploaded_at DESC
        """, (user_id,))
        documents = cur.fetchall()
        
        # Portfolio info
        cur.execute("""
            SELECT 
                (free_capital + invested_capital + referral_bonus + profits) as total_balance,
                COUNT(i.id) as investments_count
            FROM user_portfolios up
            LEFT JOIN investments i ON i.user_id = up.user_id AND i.status = 'active'
            WHERE up.user_id = %s
            GROUP BY up.id, up.free_capital, up.invested_capital, up.referral_bonus, up.profits
        """, (user_id,))
        portfolio = cur.fetchone()
        
        return jsonify({
            **user,
            "documents": documents,
            "has_portfolio": bool(portfolio and portfolio['total_balance'] > 0),
            "investments_count": portfolio['investments_count'] if portfolio else 0
        })

@admin_bp.get("/api/kyc-stats")
@admin_required
def kyc_stats():
    """Statistiche KYC"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                kyc_status,
                COUNT(*) as count
            FROM users
            GROUP BY kyc_status
        """)
        stats_raw = cur.fetchall()
        
        stats = {
            'pending': 0,
            'verified': 0,
            'rejected': 0,
            'unverified': 0,
            'total': 0
        }
        
        for stat in stats_raw:
            stats[stat['kyc_status']] = stat['count']
            stats['total'] += stat['count']
        
        # Mock trend data
        stats['trend'] = 12.5  # +12.5% vs mese scorso
        
        return jsonify(stats)

def get_kyc_requests():
    """Helper per ottenere richieste KYC"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                u.id, u.nome, u.email, u.telefono, u.address,
                u.kyc_status, u.created_at, u.kyc_notes,
                COUNT(d.id) as documents_count,
                CASE WHEN up.id IS NOT NULL AND 
                     (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) > 0 
                     THEN true ELSE false END as has_portfolio
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            LEFT JOIN doc_categories dc ON dc.id = d.category_id AND dc.is_kyc = true
            LEFT JOIN user_portfolios up ON up.user_id = u.id
            WHERE u.role = 'investor'
            GROUP BY u.id, u.nome, u.email, u.telefono, u.address, 
                     u.kyc_status, u.created_at, u.kyc_notes, up.id,
                     up.free_capital, up.invested_capital, up.referral_bonus, up.profits
            ORDER BY 
                CASE u.kyc_status 
                    WHEN 'pending' THEN 1 
                    WHEN 'unverified' THEN 2
                    WHEN 'rejected' THEN 3
                    WHEN 'verified' THEN 4
                END,
                u.created_at DESC
        """)
        
        return cur.fetchall()

@admin_bp.post("/kyc/<int:user_id>/approve")
@admin_required
def kyc_approve(user_id):
    """Approva KYC utente"""
    data = request.json or {}
    notes = data.get('notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'verified', 
                kyc_notes = %s
            WHERE id = %s AND role = 'investor'
        """, (notes, user_id))
        
        if cur.rowcount == 0:
            return jsonify({"error": "Utente non trovato"}), 404
        
        # Log dell'azione admin
        cur.execute("""
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'kyc_approve', 'user', %s, %s)
        """, (session.get('user_id'), user_id, f"KYC approvato: {notes}"))
    
    return jsonify({"success": True, "message": "KYC approvato con successo"})

@admin_bp.post("/kyc/<int:user_id>/reject")
@admin_required
def kyc_reject(user_id):
    """Rifiuta KYC utente"""
    data = request.json or {}
    notes = data.get('notes', '')
    
    if not notes:
        return jsonify({"error": "Le note sono obbligatorie per il rifiuto"}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'rejected',
                kyc_notes = %s
            WHERE id = %s AND role = 'investor'
        """, (notes, user_id))
        
        if cur.rowcount == 0:
            return jsonify({"error": "Utente non trovato"}), 404
        
        # Log dell'azione admin
        cur.execute("""
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'kyc_reject', 'user', %s, %s)
        """, (session.get('user_id'), user_id, f"KYC rifiutato: {notes}"))
    
    return jsonify({"success": True, "message": "KYC rifiutato"})

@admin_bp.post("/kyc/bulk-action")
@admin_required
def kyc_bulk_action():
    """Azioni multiple su KYC"""
    data = request.json or {}
    action = data.get('action')
    request_ids = data.get('request_ids', [])
    
    if not action or not request_ids:
        return jsonify({"error": "Parametri mancanti"}), 400
    
    valid_actions = ['approve', 'reject', 'pending', 'export']
    if action not in valid_actions:
        return jsonify({"error": "Azione non valida"}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        if action == 'approve':
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'verified',
                    kyc_notes = 'Approvazione multipla'
                WHERE id = ANY(%s) AND role = 'investor'
            """, (request_ids,))
            
        elif action == 'reject':
            notes = data.get('notes', 'Rifiuto multiplo')
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'rejected',
                    kyc_notes = %s
                WHERE id = ANY(%s) AND role = 'investor'
            """, (notes, request_ids))
            
        elif action == 'pending':
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'pending',
                    kyc_notes = 'Rimesso in attesa'
                WHERE id = ANY(%s) AND role = 'investor'
            """, (request_ids,))
        
        elif action == 'export':
            # Per l'export, restituiamo i dati invece di modificarli
            placeholders = ','.join(['%s'] * len(request_ids))
            cur.execute(f"""
                SELECT id, nome, email, telefono, kyc_status, created_at
                FROM users 
                WHERE id IN ({placeholders}) AND role = 'investor'
                ORDER BY created_at DESC
            """, request_ids)
            
            users = cur.fetchall()
            return jsonify({"users": users, "action": "export"})
        
        
        # Log dell'azione admin
        if action != 'export':
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, %s, 'bulk_kyc', %s, %s)
            """, (session.get('user_id'), f'kyc_bulk_{action}', 0, f"Azione {action} su {len(request_ids)} utenti"))
    
    return jsonify({
        "success": True, 
        "message": f"Azione '{action}' completata su {len(request_ids)} utenti"
    })

@admin_bp.get("/kyc/export")
@admin_required
def kyc_export():
    """Esporta dati KYC in CSV"""
    format_type = request.args.get('format', 'csv')
    status = request.args.get('status')
    search = request.args.get('search')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Build query with filters
        where_conditions = ["u.role = 'investor'"]
        params = []
        
        if status:
            where_conditions.append("u.kyc_status = %s")
            params.append(status)
        
        if search:
            where_conditions.append("""
                (u.nome ILIKE %s OR u.email ILIKE %s OR u.telefono ILIKE %s)
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions)
        
        cur.execute(f"""
            SELECT 
                u.id, u.nome, u.email, u.telefono, u.address,
                u.kyc_status, u.created_at, u.kyc_notes,
                COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            LEFT JOIN doc_categories dc ON dc.id = d.category_id AND dc.is_kyc = true
            WHERE {where_clause}
            GROUP BY u.id, u.nome, u.email, u.telefono, u.address, 
                     u.kyc_status, u.created_at, u.kyc_notes
            ORDER BY u.created_at DESC
        """, params)
        
        kyc_requests = cur.fetchall()
    
    if format_type == 'csv':
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow([
            'ID', 'Nome Completo', 'Email', 'Telefono', 'Indirizzo',
            'Stato KYC', 'Data Registrazione', 'Note', 'Documenti'
        ])
        
        # Dati utenti
        for user in kyc_requests:
            writer.writerow([
                user.get('id', ''),
                user.get('nome', ''),
                user.get('email', ''),
                user.get('telefono', ''),
                user.get('address', ''),
                user.get('kyc_status', ''),
                user.get('created_at', ''),
                user.get('kyc_notes', ''),
                user.get('documents_count', 0)
            ])
        
        output.seek(0)
        
        filename = f"kyc_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    
    return jsonify(kyc_requests)

# ---- Gestione Utenti (pagina rimossa) ----

@admin_bp.get("/users/stats")
@admin_required
def users_stats():
    """Statistiche utenti"""
    with get_conn() as conn, conn.cursor() as cur:
        # Statistiche base
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE kyc_status = 'verified') as verified,
                COUNT(*) FILTER (WHERE kyc_status = 'pending') as pending,
                COUNT(*) FILTER (WHERE kyc_status = 'rejected') as rejected,
                COUNT(*) FILTER (WHERE kyc_status = 'rejected') as suspended,
                COUNT(*) FILTER (WHERE role = 'admin') as admins
            FROM users
        """)
        basic_stats = cur.fetchone()
        
        # Investitori attivi (con investimenti)
        cur.execute("""
            SELECT 
                COUNT(DISTINCT i.user_id) as active_investors,
                COALESCE(SUM(i.amount), 0) as total_investment_volume
            FROM investments i
            JOIN users u ON u.id = i.user_id
            WHERE i.status IN ('active', 'completed')
        """)
        investment_stats = cur.fetchone()
        
        # Crescita mensile (mock data)
        cur.execute("""
            SELECT 
                COUNT(*) as current_month_users
            FROM users
            WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE)
        """)
        current_month = cur.fetchone()
        
        cur.execute("""
            SELECT 
                COUNT(*) as previous_month_users
            FROM users
            WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
            AND created_at < DATE_TRUNC('month', CURRENT_DATE)
        """)
        previous_month = cur.fetchone()
        
        # Calcola crescita percentuale
        growth = 0
        if previous_month['previous_month_users'] > 0:
            growth = ((current_month['current_month_users'] - previous_month['previous_month_users']) / 
                     previous_month['previous_month_users']) * 100
        
        return jsonify({
            'total': basic_stats['total'],
            'verified': basic_stats['verified'],
            'pending': basic_stats['pending'],
            'rejected': basic_stats['rejected'],
            'suspended': basic_stats['suspended'],
            'admins': basic_stats['admins'],
            'active_investors': investment_stats['active_investors'],
            'investment_volume': float(investment_stats['total_investment_volume']),
            'growth': round(growth, 1)
        })

def get_users_list():
    """Helper per ottenere lista utenti con filtri"""
    kyc_status = request.args.get('kyc_status')
    role = request.args.get('role')
    investment_status = request.args.get('investment_status')
    date_range = request.args.get('date_range')
    search = request.args.get('search')
    sort = request.args.get('sort', 'created_at_desc')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Build WHERE conditions
        where_conditions = []
        params = []
        
        if kyc_status:
            where_conditions.append("u.kyc_status = %s")
            params.append(kyc_status)
        
        if role:
            where_conditions.append("u.role = %s")
            params.append(role)
        
        if search:
            where_conditions.append("""
                (u.nome ILIKE %s OR u.email ILIKE %s OR u.telefono ILIKE %s)
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Date range filter
        if date_range:
            if date_range == 'today':
                where_conditions.append("u.created_at >= CURRENT_DATE")
            elif date_range == 'week':
                where_conditions.append("u.created_at >= CURRENT_DATE - INTERVAL '7 days'")
            elif date_range == 'month':
                where_conditions.append("u.created_at >= CURRENT_DATE - INTERVAL '30 days'")
            elif date_range == 'quarter':
                where_conditions.append("u.created_at >= CURRENT_DATE - INTERVAL '90 days'")
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Build ORDER BY
        order_mapping = {
            'created_at_desc': 'u.created_at DESC',
            'created_at_asc': 'u.created_at ASC',
            'name_asc': 'u.nome ASC',
            'name_desc': 'u.nome DESC',
            'kyc_status': """
                CASE u.kyc_status 
                    WHEN 'verified' THEN 1 
                    WHEN 'pending' THEN 2
                    WHEN 'rejected' THEN 3
                    WHEN 'unverified' THEN 4
                END
            """,
            'investment_volume': 'COALESCE(portfolio_total, 0) DESC'
        }
        order_by = order_mapping.get(sort, 'u.created_at DESC')
        
        # Main query
        query = f"""
            SELECT 
                u.id, u.nome, u.email, u.telefono, u.address,
                u.kyc_status, u.role, u.created_at,
                up.free_capital + up.invested_capital + up.referral_bonus + up.profits as portfolio_balance,
                COALESCE(inv_stats.investments_count, 0) as investments_count,
                COALESCE(inv_stats.investment_volume, 0) as investment_volume,
                CASE WHEN inv_stats.investments_count > 0 THEN true ELSE false END as has_investments,
                up.referral_bonus,
                up.profits,
                (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) as portfolio_total
            FROM users u
            LEFT JOIN user_portfolios up ON up.user_id = u.id
            LEFT JOIN (
                SELECT 
                    user_id,
                    COUNT(*) as investments_count,
                    SUM(amount) as investment_volume
                FROM investments 
                WHERE status IN ('active', 'completed')
                GROUP BY user_id
            ) inv_stats ON inv_stats.user_id = u.id
            {where_clause}
            ORDER BY {order_by}
        """
        
        cur.execute(query, params)
        users = cur.fetchall()
        
        # Investment status filter (post-query because it's complex)
        if investment_status:
            if investment_status == 'with_investments':
                users = [u for u in users if u.get('has_investments')]
            elif investment_status == 'without_investments':
                users = [u for u in users if not u.get('has_investments')]
        
        return users

@admin_bp.get("/users/<int:user_id>")
@admin_required
def user_detail(user_id):
    """Dettaglio utente specifico"""
    with get_conn() as conn, conn.cursor() as cur:
        # Dati utente base
        cur.execute("""
            SELECT u.*, up.free_capital, up.invested_capital, up.referral_bonus, up.profits
            FROM users u
            LEFT JOIN user_portfolios up ON up.user_id = u.id
            WHERE u.id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            abort(404)
        
        # Portfolio balance
        portfolio_balance = (user.get('free_capital', 0) + user.get('invested_capital', 0) + 
                           user.get('referral_bonus', 0) + user.get('profits', 0))
        
        # Statistiche investimenti
        cur.execute("""
            SELECT 
                COUNT(*) as investments_count,
                COALESCE(SUM(amount), 0) as investment_volume
            FROM investments 
            WHERE user_id = %s AND status IN ('active', 'completed')
        """, (user_id,))
        investment_stats = cur.fetchone()
        
        # Documenti KYC
        cur.execute("""
            SELECT d.*, dc.name as category_name
            FROM documents d
            JOIN doc_categories dc ON dc.id = d.category_id
            WHERE d.user_id = %s AND dc.is_kyc = true
            ORDER BY d.uploaded_at DESC
        """, (user_id,))
        kyc_documents = cur.fetchall()
        
        # Attivit recente (mock data)
        cur.execute("""
            SELECT 'investment' as type, 'Nuovo investimento' as description, created_at
            FROM investments 
            WHERE user_id = %s
            ORDER BY created_at DESC 
            LIMIT 5
        """, (user_id,))
        recent_activity = cur.fetchall()
        
        return jsonify({
            **user,
            'portfolio_balance': float(portfolio_balance),
            'investments_count': investment_stats['investments_count'],
            'investment_volume': float(investment_stats['investment_volume']),
            'kyc_documents': kyc_documents,
            'recent_activity': recent_activity
        })

@admin_bp.post("/users/<int:user_id>/toggle-status")
@admin_required
def toggle_user_status(user_id):
    """Attiva/Sospendi utente"""
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni stato attuale
        cur.execute("SELECT kyc_status, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({"error": "Utente non trovato"}), 404
        
        # Non permettere di sospendere admin
        if user['role'] == 'admin':
            return jsonify({"error": "Non  possibile sospendere un amministratore"}), 400
        
        new_status = 'verified' if user['kyc_status'] == 'rejected' else 'rejected'
        
        cur.execute("""
            UPDATE users 
            SET kyc_status = %s
            WHERE id = %s
        """, (new_status, user_id))
        
        # Log dell'azione admin
        action = 'user_activate' if new_status == 'verified' else 'user_suspend'
        cur.execute("""
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, %s, 'user', %s, %s)
        """, (session.get('user_id'), action, user_id, f"Utente {'attivato' if new_status == 'verified' else 'sospeso'}"))
    
    return jsonify({
        "success": True, 
        "message": f"Utente {'attivato' if new_status == 'verified' else 'sospeso'} con successo",
        "new_status": new_status
    })

@admin_bp.post("/users/bulk-action")
@admin_required  
def users_bulk_action():
    """Azioni multiple su utenti"""
    data = request.json or {}
    action = data.get('action')
    user_ids = data.get('user_ids', [])
    
    if not action or not user_ids:
        return jsonify({"error": "Parametri mancanti"}), 400
    
    valid_actions = ['approve_kyc', 'reject_kyc', 'suspend', 'activate', 'export']
    if action not in valid_actions:
        return jsonify({"error": "Azione non valida"}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        if action == 'approve_kyc':
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'verified',
                    kyc_notes = 'Approvazione multipla'
                WHERE id = ANY(%s) AND role != 'admin'
            """, (user_ids,))
            
        elif action == 'reject_kyc':
            notes = data.get('notes', 'Rifiuto multiplo')
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'rejected',
                    kyc_notes = %s
                WHERE id = ANY(%s) AND role != 'admin'
            """, (notes, user_ids))
            
        elif action == 'suspend':
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'rejected'
                WHERE id = ANY(%s) AND role != 'admin'
            """, (user_ids,))
            
        elif action == 'activate':
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'verified'
                WHERE id = ANY(%s)
            """, (user_ids,))
        
        elif action == 'export':
            # Per l'export, restituiamo i dati invece di modificarli
            placeholders = ','.join(['%s'] * len(user_ids))
            cur.execute(f"""
                SELECT id, nome, email, telefono, kyc_status, created_at
                FROM users 
                WHERE id IN ({placeholders})
                ORDER BY created_at DESC
            """, user_ids)
            
            users = cur.fetchall()
            return jsonify({"users": users, "action": "export"})
        
        
        # Log dell'azione admin
        if action != 'export':
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, %s, 'bulk_users', %s, %s)
            """, (session.get('user_id'), f'users_bulk_{action}', 0, f"Azione {action} su {len(user_ids)} utenti"))
    
    return jsonify({
        "success": True, 
        "message": f"Azione '{action}' completata su {len(user_ids)} utenti"
    })

@admin_bp.get("/users/export")
@admin_required
def users_export():
    """Esporta dati utenti in CSV"""
    format_type = request.args.get('format', 'csv')
    
    # Usa la stessa logica di filtri della lista
    users = get_users_list()
    
    if format_type == 'csv':
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow([
            'ID', 'Nome Completo', 'Email', 'Telefono', 'Indirizzo',
            'Stato KYC', 'Ruolo', 'Portfolio Balance', 'Investimenti', 'Data Registrazione'
        ])
        
        # Dati utenti
        for user in users:
            writer.writerow([
                user.get('id', ''),
                user.get('nome', ''),
                user.get('email', ''),
                user.get('telefono', ''),
                user.get('address', ''),
                user.get('kyc_status', ''),
                user.get('role', ''),
                user.get('portfolio_balance', 0),
                user.get('investments_count', 0),
                user.get('created_at', '')
            ])
        
        output.seek(0)
        
        filename = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    
    return jsonify(users)

# =====================================================
# API Admin: Users Management (search, filters, detail, update)
# =====================================================

@admin_bp.get("/test-api")
def test_api():
    """Test API per debug."""
    return jsonify({"status": "ok", "message": "Test API funziona"})

@admin_bp.get("/test-users")
def test_users():
    """Test API utenti senza autenticazione per debug."""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.nome,
                    u.cognome,
                    u.telefono,
                    u.nome_telegram,
                    u.role,
                    u.kyc_status,
                    u.created_at,
                    u.address,
                    u.is_vip
                FROM users u
                WHERE u.role IN ('investor', 'user')
                ORDER BY u.created_at DESC
            """)
            users = cur.fetchall()
            
            # Converti in formato JSON
            users_list = []
            for u in users:
                users_list.append({
                    'id': u['id'],
                    'nome': u['nome'],
                    'cognome': u['cognome'],
                    'email': u['email'],
                    'phone': u['telefono'],
                    'telegram': u['nome_telegram'],
                    'investor_status': 'investor' if u['role'] == 'investor' else 'admin',
                    'kyc_status': u['kyc_status'],
                    'created_at': u['created_at'].isoformat() if u['created_at'] else None,
                    'address': u['address'],
                    'is_vip': u['is_vip']
                })
            
            return jsonify({
                "status": "ok",
                "users": users_list,
                "total": len(users_list)
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.get("/api/users")
def api_admin_users_list():
    """Lista utenti con ricerca e filtri per dashboard admin."""
    try:
        # Verifica autenticazione admin
        if not session.get('user_id'):
            return jsonify({"error": "Non autenticato"}), 401
        
        # Verifica ruolo admin
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT role FROM users WHERE id = %s", (session.get('user_id'),))
            user = cur.fetchone()
            if not user or user['role'] != 'admin':
                return jsonify({"error": "Accesso negato"}), 403
        
        # Query utenti
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    u.id,
                    u.email,
                    u.nome,
                    u.cognome,
                    u.telefono,
                    u.nome_telegram,
                    u.role,
                    u.kyc_status,
                    u.created_at,
                    u.address,
                    u.is_vip
                FROM users u
                WHERE u.role IN ('investor', 'user')
                ORDER BY u.created_at DESC
            """)
            users = cur.fetchall()
            
            # Converti in formato JSON
            users_list = []
            for u in users:
                users_list.append({
                    'id': u['id'],
                    'nome': u['nome'],
                    'cognome': u['cognome'],
                    'email': u['email'],
                    'phone': u['telefono'],
                    'telegram': u['nome_telegram'],
                    'investor_status': 'investor' if u['role'] == 'investor' else 'admin',
                    'kyc_status': u['kyc_status'],
                    'created_at': u['created_at'].isoformat() if u['created_at'] else None,
                    'address': u['address'],
                    'is_vip': u['is_vip']
                })
            
            return jsonify({
                "status": "ok",
                "users": users_list,
                "total": len(users_list)
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@admin_bp.get("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_user_detail(user_id: int):
    """Dettaglio utente per sidebar/modal admin."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT 
                u.id,
                u.email,
                u.telefono,
                u.nome,
                u.cognome,
                u.nome_telegram,
                u.role,
                u.kyc_status,
                u.created_at,
                u.address,
                u.is_vip
            FROM users u
            WHERE u.id = %s
            """,
            (user_id,)
        )
        u = cur.fetchone()
        if not u:
            return jsonify({'error': 'Utente non trovato'}), 404

    return jsonify({
        'id': u['id'],
        'name': f"{u['nome']} {u['cognome']}",
        'nome': u['nome'],
        'cognome': u['cognome'],
        'email': u['email'],
        'phone': u['telefono'],
        'telegram': u['nome_telegram'],
        'investor_status': 'investor' if u['role'] == 'investor' else 'admin',
        'kyc_status': u['kyc_status'],
        'created_at': u['created_at'].isoformat() if u['created_at'] else None,
        'address': u['address'],
        'is_vip': u['is_vip']
    })


@admin_bp.patch("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_user_update(user_id: int):
    """Aggiorna dati utente. Solo admin."""
    try:
        data = request.get_json() or {}

        allowed_fields = ['name', 'nome', 'cognome', 'email', 'phone', 'telegram', 'investor_status', 'kyc_status', 'address', 'is_vip']
        updates = {k: v for k, v in data.items() if k in allowed_fields}

        if not updates:
            return jsonify({'error': 'Nessun campo da aggiornare'}), 400

        # Split name in nome/cognome se presente
        nome = None
        cognome = None
        if 'name' in updates and updates['name']:
            parts = str(updates['name']).strip().split(' ', 1)
            nome = parts[0]
            cognome = parts[1] if len(parts) > 1 else ''
        # Se arrivano separati, sovrascrivono lo split
        if 'nome' in updates:
            nome = updates['nome']
        if 'cognome' in updates:
            cognome = updates['cognome']

        # Mappa investor_status a role
        role_value = None
        if 'investor_status' in updates:
            role_value = 'investor' if updates['investor_status'] in (True, 'si', 'investor', 'yes') else 'admin'

        # Assicurati che la tabella admin_actions esista prima della transazione
        with get_conn() as conn, conn.cursor() as cur:
            ensure_admin_actions_table(cur)
        
        with get_conn() as conn, conn.cursor() as cur:
            try:
                # Esiste utente?
                cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
                if not cur.fetchone():
                    return jsonify({'error': 'Utente non trovato'}), 404

                set_clauses = []
                params = []
                if nome is not None:
                    set_clauses.append('nome = %s')
                    params.append(nome)
                if cognome is not None:
                    set_clauses.append('cognome = %s')
                    params.append(cognome)
                if 'email' in updates:
                    set_clauses.append('email = %s')
                    params.append(updates['email'])
                if 'phone' in updates:
                    set_clauses.append('telefono = %s')
                    params.append(updates['phone'])
                if 'telegram' in updates:
                    set_clauses.append('nome_telegram = %s')
                    params.append(updates['telegram'])
                if 'kyc_status' in updates:
                    set_clauses.append('kyc_status = %s')
                    params.append(updates['kyc_status'])
                if role_value is not None:
                    set_clauses.append('role = %s')
                    params.append(role_value)
                if 'address' in updates:
                    set_clauses.append('address = %s')
                    params.append(updates['address'])
                if 'is_vip' in updates:
                    set_clauses.append('is_vip = %s')
                    params.append(bool(updates['is_vip']))

                if not set_clauses:
                    return jsonify({'error': 'Nessun campo valido da aggiornare'}), 400

                params.append(user_id)
                cur.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s", params)
                # Log azione
                cur.execute(
                    """
                    INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (session.get('user_id'), 'user_update', 'user', user_id, 'Aggiornati campi utente')
                )
                conn.commit()
            except Exception as db_error:
                conn.rollback()
                print(f"Errore database aggiornamento utente {user_id}: {db_error}")
                return jsonify({'error': f'Errore database: {str(db_error)}'}), 500

        return jsonify({'success': True, 'message': 'Utente aggiornato con successo'})
    
    except Exception as e:
        print(f"Errore aggiornamento utente {user_id}: {e}")
        return jsonify({'error': f'Errore durante l\'aggiornamento: {str(e)}'}), 500


@admin_bp.get("/api/admin/users/<int:user_id>/portfolio")
@admin_required
def api_admin_user_portfolio(user_id: int):
    """Dettagli portafoglio utente: bilanci e investimenti"""
    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        # Bilanci
        cur.execute(
            """
            SELECT 
                COALESCE(up.free_capital,0) AS free_capital,
                COALESCE(up.invested_capital,0) AS invested_capital,
                COALESCE(up.referral_bonus,0) AS referral_bonus,
                COALESCE(up.profits,0) AS profits
            FROM user_portfolios up
            WHERE up.user_id = %s
            """,
            (user_id,)
        )
        balances = cur.fetchone() or {
            'free_capital': 0,
            'invested_capital': 0,
            'referral_bonus': 0,
            'profits': 0,
        }

        # Investimenti con nome progetto, importo e stato
        cur.execute(
            """
            SELECT i.id, i.amount, i.status, i.created_at, p.title AS project_name
            FROM investments i
            LEFT JOIN projects p ON p.id = i.project_id
            WHERE i.user_id = %s
            ORDER BY i.created_at DESC
            """,
            (user_id,)
        )
        investments = cur.fetchall() or []

    total = float(balances.get('free_capital',0) + balances.get('invested_capital',0) + balances.get('referral_bonus',0) + balances.get('profits',0))

    return jsonify({
        'balances': {
            'free_capital': float(balances.get('free_capital',0)),
            'invested_capital': float(balances.get('invested_capital',0)),
            'referral_bonus': float(balances.get('referral_bonus',0)),
            'profits': float(balances.get('profits',0)),
            'total': total,
        },
        'investments': [
            {
                'id': inv['id'],
                'amount': float(inv['amount']),
                'status': inv['status'],
                'created_at': inv['created_at'].isoformat() if inv.get('created_at') else None,
                'project_name': inv.get('project_name')
            }
            for inv in investments
        ]
    })


@admin_bp.patch("/api/admin/users/<int:user_id>/portfolio")
@admin_required
def api_admin_update_portfolio(user_id: int):
    """Aggiorna i saldi del portafoglio utente (solo admin)."""
    try:
        data = request.get_json() or {}
        allowed = ['free_capital', 'invested_capital', 'referral_bonus', 'profits']
        updates = {k: float(data[k]) for k in allowed if k in data}
        if not updates:
            return jsonify({'error': 'Nessun campo da aggiornare'}), 400

        with get_conn() as conn, conn.cursor() as cur:
            ensure_admin_actions_table(cur)
            # Assicurati che la riga del portafoglio esista
            cur.execute("SELECT user_id FROM user_portfolios WHERE user_id = %s", (user_id,))
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
                    VALUES (%s, 0, 0, 0, 0)
                    """,
                    (user_id,)
                )

            set_parts = []
            params = []
            for field, value in updates.items():
                set_parts.append(f"{field} = %s")
                params.append(value)
            params.append(user_id)

            cur.execute(f"UPDATE user_portfolios SET {', '.join(set_parts)} WHERE user_id = %s", params)
            
            # Se è stato modificato invested_capital, sincronizza con la tabella investments
            if 'invested_capital' in updates:
                new_invested_capital = updates['invested_capital']
                
                # Ottieni il totale attuale degli investimenti attivi
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) as total_investments
                    FROM investments 
                    WHERE user_id = %s AND status = 'active'
                """, (user_id,))
                current_total = float(cur.fetchone()['total_investments'] or 0)
                
                # Calcola la differenza
                difference = new_invested_capital - current_total
                
                if difference != 0:
                    # Se c'è una differenza, aggiorna proporzionalmente tutti gli investimenti attivi
                    if current_total > 0:
                        # Aggiorna proporzionalmente ogni investimento
                        cur.execute("""
                            UPDATE investments 
                            SET amount = amount * (%s / %s)
                            WHERE user_id = %s AND status = 'active'
                        """, (new_invested_capital, current_total, user_id))
                    else:
                        # Se non ci sono investimenti attivi ma c'è capitale investito,
                        # crea un investimento virtuale per il primo progetto attivo
                        cur.execute("""
                            SELECT id FROM projects 
                            WHERE status = 'active' 
                            ORDER BY created_at ASC 
                            LIMIT 1
                        """)
                        first_project = cur.fetchone()
                        if first_project:
                            cur.execute("""
                                INSERT INTO investments (user_id, project_id, amount, status, created_at)
                                VALUES (%s, %s, %s, 'active', NOW())
                            """, (user_id, first_project['id'], new_invested_capital))
            
            cur.execute(
                """
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'portfolio_update', 'user', %s, %s)
                """,
                (session.get('user_id'), user_id, 'Aggiornati saldi portafoglio')
            )
            
            # Commit esplicito per assicurarsi che le modifiche vengano salvate
            conn.commit()

        return jsonify({'success': True, 'message': 'Portafoglio aggiornato'})
        
    except Exception as e:
        print(f"Errore nel salvataggio portafoglio: {str(e)}")
        return jsonify({'error': f'Errore nel salvataggio: {str(e)}'}), 500


@admin_bp.patch("/api/admin/users/<int:user_id>/portfolio/investments/<int:investment_id>")
@admin_required
def api_admin_update_investment(user_id: int, investment_id: int):
    """Aggiorna un investimento dell'utente (importo o stato)."""
    data = request.get_json() or {}
    allowed = ['amount', 'status']
    updates = {k: data[k] for k in allowed if k in data}
    if not updates:
        return jsonify({'error': 'Nessun campo da aggiornare'}), 400

    set_parts = []
    params = []
    if 'amount' in updates:
        set_parts.append('amount = %s')
        params.append(float(updates['amount']))
    if 'status' in updates:
        set_parts.append('status = %s')
        params.append(updates['status'])
    params.extend([investment_id, user_id])

    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        
        # Se stai modificando l'importo, aggiorna anche il progetto
        if 'amount' in updates:
            new_amount = float(updates['amount'])
            
            # Ottieni l'investimento attuale per calcolare la differenza
            cur.execute("""
                SELECT amount, project_id 
                FROM investments 
                WHERE id = %s AND user_id = %s
            """, (investment_id, user_id))
            investment = cur.fetchone()
            
            if investment:
                old_amount = float(investment['amount'])
                project_id = investment['project_id']
                difference = new_amount - old_amount
                
                # Aggiorna l'investimento
                cur.execute(
                    f"UPDATE investments SET {', '.join(set_parts)} WHERE id = %s AND user_id = %s",
                    params
                )
                
                # Aggiorna il funded_amount del progetto
                cur.execute("""
                    UPDATE projects 
                    SET funded_amount = funded_amount + %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (difference, project_id))
                
                # Aggiorna anche il portfolio dell'utente
                cur.execute("""
                    UPDATE user_portfolios 
                    SET invested_capital = invested_capital + %s,
                        updated_at = NOW()
                    WHERE user_id = %s
                """, (difference, user_id))
            else:
                return jsonify({'error': 'Investimento non trovato'}), 404
        else:
            # Se non stai modificando l'importo, aggiorna solo l'investimento
            cur.execute(
                f"UPDATE investments SET {', '.join(set_parts)} WHERE id = %s AND user_id = %s",
                params
            )
        
        cur.execute(
            """
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'investment_update', 'user', %s, %s)
            """,
            (session.get('user_id'), user_id, f'Aggiornamento investimento {investment_id}')
        )

    return jsonify({'success': True, 'message': 'Investimento aggiornato'})


@admin_bp.post("/api/admin/users/portfolio/bulk-adjust")
@admin_required
def api_admin_portfolio_bulk_adjust():
    """Aggiunge o rimuove un importo dalla sezione profits di pi utenti.
    Body: { user_ids: [int], op: 'add'|'remove', amount: number }
    """
    data = request.get_json() or {}
    user_ids = data.get('user_ids') or []
    op = data.get('op')
    amount = data.get('amount')

    if not user_ids or op not in ('add', 'remove'):
        return jsonify({'error': 'Parametri mancanti o non validi'}), 400
    try:
        amount = float(amount)
    except Exception:
        return jsonify({'error': 'Importo non valido'}), 400
    if amount <= 0:
        return jsonify({'error': 'L\'importo deve essere positivo'}), 400

    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        # Assicura che esistano le righe per ciascun utente
        for uid in user_ids:
            cur.execute("SELECT 1 FROM user_portfolios WHERE user_id = %s", (uid,))
            if not cur.fetchone():
                cur.execute(
                    "INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits) VALUES (%s, 0, 0, 0, 0)",
                    (uid,)
                )

        if op == 'remove':
            # Verifica sufficienza profitti per ciascun utente
            cur.execute(
                "SELECT user_id, profits FROM user_portfolios WHERE user_id = ANY(%s)",
                (user_ids,)
            )
            rows = cur.fetchall() or []
            insufficient = [r['user_id'] for r in rows if float(r['profits']) < amount]
            if insufficient:
                return jsonify({'error': 'Profitti insufficienti per alcuni utenti', 'user_ids': insufficient}), 400
            # Esegui sottrazione
            cur.execute(
                "UPDATE user_portfolios SET profits = profits - %s WHERE user_id = ANY(%s)",
                (amount, user_ids)
            )
        else:
            # Esegui addizione
            cur.execute(
                "UPDATE user_portfolios SET profits = profits + %s WHERE user_id = ANY(%s)",
                (amount, user_ids)
            )
        # Log azione
        cur.execute(
            """
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, %s, 'bulk_users', 0, %s)
            """,
            (session.get('user_id'), f'portfolio_{op}', f'Bulk {op} profits {amount} su {len(user_ids)} utenti')
        )
        # Log per-utente per tracciabilit dettagliata
        per_user_details = 'Aggiunta profitti' if op == 'add' else 'Rimozione profitti'
        for uid in user_ids:
            try:
                cur.execute(
                    """
                    INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                    VALUES (%s, %s, 'user', %s, %s)
                    """,
                    (
                        session.get('user_id'),
                        f'portfolio_{op}',
                        uid,
                        f"{per_user_details} {amount} EUR"
                    )
                )
            except Exception:
                pass

    return jsonify({'success': True})


@admin_bp.post("/api/admin/users/<int:user_id>/delete")
@admin_required
def api_admin_delete_user(user_id: int):
    """Elimina definitivamente un utente previa verifica password admin."""
    try:
        data = request.get_json() or {}
        admin_password = data.get('admin_password')
        if not admin_password:
            return jsonify({'error': 'Password admin richiesta'}), 400

        admin_id = session.get('user_id')
        if not admin_id:
            return jsonify({'error': 'Non autenticato'}), 401

        with get_conn() as conn, conn.cursor() as cur:
            # Verifica password admin
            cur.execute("SELECT password_hash, role FROM users WHERE id = %s", (admin_id,))
            admin_row = cur.fetchone()
            if not admin_row or admin_row.get('role') != 'admin':
                return jsonify({'error': 'Permesso negato'}), 403
            # Verifica password usando SHA-256 (come nel sistema di login)
            import hashlib
            if admin_row.get('password_hash') != hashlib.sha256(admin_password.encode()).hexdigest():
                return jsonify({'error': 'Password admin non corretta'}), 401

            # Non consentire eliminazione di un amministratore
            cur.execute("SELECT role FROM users WHERE id = %s", (user_id,))
            target = cur.fetchone()
            if not target:
                return jsonify({'error': 'Utente non trovato'}), 404
            if target.get('role') == 'admin':
                return jsonify({'error': 'Non è possibile eliminare un amministratore'}), 400

            # Prima di eliminare: fai "slittare" tutti gli invitati diretti al referrer del target
            cur.execute("SELECT referred_by FROM users WHERE id = %s", (user_id,))
            parent_row = cur.fetchone()
            parent_id = parent_row.get('referred_by') if parent_row else None

            if parent_id is not None:
                # Riassegna tutti gli utenti che avevano come referrer l'utente eliminato
                cur.execute(
                    """
                    UPDATE users
                    SET referred_by = %s
                    WHERE referred_by = %s
                    """,
                    (parent_id, user_id)
                )
            else:
                # Nessun referrer sopra: mantieni comportamento di orfanizzazione
                cur.execute(
                    """
                    UPDATE users
                    SET referred_by = NULL
                    WHERE referred_by = %s
                    """,
                    (user_id,)
                )

            # Elimina TUTTI i record correlati all'utente (cancellazione completa)
            # 1. Elimina transazioni e richieste
            cur.execute("DELETE FROM portfolio_transactions WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM deposit_requests WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM withdrawal_requests WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM investment_requests WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM kyc_requests WHERE user_id = %s", (user_id,))
            
            # 2. Elimina investimenti e portfolio
            cur.execute("DELETE FROM investments WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM user_portfolios WHERE user_id = %s", (user_id,))
            
            # 3. Elimina documenti e notifiche
            cur.execute("DELETE FROM documents WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM admin_notifications WHERE user_id = %s", (user_id,))
            
            # 4. Elimina codici referral
            cur.execute("DELETE FROM referral_codes WHERE user_id = %s", (user_id,))
            
            # 5. Aggiorna riferimenti in altre tabelle (set NULL per created_by, approved_by)
            cur.execute("UPDATE bank_configurations SET created_by = NULL WHERE created_by = %s", (user_id,))
            cur.execute("UPDATE wallet_configurations SET created_by = NULL WHERE created_by = %s", (user_id,))
            cur.execute("UPDATE deposit_requests SET approved_by = NULL WHERE approved_by = %s", (user_id,))
            cur.execute("UPDATE withdrawal_requests SET approved_by = NULL WHERE approved_by = %s", (user_id,))
            
            # 6. Infine elimina l'utente stesso
            cur.execute("DELETE FROM users WHERE id = %s", (user_id,))

        return jsonify({'success': True, 'message': 'Utente eliminato'})
    
    except Exception as e:
        logger.error(f"Errore eliminazione utente {user_id}: {e}")
        return jsonify({'error': f'Errore durante eliminazione: {str(e)}'}), 500


@admin_bp.post("/api/admin/users/<int:user_id>/reset-password")
@admin_required
def api_admin_reset_user_password(user_id: int):
    """Genera una nuova password temporanea per un utente previa verifica password admin."""
    try:
        data = request.get_json() or {}
        admin_password = data.get('admin_password')
        if not admin_password:
            return jsonify({'error': 'Password admin richiesta'}), 400

        admin_id = session.get('user_id')
        if not admin_id:
            return jsonify({'error': 'Non autenticato'}), 401

        # Verifiche preliminari FUORI dalla transazione
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica password admin
            cur.execute("SELECT password_hash, role FROM users WHERE id = %s", (admin_id,))
            admin_row = cur.fetchone()
            if not admin_row or admin_row.get('role') != 'admin':
                return jsonify({'error': 'Permesso negato'}), 403
            
            # Verifica password usando SHA-256 (come nel sistema di login)
            import hashlib
            if admin_row.get('password_hash') != hashlib.sha256(admin_password.encode()).hexdigest():
                return jsonify({'error': 'Password admin non corretta'}), 401

            # Verifica che l'utente esista
            cur.execute("SELECT id, email, role FROM users WHERE id = %s", (user_id,))
            target_user = cur.fetchone()
            if not target_user:
                return jsonify({'error': 'Utente non trovato'}), 404
            
            # Non consentire reset password di un amministratore
            if target_user.get('role') == 'admin':
                return jsonify({'error': 'Non è possibile resettare la password di un amministratore'}), 400

        # Verifica che la tabella admin_actions esista FUORI dalla transazione
        with get_conn() as conn, conn.cursor() as cur:
            ensure_admin_actions_table(cur)
        
        # Transazione separata per le modifiche
        with get_conn() as conn, conn.cursor() as cur:
            try:
                
                # Genera nuova password temporanea (8 caratteri alfanumerici)
                import secrets
                import string
                new_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(8))
                
                # Hash della nuova password con SHA-256
                new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                
                # Aggiorna la password nel database e marca come password temporanea
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, updated_at = NOW(), password_reset_required = true
                    WHERE id = %s
                """, (new_password_hash, user_id))
                
                # Log dell'azione admin
                cur.execute(
                    """
                    INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                    VALUES (%s, 'password_reset', 'user', %s, %s)
                    """,
                    (admin_id, user_id, f'Password resettata per utente {target_user.get("email")}')
                )
                
                # COMMIT DELLE MODIFICHE
                conn.commit()
                
                return jsonify({
                    'success': True, 
                    'message': 'Password generata con successo',
                    'new_password': new_password
                })
                
            except Exception as db_error:
                print(f"Errore database reset password utente {user_id}: {db_error}")
                conn.rollback()
                return jsonify({'error': f'Errore di connessione al database: {str(db_error)}'}), 500
        
    except Exception as e:
        print(f"Errore reset password utente {user_id}: {e}")
        return jsonify({'error': f'Errore interno del server: {str(e)}'}), 500


@admin_bp.get("/api/admin/users/<int:user_id>/history")
@admin_required
def api_admin_user_history(user_id: int):
    """Storico immutabile delle azioni admin su un utente."""
    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        cur.execute(
            """
            SELECT a.id, a.admin_id, a.action, a.target_type, a.target_id, a.details, a.created_at,
                   u.email as admin_email
            FROM admin_actions a
            LEFT JOIN users u ON u.id = a.admin_id
            WHERE a.target_type IN ('user','bulk_users') AND (a.target_id = %s OR a.target_id = 0)
              AND (a.details ILIKE %s OR a.action IN ('user_update','portfolio_update','investment_update','portfolio_add','portfolio_remove','user_delete'))
            ORDER BY a.created_at DESC
            """,
            (user_id, '%')
        )
        items = cur.fetchall() or []
    return jsonify({'items': items})


@admin_bp.get("/api/admin/users/history")
@admin_required
def api_admin_users_history():
    """Storico globale delle azioni su utenti (immutabile)."""
    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        cur.execute(
            """
            SELECT a.id, a.admin_id, a.action, a.target_type, a.target_id, a.details, a.created_at,
                   u.email as admin_email
            FROM admin_actions a
            LEFT JOIN users u ON u.id = a.admin_id
            WHERE a.target_type IN ('user','bulk_users')
            ORDER BY a.created_at DESC
            LIMIT 500
            """
        )
        items = cur.fetchall() or []
    return jsonify({'items': items})


## Endpoint rimosso: clear dello storico non pi disponibile

# ---- Analytics e Reporting ----
@admin_bp.get("/analytics")
@admin_required
def analytics_dashboard():
    """Dashboard analytics admin"""
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(get_analytics_data())
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    
    # Ottieni metriche utenti per il sidebar
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM users")
        users_total = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as active FROM users WHERE kyc_status = 'verified'")
        users_active = cur.fetchone()['active']
        
        cur.execute("SELECT COUNT(*) as verified FROM users WHERE kyc_status = 'verified'")
        users_verified = cur.fetchone()['verified']
        
        cur.execute("SELECT COUNT(*) as pending FROM users WHERE kyc_status = 'pending'")
        kyc_pending = cur.fetchone()['pending']
        
        cur.execute("SELECT COUNT(*) as suspended FROM users WHERE kyc_status = 'rejected'")
        users_suspended = cur.fetchone()['suspended']
    
    metrics = {
        'users_total': users_total,
        'users_active': users_active,
        'users_verified': users_verified,
        'kyc_pending': kyc_pending,
        'users_suspended': users_suspended,
        'total_users': users_total  # Per compatibilit con sidebar
    }
    
    return render_template("admin/analytics/dashboard.html", metrics=metrics)

@admin_bp.get("/analytics/data")
@admin_required
def analytics_data():
    """Dati analytics con filtri temporali"""
    return jsonify(get_analytics_data())

# =====================================================
# Admin page: Users management UI
# =====================================================

@admin_bp.get("/users")
def users_management_page():
    """Render della pagina Gestione Utenti"""
    # Controllo manuale se l'utente è admin
    from flask import session
    if 'user_id' not in session:
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))
    
    from backend.auth.middleware import is_admin
    if not is_admin():
        from flask import redirect, url_for, flash
        flash("Accesso negato. Solo gli amministratori possono accedere a questa pagina", "error")
        return redirect(url_for('user.dashboard'))
    
    return render_template("admin/users/list.html")

def get_analytics_data():
    """Helper per ottenere dati analytics"""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Calculate date range based on period
    from datetime import datetime, timedelta
    now = datetime.now()
    
    if start_date and end_date:
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        if period == 'today':
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = now
        elif period == 'week':
            start_dt = now - timedelta(days=7)
            end_dt = now
        elif period == 'month':
            start_dt = now - timedelta(days=30)
            end_dt = now
        elif period == 'quarter':
            start_dt = now - timedelta(days=90)
            end_dt = now
        elif period == 'year':
            start_dt = now - timedelta(days=365)
            end_dt = now
        else:  # all
            start_dt = datetime(2020, 1, 1)  # Platform start date
            end_dt = now
    
    with get_conn() as conn, conn.cursor() as cur:
        # KPI calculations
        kpis = calculate_kpis(cur, start_dt, end_dt, period)
        
        # Secondary metrics
        metrics = calculate_secondary_metrics(cur, start_dt, end_dt)
        
        # Chart data
        charts = generate_chart_data(cur, start_dt, end_dt, period)
        
        # Top projects
        top_projects = get_top_projects_performance(cur, start_dt, end_dt)
        
        # Conversion funnel
        funnel = calculate_conversion_funnel(cur, start_dt, end_dt)
        
        # Geographic data
        geographic = calculate_geographic_distribution(cur, start_dt, end_dt)
        
        return {
            'period': period,
            'start_date': start_dt.isoformat(),
            'end_date': end_dt.isoformat(),
            'kpis': kpis,
            'metrics': metrics,
            'charts': charts,
            'top_projects': top_projects,
            'funnel': funnel,
            'geographic': geographic
        }

def calculate_kpis(cur, start_dt, end_dt, period):
    """Calcola KPI principali"""
    # Total Revenue (mock calculation based on investments)
    cur.execute("""
        SELECT COALESCE(SUM(amount * 0.02), 0) as total_revenue
        FROM investments 
        WHERE created_at BETWEEN %s AND %s 
        AND status IN ('active', 'completed')
    """, (start_dt, end_dt))
    current_revenue = cur.fetchone()['total_revenue']
    
    # Previous period revenue for comparison  
    from datetime import timedelta
    if period == 'month':
        prev_start = start_dt - timedelta(days=30)
        prev_end = start_dt
    elif period == 'week':
        prev_start = start_dt - timedelta(days=7)
        prev_end = start_dt
    else:
        prev_start = start_dt - (end_dt - start_dt)
        prev_end = start_dt
    
    cur.execute("""
        SELECT COALESCE(SUM(amount * 0.02), 0) as prev_revenue
        FROM investments 
        WHERE created_at BETWEEN %s AND %s 
        AND status IN ('active', 'completed')
    """, (prev_start, prev_end))
    prev_revenue = cur.fetchone()['prev_revenue']
    
    revenue_change = ((current_revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0
    
    # New Users
    cur.execute("""
        SELECT COUNT(*) as new_users
        FROM users 
        WHERE created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    current_users = cur.fetchone()['new_users']
    
    cur.execute("""
        SELECT COUNT(*) as prev_users
        FROM users 
        WHERE created_at BETWEEN %s AND %s
    """, (prev_start, prev_end))
    prev_users = cur.fetchone()['prev_users']
    
    users_change = ((current_users - prev_users) / prev_users * 100) if prev_users > 0 else 0
    
    # Investment Volume
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as investment_volume
        FROM investments 
        WHERE created_at BETWEEN %s AND %s 
        AND status IN ('active', 'completed')
    """, (start_dt, end_dt))
    current_investment = cur.fetchone()['investment_volume']
    
    cur.execute("""
        SELECT COALESCE(SUM(amount), 0) as prev_investment
        FROM investments 
        WHERE created_at BETWEEN %s AND %s 
        AND status IN ('active', 'completed')
    """, (prev_start, prev_end))
    prev_investment = cur.fetchone()['prev_investment']
    
    investment_change = ((current_investment - prev_investment) / prev_investment * 100) if prev_investment > 0 else 0
    
    # Active Projects
    cur.execute("""
        SELECT COUNT(*) as active_projects
        FROM projects 
        WHERE status = 'active'
        AND created_at <= %s
    """, (end_dt,))
    active_projects = cur.fetchone()['active_projects']
    
    # Previous month active projects
    prev_month = end_dt - timedelta(days=30)
    cur.execute("""
        SELECT COUNT(*) as prev_active_projects
        FROM projects 
        WHERE status = 'active'
        AND created_at <= %s
    """, (prev_month,))
    prev_active_projects = cur.fetchone()['prev_active_projects']
    
    projects_change = active_projects - prev_active_projects
    
    return {
        'total_revenue': float(current_revenue),
        'revenue_change': revenue_change,
        'new_users': current_users,
        'users_change': users_change,
        'investment_volume': float(current_investment),
        'investment_change': investment_change,
        'active_projects': active_projects,
        'projects_change': projects_change
    }

def calculate_secondary_metrics(cur, start_dt, end_dt):
    """Calcola metriche secondarie"""
    # Conversion Rate (registered users who made investments)
    cur.execute("""
        SELECT 
            COUNT(DISTINCT u.id) as total_users,
            COUNT(DISTINCT i.user_id) as investing_users
        FROM users u
        LEFT JOIN investments i ON i.user_id = u.id AND i.status IN ('active', 'completed')
        WHERE u.created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    conversion_data = cur.fetchone()
    
    conversion_rate = (conversion_data['investing_users'] / conversion_data['total_users'] * 100) if conversion_data['total_users'] > 0 else 0
    
    # Average Investment
    cur.execute("""
        SELECT AVG(amount) as avg_investment
        FROM investments 
        WHERE created_at BETWEEN %s AND %s 
        AND status IN ('active', 'completed')
    """, (start_dt, end_dt))
    avg_investment = cur.fetchone()['avg_investment'] or 0
    
    # Average RA
    cur.execute("""
        SELECT AVG(roi) as avg_roi
        FROM projects 
        WHERE created_at BETWEEN %s AND %s
        AND roi IS NOT NULL
    """, (start_dt, end_dt))
    avg_roi = cur.fetchone()['avg_roi'] or 0
    
    # KYC Pending
    cur.execute("""
        SELECT COUNT(*) as kyc_pending
        FROM users 
        WHERE kyc_status = 'pending'
    """)
    kyc_pending = cur.fetchone()['kyc_pending']
    
    # Average KYC Approval Time (mock calculation - using created_at as approximation)
    cur.execute("""
        SELECT 
            AVG(EXTRACT(EPOCH FROM (updated_at - created_at)) / 86400) as avg_approval_days
        FROM users 
        WHERE kyc_status = 'verified' 
        AND updated_at IS NOT NULL
        AND created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    avg_approval_time = cur.fetchone()['avg_approval_days'] or 0
    
    # Retention Rate (users who logged in within 30 days of registration)
    cur.execute("""
        SELECT 
            COUNT(*) as total_users,
            0 as retained_users
        FROM users 
        WHERE created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    retention_data = cur.fetchone()
    
    retention_rate = (retention_data['retained_users'] / retention_data['total_users'] * 100) if retention_data['total_users'] > 0 else 0
    
    return {
        'conversion_rate': conversion_rate,
        'avg_investment': float(avg_investment),
        'avg_roi': float(avg_roi),
        'kyc_pending': kyc_pending,
        'avg_approval_time': avg_approval_time,
        'retention_rate': retention_rate
    }

def generate_chart_data(cur, start_dt, end_dt, period):
    """Genera dati per i grafici"""
    # Determine date grouping based on period
    if period in ['today', 'week']:
        date_trunc = 'day'
        date_format = 'DD/MM'
    elif period == 'month':
        date_trunc = 'day'
        date_format = 'DD/MM'
    elif period == 'quarter':
        date_trunc = 'week'
        date_format = 'DD/MM'
    else:
        date_trunc = 'month'
        date_format = 'MM/YYYY'
    
    # Users Growth Chart
    cur.execute(f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', created_at) as date,
            COUNT(*) as users_count
        FROM users 
        WHERE created_at BETWEEN %s AND %s
        GROUP BY DATE_TRUNC('{date_trunc}', created_at)
        ORDER BY date
    """, (start_dt, end_dt))
    users_growth_data = cur.fetchall()
    
    # Investment Volume Chart
    cur.execute(f"""
        SELECT 
            DATE_TRUNC('{date_trunc}', created_at) as date,
            COALESCE(SUM(amount), 0) as volume
        FROM investments 
        WHERE created_at BETWEEN %s AND %s
        AND status IN ('active', 'completed')
        GROUP BY DATE_TRUNC('{date_trunc}', created_at)
        ORDER BY date
    """, (start_dt, end_dt))
    investment_volume_data = cur.fetchall()
    
    # Projects Performance (top 10 projects by RA)
    cur.execute("""
        SELECT p.title, p.roi, 
               (SELECT COALESCE(SUM(amount), 0) FROM investments WHERE project_id = p.id) as volume,
               (SELECT COALESCE(SUM(amount), 0) FROM investments WHERE project_id = p.id) / p.total_amount * 100 as funding_percentage
        FROM projects p
        WHERE p.created_at BETWEEN %s AND %s
        AND p.roi IS NOT NULL
        ORDER BY p.roi DESC
        LIMIT 10
    """, (start_dt, end_dt))
    projects_performance = cur.fetchall()
    
    # Investment Distribution by Project Type
    cur.execute("""
        SELECT 
            p.type,
            COUNT(i.id) as investments_count,
            COALESCE(SUM(i.amount), 0) as total_amount
        FROM projects p
        LEFT JOIN investments i ON i.project_id = p.id AND i.status IN ('active', 'completed')
        WHERE p.created_at BETWEEN %s AND %s
        GROUP BY p.type
        ORDER BY total_amount DESC
    """, (start_dt, end_dt))
    investment_distribution = cur.fetchall()
    
    return {
        'users_growth': {
            'labels': [row['date'].strftime('%d/%m') for row in users_growth_data],
            'data': [row['users_count'] for row in users_growth_data]
        },
        'investment_volume': {
            'labels': [row['date'].strftime('%d/%m') for row in investment_volume_data],
            'data': [float(row['volume']) for row in investment_volume_data]
        },
        'projects_performance': {
            'labels': [row['name'][:20] + '...' if len(row['name']) > 20 else row['name'] for row in projects_performance],
            'roi_data': [float(row['roi']) for row in projects_performance],
            'volume_data': [float(row['volume']) for row in projects_performance],
            'funding_data': [float(row['funding_percentage']) for row in projects_performance]
        },
        'investment_distribution': {
            'labels': [row['type'] or 'Altro' for row in investment_distribution],
            'data': [float(row['total_amount']) for row in investment_distribution]
        },
        'revenue_breakdown': {
            'data': [65, 20, 10, 5]  # Mock data: Project commissions, Management fees, Referral commissions, Other
        },
        'user_segments': {
            'data': [40, 30, 20, 10]  # Mock data: Active investors, KYC verified, Pending KYC, Unverified
        },
        'monthly_trends': {
            'labels': ['Gen', 'Feb', 'Mar', 'Apr', 'Mag', 'Giu'],
            'revenue': [15000, 18000, 22000, 25000, 28000, 32000],
            'users': [120, 150, 180, 220, 260, 300]
        }
    }

def get_top_projects_performance(cur, start_dt, end_dt):
    """Ottiene top progetti per performance"""
    cur.execute("""
        SELECT 
            p.id, p.code, p.name, p.roi, p.status, p.total_amount,
            COALESCE(SUM(i.amount), 0) as volume,
            COUNT(DISTINCT i.user_id) as investors,
            COALESCE(SUM(i.amount), 0) / p.total_amount * 100 as funding_percentage
        FROM projects p
        LEFT JOIN investments i ON i.project_id = p.id AND i.status IN ('active', 'completed')
        WHERE p.created_at BETWEEN %s AND %s
        GROUP BY p.id, p.code, p.name, p.roi, p.status, p.total_amount
        ORDER BY p.roi DESC, volume DESC
        LIMIT 10
    """, (start_dt, end_dt))
    
    projects = cur.fetchall()
    
    return [
        {
            'id': project['id'],
            'code': project['code'],
            'name': project['name'],
            'roi': float(project['roi']) if project['roi'] else 0,
            'volume': float(project['volume']),
            'investors': project['investors'],
            'funding_percentage': float(project['funding_percentage']),
            'status': project['status']
        }
        for project in projects
    ]

def calculate_conversion_funnel(cur, start_dt, end_dt):
    """Calcola funnel di conversione"""
    # Visitors (mock data)
    visitors = 10000
    
    # Registrations
    cur.execute("""
        SELECT COUNT(*) as registrations
        FROM users 
        WHERE created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    registrations = cur.fetchone()['registrations']
    
    # KYC Completed
    cur.execute("""
        SELECT COUNT(*) as kyc_completed
        FROM users 
        WHERE kyc_status = 'verified'
        AND created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    kyc_completed = cur.fetchone()['kyc_completed']
    
    # First Investment
    cur.execute("""
        SELECT COUNT(DISTINCT user_id) as first_investors
        FROM investments 
        WHERE created_at BETWEEN %s AND %s
        AND status IN ('active', 'completed')
    """, (start_dt, end_dt))
    first_investors = cur.fetchone()['first_investors']
    
    return [
        { 'step': 'Visitatori', 'count': visitors, 'percentage': 100 },
        { 'step': 'Registrazioni', 'count': registrations, 'percentage': (registrations / visitors * 100) if visitors > 0 else 0 },
        { 'step': 'KYC Completato', 'count': kyc_completed, 'percentage': (kyc_completed / visitors * 100) if visitors > 0 else 0 },
        { 'step': 'Primo Investimento', 'count': first_investors, 'percentage': (first_investors / visitors * 100) if visitors > 0 else 0 }
    ]

def calculate_geographic_distribution(cur, start_dt, end_dt):
    """Calcola distribuzione geografica (mock data)"""
    return [
        { 'region': 'Nord Italia', 'percentage': 45, 'amount': 450000 },
        { 'region': 'Centro Italia', 'percentage': 30, 'amount': 300000 },
        { 'region': 'Sud Italia', 'percentage': 20, 'amount': 200000 },
        { 'region': 'Estero', 'percentage': 5, 'amount': 50000 }
    ]

@admin_bp.get("/analytics/export")
@admin_required
def analytics_export():
    """Esporta dati analytics"""
    format_type = request.args.get('format', 'csv')
    export_type = request.args.get('type', 'full')
    period = request.args.get('period', 'month')
    
    # Get analytics data
    analytics_data = get_analytics_data()
    
    if format_type == 'csv':
        return export_analytics_csv(analytics_data, export_type)
    elif format_type == 'excel':
        return export_analytics_excel(analytics_data)
    elif format_type == 'pdf':
        return export_analytics_pdf(analytics_data)
    elif format_type == 'json':
        return jsonify(analytics_data)
    
    return jsonify({'error': 'Formato non supportato'}), 400

def export_analytics_csv(analytics_data, export_type):
    """Esporta analytics in CSV"""
    import csv
    from io import StringIO
    from flask import Response
    
    output = StringIO()
    writer = csv.writer(output)
    
    if export_type == 'projects_performance':
        # Export top projects data
        writer.writerow(['Codice', 'Titolo', 'RA %', 'Volume ', 'Investitori', 'Finanziamento %', 'Stato'])
        
        for project in analytics_data.get('top_projects', []):
            writer.writerow([
                project['code'],
                project['title'],
                project['roi'],
                project['volume'],
                project['investors'],
                project['funding_percentage'],
                project['status']
            ])
    else:
        # Export full analytics data
        writer.writerow(['Metrica', 'Valore', 'Variazione %'])
        
        kpis = analytics_data.get('kpis', {})
        writer.writerow(['Revenue Totale', f"{kpis.get('total_revenue', 0):,.2f}", f"{kpis.get('revenue_change', 0):.1f}%"])
        writer.writerow(['Nuovi Utenti', kpis.get('new_users', 0), f"{kpis.get('users_change', 0):.1f}%"])
        writer.writerow(['Volume Investimenti', f"{kpis.get('investment_volume', 0):,.2f}", f"{kpis.get('investment_change', 0):.1f}%"])
        writer.writerow(['Progetti Attivi', kpis.get('active_projects', 0), kpis.get('projects_change', 0)])
        
        writer.writerow([])  # Empty row
        writer.writerow(['Metriche Secondarie', 'Valore', ''])
        
        metrics = analytics_data.get('metrics', {})
        writer.writerow(['Tasso Conversione', f"{metrics.get('conversion_rate', 0):.1f}%", ''])
        writer.writerow(['Investimento Medio', f"{metrics.get('avg_investment', 0):,.2f}", ''])
        writer.writerow(['RA Medio', f"{metrics.get('avg_roi', 0):.1f}%", ''])
        writer.writerow(['KYC Pendenti', metrics.get('kyc_pending', 0), ''])
        writer.writerow(['Tempo Approvazione Medio', f"{metrics.get('avg_approval_time', 0):.1f} giorni", ''])
        writer.writerow(['Retention Rate', f"{metrics.get('retention_rate', 0):.1f}%", ''])
    
    output.seek(0)
    
    filename = f"analytics_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

def export_analytics_excel(analytics_data):
    """Esporta analytics in Excel (placeholder)"""
    # TODO: Implement Excel export using openpyxl
    return jsonify({'message': 'Export Excel in sviluppo'}), 501

def export_analytics_pdf(analytics_data):
    """Esporta analytics in PDF (placeholder)"""
    # TODO: Implement PDF export using reportlab
    return jsonify({'message': 'Export PDF in sviluppo'}), 501






# ---- Configurazione Sistema ----
@admin_bp.get("/config")
@admin_required
def config_dashboard():
    """Dashboard configurazione sistema"""
    from flask import render_template
    
    # Ottieni metriche utenti per il sidebar
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM users")
        users_total = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as active FROM users WHERE kyc_status = 'verified'")
        users_active = cur.fetchone()['active']
        
        cur.execute("SELECT COUNT(*) as verified FROM users WHERE kyc_status = 'verified'")
        users_verified = cur.fetchone()['verified']
        
        cur.execute("SELECT COUNT(*) as pending FROM users WHERE kyc_status = 'pending'")
        kyc_pending = cur.fetchone()['pending']
        
        cur.execute("SELECT COUNT(*) as suspended FROM users WHERE kyc_status = 'rejected'")
        users_suspended = cur.fetchone()['suspended']
    
    metrics = {
        'users_total': users_total,
        'users_active': users_active,
        'users_verified': users_verified,
        'kyc_pending': kyc_pending,
        'users_suspended': users_suspended,
        'total_users': users_total  # Per compatibilit con sidebar
    }
    
    return render_template("admin/config/dashboard.html", metrics=metrics)

@admin_bp.get("/config/data")
@admin_required
def config_data():
    """Ottieni dati configurazione"""
    with get_conn() as conn, conn.cursor() as cur:
        # Configurazione bonifici
        cur.execute("""
            SELECT bank_name, account_holder, iban, bic_swift, payment_reference, created_at, updated_at
            FROM bank_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        bank_config = cur.fetchone()
        
        # Configurazione wallet USDT
        try:
            cur.execute("""
                SELECT wallet_name, wallet_address, network, created_at, updated_at
            FROM wallet_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
            wallet_config = cur.fetchone()
        except:
            # Se la tabella non esiste ancora, usa valori di default
            wallet_config = {
                'wallet_name': 'Wallet USDT',
                'wallet_address': 'Non configurato',
                'network': 'BEP20',
                'created_at': None,
                'updated_at': None
            }
        
        # Configurazioni generali
        cur.execute("""
            SELECT config_key, config_value, config_type 
            FROM system_configurations 
            WHERE is_active = true
        """)
        system_configs = cur.fetchall()
        
        # Organizza le configurazioni generali
        general_configs = {}
        for config in system_configs:
            key = config['config_key']
            value = config['config_value']
            config_type = config['config_type']
            
            # Converti il valore nel tipo corretto
            if config_type == 'number':
                try:
                    value = float(value) if '.' in value else int(value)
                except ValueError:
                    value = 0
            elif config_type == 'boolean':
                value = value.lower() == 'true' or value == '1'
            
            general_configs[key] = value
        
        return jsonify({
            'bank_config': bank_config,
            'wallet_config': wallet_config,
            'general_configs': general_configs
        })

@admin_bp.post("/config/bank")
@admin_required
def config_bank_save():
    """Salva configurazione bonifici"""
    data = request.json or {}
    
    # Tutti i campi sono ora opzionali
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            # Disattiva tutte le configurazioni precedenti
            cur.execute("UPDATE bank_configurations SET is_active = false")
            
            # Inserisci nuova configurazione
            cur.execute("""
                INSERT INTO bank_configurations 
                (bank_name, account_holder, iban, bic_swift, payment_reference, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                data.get('bank_name', ''),
                data.get('account_holder', ''),
                data.get('iban', ''),
                data.get('bic_swift', ''),
                data.get('payment_reference', ''),
                session.get('user_id')
            ))
            
            # Log dell'azione admin
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'config_update', 'bank', %s, %s)
            """, (session.get('user_id'), 0, f"Aggiornata configurazione bonifici: {data['bank_name']}"))
            
            conn.commit()
            return jsonify({"success": True, "message": "Configurazione bonifici salvata"})
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Errore nel salvataggio: {str(e)}"}), 500
    
@admin_bp.get("/wallet")
@admin_required
def wallet_dashboard():
    """Dashboard Wallet CIP"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Configurazione wallet
            try:
                cur.execute("""
                    SELECT wallet_name, wallet_address, network, created_at, updated_at
                    FROM wallet_configurations 
                    WHERE is_active = true 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """)
                wallet_config = cur.fetchone()
                if not wallet_config:
                    wallet_config = {
                        'wallet_name': 'Wallet USDT',
                        'wallet_address': 'Non configurato',
                        'network': 'BEP20',
                        'created_at': None,
                        'updated_at': None
                    }
            except:
                wallet_config = {
                    'wallet_name': 'Wallet USDT',
                    'wallet_address': 'Non configurato',
                    'network': 'BEP20',
        'created_at': None,
        'updated_at': None
    }
    
            # Statistiche wallet reali
            cur.execute("""
                SELECT 
                    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending_deposits,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_deposits,
                    COALESCE(SUM(CASE WHEN status = 'completed' THEN amount ELSE 0 END), 0) as total_deposits_amount
                FROM deposit_requests
            """)
            stats_data = cur.fetchone()
            
            # Calcola bilancio totale dai portafogli utenti
            cur.execute("""
                SELECT 
                    COALESCE(SUM(free_capital + invested_capital + referral_bonus + profits), 0) as total_balance
                FROM user_portfolios
            """)
            balance_data = cur.fetchone()
            
            wallet_stats = {
                'total_balance': float(balance_data['total_balance'] or 0),
                'pending_deposits': stats_data['pending_deposits'] or 0,
                'completed_deposits': stats_data['completed_deposits'] or 0,
                'total_deposits_amount': float(stats_data['total_deposits_amount'] or 0)
            }
            
    except Exception as e:
        print(f"Errore wallet dashboard: {e}")
        wallet_config = {
            'wallet_name': 'Wallet USDT',
            'wallet_address': 'Non configurato',
            'network': 'BEP20',
            'created_at': None,
            'updated_at': None
        }
    wallet_stats = {
        'total_balance': 0.0,
        'pending_deposits': 0,
        'completed_deposits': 0,
        'total_deposits_amount': 0.0
    }
    
    return render_template('admin/wallet/dashboard.html', 
                         wallet_config=wallet_config, 
                         wallet_stats=wallet_stats)

@admin_bp.post("/config/wallet")
@admin_required
def config_wallet_save():
    """Salva configurazione wallet USDT"""
    data = request.json or {}
    
    required_fields = ['wallet_address']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"Campo {field} richiesto"}), 400
    
    # Validazione indirizzo wallet
    try:
        from backend.shared.validators import validate_wallet_address, validate_wallet_network
        network = validate_wallet_network(data.get('network', 'BEP20'))
        wallet_address = validate_wallet_address(data.get('wallet_address'), network)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            # Disattiva tutte le configurazioni precedenti
            cur.execute("UPDATE wallet_configurations SET is_active = false")
            
            # Inserisci nuova configurazione
            cur.execute("""
                INSERT INTO wallet_configurations 
                (wallet_name, wallet_address, network, created_by)
                VALUES (%s, %s, %s, %s)
            """, (
                f"Wallet {network}",
                wallet_address,
                network,
                session.get('user_id')
            ))
            
            # Log dell'azione admin
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'config_update', 'wallet', %s, %s)
            """, (session.get('user_id'), 0, f"Aggiornata configurazione wallet: {wallet_address} ({network})"))
            
            conn.commit()
            return jsonify({"success": True, "message": "Configurazione wallet salvata"})
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Errore nel salvataggio: {str(e)}"}), 500

@admin_bp.post("/config/general")
@admin_required
def config_general_save():
    """Salva configurazioni generali"""
    data = request.json or {}
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            for key, value in data.items():
                # Determina il tipo di valore
                if isinstance(value, bool):
                    value_type = 'boolean'
                    value_str = str(value).lower()
                elif isinstance(value, (int, float)):
                    value_type = 'number'
                    value_str = str(value)
                else:
                    value_type = 'string'
                    value_str = str(value)
                
                # Inserisci o aggiorna la configurazione
                cur.execute("""
                    INSERT INTO system_configurations 
                    (config_key, config_value, config_type, updated_by)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (config_key) 
                    DO UPDATE SET 
                        config_value = EXCLUDED.config_value,
                        config_type = EXCLUDED.config_type,
                        updated_by = EXCLUDED.updated_by,
                        updated_at = CURRENT_TIMESTAMP
                """, (key, value_str, value_type, session.get('user_id')))
            
            # Log dell'azione admin
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'config_update', 'general', %s, %s)
            """, (session.get('user_id'), 0, f"Aggiornate configurazioni generali: {', '.join(data.keys())}"))
            
            conn.commit()
            return jsonify({"success": True, "message": "Configurazioni generali salvate"})
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Errore nel salvataggio: {str(e)}"}), 500

# ---- Performance Monitoring ----
@admin_bp.post("/performance/report")
@admin_required
def performance_report():
    """Riceve report di performance dal frontend"""
    data = request.json or {}
    
    try:
        # Log del report di performance
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO performance_reports (
                    url, user_agent, viewport_width, viewport_height,
                    page_load_time, dom_ready_time, lcp, cls, fid,
                    error_count, warning_count, overall_score, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
                data.get('url'),
                data.get('userAgent'),
                data.get('viewport', {}).get('width'),
                data.get('viewport', {}).get('height'),
                data.get('performance', {}).get('pageLoad'),
                data.get('performance', {}).get('domReady'),
                data.get('performance', {}).get('largestContentfulPaint'),
                data.get('performance', {}).get('cumulativeLayoutShift'),
                data.get('performance', {}).get('firstInputDelay'),
                data.get('quality', {}).get('errors', 0),
                data.get('quality', {}).get('warnings', 0),
                data.get('scores', {}).get('overall', 0)
            ))
    except Exception as e:
        # Se la tabella non esiste, logga solo in console
        print(f"Performance report: {data.get('scores', {}).get('overall', 0)}/100 for {data.get('url')}")
    
    return jsonify({"success": True, "message": "Performance report received"})

def users_list():
    q = request.args.get('q')
    where = ""
    params = []
    if q:
        where = "WHERE email ILIKE %s OR nome ILIKE %s"
        params = [f"%{q}%", f"%{q}%"]
    sql = f"SELECT id, email, nome, role, kyc_status, currency_code FROM users {where} ORDER BY id"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify(rows)

@admin_bp.get("/users/<int:uid>")
@admin_required
def user_detail_legacy(uid):
    """Dettaglio utente legacy - mantenuto per compatibilit"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,email,nome,phone,address,role,kyc_status,currency_code,referral_code,referred_by FROM users WHERE id=%s", (uid,))
        u = cur.fetchone()
        cur.execute("""
            SELECT i.id, p.title, i.amount, i.status, i.created_at
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.user_id=%s ORDER BY i.created_at DESC
        """, (uid,))
        inv = cur.fetchall()
        cur.execute("SELECT SUM(amount) AS total_bonus FROM referral_bonuses WHERE receiver_user_id=%s", (uid,))
        bonus = cur.fetchone()
        # rete referral tabellare
        cur.execute("""
            WITH RECURSIVE tree AS (
              SELECT id, referred_by, 1 AS level FROM users WHERE referred_by = %s
              UNION ALL
              SELECT u.id, u.referred_by, t.level+1 FROM users u
              JOIN tree t ON u.referred_by = t.id
            ) SELECT * FROM tree ORDER BY level
        """, (uid,))
        net = cur.fetchall()
    return jsonify({"user": u, "investments": inv, "bonus_total": (bonus and bonus['total_bonus'] or 0), "network": net})

@admin_bp.post("/users/<int:uid>/referrer")
@admin_required
def user_change_referrer(uid):
    data = request.form or request.json or {}
    referred_by = data.get('referred_by')
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET referred_by=%s WHERE id=%s", (referred_by, uid))
    return jsonify({"ok": True})

@admin_bp.route("/users/<int:uid>/bonuses", methods=['GET', 'POST'])
@admin_required
def user_bonuses(uid):
    if request.method == 'GET':
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM referral_bonuses WHERE receiver_user_id=%s ORDER BY month_ref DESC", (uid,))
            rows = cur.fetchall()
        return jsonify(rows)
    data = request.form or request.json or {}
    amount = data.get('amount'); level = data.get('level', 1); month_ref = data.get('month_ref')
    if not amount or not month_ref:
        abort(400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO referral_bonuses(receiver_user_id, source_user_id, investment_id, level, amount, month_ref, status)
            VALUES (%s,%s,%s,%s,%s,%s,'accrued') RETURNING id
        """, (uid, data.get('source_user_id'), data.get('investment_id'), level, amount, month_ref))
        rid = cur.fetchone()['id']
    return jsonify({"id": rid})

# ---- Gestione Investimenti ----
@admin_bp.get("/investments")
@admin_required
def investments_list():
    status = request.args.get('status')
    user_id = request.args.get('user_id')
    project_id = request.args.get('project_id')
    q = []; params = []
    if status: q.append("i.status=%s"); params.append(status)
    if user_id: q.append("i.user_id=%s"); params.append(user_id)
    if project_id: q.append("i.project_id=%s"); params.append(project_id)
    where = ("WHERE "+" AND ".join(q)) if q else ""
    sql = f"""
        SELECT i.id, u.nome, p.title, i.amount, i.status, i.created_at
        FROM investments i
        JOIN users u ON u.id=i.user_id
        JOIN projects p ON p.id=i.project_id
        {where}
        ORDER BY i.created_at DESC
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify(rows)

@admin_bp.get("/investments/<int:iid>")
@admin_required
def investment_detail(iid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.*, u.nome, p.title AS project_title
            FROM investments i
            JOIN users u ON u.id=i.user_id
            JOIN projects p ON p.id=i.project_id
            WHERE i.id=%s
        """, (iid,))
        inv = cur.fetchone()
        cur.execute("SELECT * FROM investment_yields WHERE investment_id=%s ORDER BY period_end DESC", (iid,))
        yields = cur.fetchall()
    return jsonify({"investment": inv, "yields": yields})

@admin_bp.post("/investments/<int:iid>/confirm_wire")
@admin_required
def investment_confirm_wire(iid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE investments SET status='active' WHERE id=%s", (iid,))
    return jsonify({"status": "active"})

@admin_bp.post("/investments/<int:iid>/yield")
@admin_required
def investment_add_yield(iid):
    data = request.form or request.json or {}
    amount = data.get('amount'); period_start = data.get('period_start'); period_end = data.get('period_end')
    if not amount or not period_start or not period_end:
        abort(400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO investment_yields(investment_id, period_start, period_end, amount)
            VALUES (%s,%s,%s,%s) RETURNING id
        """, (iid, period_start, period_end, amount))
        yid = cur.fetchone()['id']
    return jsonify({"id": yid})

# ---- Gestione Richieste ----
@admin_bp.get("/requests")
@admin_required
def requests_queue():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.id, u.nome, p.title AS project, r.amount, r.state, r.created_at
            FROM investment_requests r
            JOIN users u ON u.id=r.user_id
            JOIN projects p ON p.id=r.project_id
            WHERE r.state='in_review' ORDER BY r.created_at ASC
        """)
        rows = cur.fetchall()
    return jsonify(rows)

@admin_bp.post("/requests/<int:rid>/approve")
@admin_required
def requests_approve(rid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE investment_requests SET state='approved', updated_at=NOW() WHERE id=%s", (rid,))
        cur.execute(
            """
            INSERT INTO investments(user_id, project_id, amount, status)
            SELECT user_id, project_id, amount, 'approved' FROM investment_requests WHERE id=%s
            RETURNING id
            """, (rid,)
        )
        inv_id = cur.fetchone()['id']
    return jsonify({"approved_request": rid, "investment_id": inv_id})

@admin_bp.post("/requests/<int:rid>/reject")
@admin_required
def requests_reject(rid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE investment_requests SET state='rejected', updated_at=NOW() WHERE id=%s", (rid,))
    return jsonify({"rejected_request": rid})

# ---- KYC ----
@admin_bp.post("/kyc/<int:uid>/verify")
@admin_required
def kyc_verify(uid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET kyc_status='verified' WHERE id=%s", (uid,))
    return jsonify({"kyc_status": "verified"})

@admin_bp.post("/kyc/<int:uid>/reject")
@admin_required
def kyc_reject_legacy(uid):
    """KYC reject legacy - mantenuto per compatibilit"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET kyc_status='rejected' WHERE id=%s", (uid,))
    return jsonify({"kyc_status": "rejected"})

# ---- Documenti (admin) ----
@admin_bp.get("/documents")
@admin_required
def admin_documents():
    user_id = request.args.get('user_id')
    visibility = request.args.get('visibility')
    q = []; params = []
    if user_id: q.append("user_id=%s"); params.append(user_id)
    if visibility: q.append("visibility=%s"); params.append(visibility)
    where = ("WHERE "+" AND ".join(q)) if q else ""
    sql = f"SELECT * FROM documents {where} ORDER BY uploaded_at DESC"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify(rows)

@admin_bp.post("/documents/upload")
@admin_required
def admin_documents_upload():
    user_id = request.form.get('user_id')
    category_id = request.form.get('category_id')
    title = request.form.get('title')
    file = request.files.get('file')
    if not (user_id and category_id and file):
        abort(400)
    filename = secure_filename(file.filename)
    path = os.path.join(get_upload_folder(), f"{uuid.uuid4()}-{filename}")
    file.save(path)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documents(user_id, category_id, title, file_path, visibility)
            VALUES (%s,%s,%s,%s,%s) RETURNING id
        """, (user_id, category_id, title or filename, path, request.form.get('visibility','admin')))
        did = cur.fetchone()['id']
    return jsonify({"id": did, "file_path": path})

@admin_bp.post("/documents/<int:doc_id>/visibility")
@admin_required
def admin_documents_visibility(doc_id):
    visibility = request.form.get('visibility', 'private')
    verified = request.form.get('verified_by_admin')
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE documents SET visibility=%s, verified_by_admin=COALESCE(%s, verified_by_admin) WHERE id=%s",
                    (visibility, True if verified in ('1','true','True') else None, doc_id))
    return jsonify({"updated": True})


# ---- Analytics Legacy ----
@admin_bp.get("/analytics/legacy")
@admin_required
def analytics_legacy():
    """Analytics legacy - mantenuto per compatibilit"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT date_trunc('month', created_at) AS month, SUM(amount) AS invested
            FROM investments GROUP BY 1 ORDER BY 1 DESC
        """)
        inv_month = cur.fetchall()
        cur.execute("""
            SELECT date_trunc('month', created_at) AS month, COUNT(*) AS new_users
            FROM users GROUP BY 1 ORDER BY 1 DESC
        """)
        users_month = cur.fetchall()
        cur.execute("""
            SELECT month_ref AS month, SUM(amount) AS bonuses
            FROM referral_bonuses GROUP BY 1 ORDER BY 1 DESC
        """)
        bonus_month = cur.fetchall()
    return jsonify({"investments": inv_month, "users": users_month, "bonuses": bonus_month})

# ---- TASK 2.7 - Gestione Ricariche ----
@admin_bp.get("/deposits")
@admin_required
def deposits_dashboard():
    """Pagina Depositi con statistiche di default."""
    # Statistiche di default (tabelle non implementate)
    deposits_stats = {
        'total_deposits': 0,
        'total_deposit_amount': 0.0,
        'completed_deposits': 0,
        'completed_deposit_amount': 0.0,
        'pending_deposits': 0,
        'rejected_deposits': 0
    }
    return render_template('admin/deposits/dashboard.html', deposits_stats=deposits_stats)

@admin_bp.get("/api/deposits/metrics")
@admin_required
def deposits_api_metrics():
    """API per statistiche depositi"""
    logger.info(f"deposits_api_metrics called - session: {dict(session)}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Conta depositi per stato
            cur.execute("SELECT status, COUNT(*), COALESCE(SUM(amount), 0) FROM deposit_requests GROUP BY status")
            results = cur.fetchall()
            logger.info(f"Deposits metrics query results: {results}")
            
            metrics = {
                'pending': 0,
                'completed': 0,
                'rejected': 0,
                'total_amount': 0.0
            }
            
            for row in results:
                status = row['status']
                count = row['count']
                total_amount = row['coalesce']  # Il nome della colonna è 'coalesce'
                logger.info(f"Processing status: {status}, count: {count}, total: {total_amount}")
                if status == 'pending':
                    metrics['pending'] = count
                elif status == 'completed':
                    metrics['completed'] = count
                elif status in ['failed', 'rejected']:
                    metrics['rejected'] += count
                metrics['total_amount'] += float(total_amount or 0)
            
            return jsonify(metrics)
    except Exception as e:
        logger.exception("Errore nel caricamento metriche depositi: %s", e)
        return jsonify({
            'pending': 0,
            'completed': 0,
            'rejected': 0,
            'total_amount': 0.0
        })

@admin_bp.get("/api/deposits/pending")
@admin_required
def deposits_api_pending():
    """API per depositi in attesa"""
    logger.info(f"deposits_api_pending called - session: {dict(session)}")
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT dr.id, dr.amount, 
                       COALESCE(dr.iban, '') as iban, 
                       COALESCE(dr.method, 'bank') as method, 
                       COALESCE(dr.network, 'ethereum') as network,
                       COALESCE(dr.unique_key, '') as unique_key, 
                       COALESCE(dr.payment_reference, '') as payment_reference,
                       dr.created_at, 
                       COALESCE(dr.admin_notes, '') as admin_notes,
                       u.id as user_id, 
                       COALESCE(u.nome, '') as nome, 
                       u.email, 
                       COALESCE(u.kyc_status, 'unverified') as kyc_status
                FROM deposit_requests dr
                JOIN users u ON dr.user_id = u.id
                WHERE dr.status = 'pending'
                ORDER BY dr.created_at ASC
            """)
            pending_deposits = cur.fetchall()
            
            # Serializza datetime per JSON
            deposits = []
            for deposit in pending_deposits:
                item = dict(deposit)
                if item.get('created_at'):
                    try:
                        item['created_at'] = item['created_at'].isoformat()
                    except Exception:
                        item['created_at'] = str(item['created_at'])
                deposits.append(item)
            
            return jsonify({'pending_deposits': deposits})
    except Exception as e:
        logger.exception("Errore nel caricamento depositi in attesa: %s", e)
        return jsonify({'pending_deposits': []})

@admin_bp.post("/api/deposits/approve/<int:deposit_id>")
@admin_required
def deposits_api_approve(deposit_id):
    """API per approvare deposito"""
    try:
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', '')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste e è pending
            cur.execute("""
                SELECT id, user_id, amount, status FROM deposit_requests 
                WHERE id = %s
            """, (deposit_id,))
            request_detail = cur.fetchone()
            
            if not request_detail:
                return jsonify({'error': 'Richiesta non trovata'}), 404
            if request_detail['status'] != 'pending':
                return jsonify({'error': 'Solo le richieste in attesa possono essere approvate'}), 400
            
            # Approva richiesta
            cur.execute("""
                UPDATE deposit_requests 
                SET status = 'completed', approved_at = NOW(), approved_by = %s, admin_notes = %s
                WHERE id = %s
            """, (session.get('user_id'), admin_notes, deposit_id))
            
            # Aggiorna portfolio utente (crea record se non esiste)
            cur.execute("""
                INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits, created_at, updated_at)
                VALUES (%s, %s, 0.00, 0.00, 0.00, NOW(), NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    free_capital = user_portfolios.free_capital + %s,
                    updated_at = NOW()
            """, (request_detail['user_id'], request_detail['amount'], request_detail['amount']))
            
            # Crea transazione portfolio
            cur.execute("""
                INSERT INTO portfolio_transactions 
                (user_id, type, amount, description, created_at)
                VALUES (%s, 'deposit', %s, 'Deposito approvato', NOW())
            """, (request_detail['user_id'], request_detail['amount']))
            
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Deposito approvato con successo'})
    except Exception as e:
        logger.exception("Errore nell'approvazione deposito: %s", e)
        return jsonify({'error': 'approve_failed', 'debug': str(e)}), 500

@admin_bp.post("/api/deposits/reject/<int:deposit_id>")
@admin_required
def deposits_api_reject(deposit_id):
    """API per rifiutare deposito"""
    try:
        data = request.get_json() or {}
        admin_notes = data.get('admin_notes', '')
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste e è pending
            cur.execute("""
                SELECT id, status FROM deposit_requests 
                WHERE id = %s
            """, (deposit_id,))
            request_detail = cur.fetchone()
            
            if not request_detail:
                return jsonify({'error': 'Richiesta non trovata'}), 404
            if request_detail['status'] != 'pending':
                return jsonify({'error': 'Solo le richieste in attesa possono essere rifiutate'}), 400
            
            # Rifiuta richiesta
            cur.execute("""
                UPDATE deposit_requests 
                SET status = 'failed', admin_notes = %s
                WHERE id = %s
            """, (admin_notes, deposit_id))
            
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Deposito rifiutato con successo'})
    except Exception as e:
        logger.exception("Errore nel rifiuto deposito: %s", e)
        return jsonify({'error': 'reject_failed', 'debug': str(e)}), 500

@admin_bp.get("/deposits/history")
@admin_required
def deposits_history():
    """Pagina storico depositi"""
    return render_template('admin/deposits/history.html')

@admin_bp.get("/api/deposits/history")
@admin_required
def deposits_api_history():
    """API per storico depositi"""
    logger.info(f"deposits_api_history called - session: {dict(session)}")
    try:
        # Parametri di paginazione
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', '')
        search = request.args.get('search', '')
        
        offset = (page - 1) * per_page
        
        with get_conn() as conn, conn.cursor() as cur:
            # Query base
            base_query = """
                SELECT dr.id, dr.amount, dr.iban, dr.method, 
                       COALESCE(dr.network, 'ethereum') as network,
                       dr.unique_key, dr.payment_reference,
                       dr.status, dr.created_at, dr.approved_at, dr.admin_notes,
                       u.id as user_id, u.nome, u.email, u.kyc_status,
                       ic.bank_name, ic.account_holder,
                       admin_user.nome as approved_by_name
                FROM deposit_requests dr
                JOIN users u ON dr.user_id = u.id
                LEFT JOIN bank_configurations ic ON (dr.iban = ic.iban AND dr.method = 'bank')
                LEFT JOIN users admin_user ON dr.approved_by = admin_user.id
            """
            
            # Condizioni WHERE
            where_conditions = []
            params = []
            
            if status_filter:
                where_conditions.append("dr.status = %s")
                params.append(status_filter)
            
            if search:
                where_conditions.append("(u.email ILIKE %s OR u.nome ILIKE %s OR dr.unique_key ILIKE %s)")
                search_param = f"%{search}%"
                params.extend([search_param, search_param, search_param])
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Query per contare il totale
            count_query = f"""
                SELECT COUNT(*) as total
                FROM deposit_requests dr
                JOIN users u ON dr.user_id = u.id
                {where_clause}
            """
            cur.execute(count_query, params)
            total_count = cur.fetchone()['total']
            
            # Query per i dati
            data_query = f"""
                {base_query}
                {where_clause}
                ORDER BY dr.created_at DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(data_query, params + [per_page, offset])
            deposits = cur.fetchall()
            
            # Serializza datetime per JSON
            deposits_list = []
            for deposit in deposits:
                item = dict(deposit)
                if item.get('created_at'):
                    try:
                        item['created_at'] = item['created_at'].isoformat()
                    except Exception:
                        item['created_at'] = str(item['created_at'])
                if item.get('approved_at'):
                    try:
                        item['approved_at'] = item['approved_at'].isoformat()
                    except Exception:
                        item['approved_at'] = str(item['approved_at'])
                deposits_list.append(item)
            
            return jsonify({
                'deposits': deposits_list,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'total_pages': (total_count + per_page - 1) // per_page
                }
            })
    except Exception as e:
        logger.exception("Errore nel caricamento storico depositi: %s", e)
        return jsonify({'deposits': [], 'pagination': {'page': 1, 'per_page': 20, 'total': 0, 'total_pages': 0}})

@admin_bp.get("/api/deposit-requests")
@admin_required
def deposit_requests_list():
    return jsonify({'error': 'Depositi disabilitati'}), 404

@admin_bp.get("/api/deposit-stats")
@admin_required
def deposit_stats():
    return jsonify({'error': 'Depositi disabilitati'}), 404

@admin_bp.post("/api/deposit-requests/approve")
@admin_required
def approve_deposit_request():
    return jsonify({'error': 'Depositi disabilitati'}), 404

@admin_bp.post("/api/deposit-requests/reject")
@admin_required
def reject_deposit_request():
    return jsonify({'error': 'Depositi disabilitati'}), 404

# ---- TASK 2.7 - Gestione Prelievi ----
@admin_bp.get("/withdrawals")
@admin_required
def withdrawals_dashboard():
    """Dashboard dedicata per gestione prelievi"""
    return render_template('admin/withdrawals/dashboard.html')

@admin_bp.get("/withdrawals/history")
@admin_required
def withdrawals_history():
    """Storico prelievi admin"""
    return render_template('admin/withdrawals/history.html')

def get_admin_metrics():
    """Funzione helper per ottenere metriche generali admin"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Metriche utenti
            cur.execute("SELECT COUNT(*) FROM users")
            users_total_result = cur.fetchone()
            users_total = users_total_result[0] if users_total_result else 0
            
            cur.execute("SELECT COUNT(*) FROM users WHERE kyc_status = 'verified'")
            users_verified_result = cur.fetchone()
            users_verified = users_verified_result[0] if users_verified_result else 0
            
            # Metriche progetti
            cur.execute("SELECT COUNT(*) FROM projects WHERE status = 'active'")
            projects_active_result = cur.fetchone()
            projects_active = projects_active_result[0] if projects_active_result else 0
            
            # Metriche investimenti (placeholder)
            investments_total = 0.0
            
            # Metriche richieste
            cur.execute("SELECT COUNT(*) FROM deposit_requests WHERE status = 'pending'")
            requests_pending_result = cur.fetchone()
            requests_pending = requests_pending_result[0] if requests_pending_result else 0
            
            # Metriche transazioni
            cur.execute("SELECT COUNT(*) FROM portfolio_transactions WHERE DATE(created_at) = CURRENT_DATE")
            transactions_today_result = cur.fetchone()
            transactions_today = transactions_today_result[0] if transactions_today_result else 0
            
            return {
                'users_total': users_total,
                'users_verified': users_verified,
                'projects_active': projects_active,
                'investments_total': investments_total,
                'requests_pending': requests_pending,
                'transactions_today': transactions_today
            }
    except Exception as e:
        print(f"Errore nel recupero metriche admin: {e}")
        return {
            'users_total': 0,
            'users_verified': 0,
            'projects_active': 0,
            'investments_total': 0.0,
            'requests_pending': 0,
            'transactions_today': 0
        }

# ---- TASK 2.7 - Transazioni Sistema (RIMOSSA) ----
# Funzione rimossa - ora implementata più avanti nel file

# ---- TASK 2.7 - Sistema Referral (NUOVO) ----
@admin_bp.get("/referral")
@admin_required
def referral_dashboard():
    """Dashboard referral - Nuovo sistema referral"""
    return render_template('admin/referral/dashboard.html')

@admin_bp.get("/api/referral/users")
@admin_required
def get_referral_users():
    """Ottieni lista di tutti gli utenti con dati referral"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni tutti gli utenti con i loro dati referral
            cur.execute("""
                SELECT 
                    u.id,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u.nome, u.cognome)), ''),
                        u.nome
                    ) AS nome,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u.nome, u.cognome)), ''),
                        u.nome,
                        'Utente'
                    ) AS full_name,
                    u.email, u.created_at, u.referral_code,
                    COALESCE(up.free_capital, 0) + COALESCE(up.invested_capital, 0) + 
                    COALESCE(up.referral_bonus, 0) + COALESCE(up.profits, 0) as total_balance,
                    COALESCE(up.invested_capital, 0) as total_invested,
                    COALESCE(up.profits, 0) as total_profits,
                    COALESCE(up.referral_bonus, 0) as bonus_earned,
                    CASE 
                        WHEN up.id IS NOT NULL AND (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) > 0 
                        THEN 'active'
                        WHEN u.kyc_status = 'verified' THEN 'pending'
                        ELSE 'inactive'
                    END as status,
                    (SELECT COUNT(*) FROM users u2 WHERE u2.referred_by = u.id) as invited_count
                FROM users u
                LEFT JOIN user_portfolios up ON up.user_id = u.id
                ORDER BY u.created_at DESC
            """)
            users = cur.fetchall()
            
            return jsonify({
                'users': users
            })
            
    except Exception as e:
        print(f"Errore nel caricamento utenti referral: {e}")
        return jsonify({'error': 'Errore nel caricamento degli utenti'}), 500

@admin_bp.get("/api/referral/users/<int:user_id>/details")
@admin_required
def get_user_referral_details(user_id):
    """Ottieni dettagli referral di un utente specifico"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Ottieni dati utente
            cur.execute("""
                SELECT 
                    u.id,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u.nome, u.cognome)), ''),
                        u.nome
                    ) AS nome,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u.nome, u.cognome)), ''),
                        u.nome,
                        'Utente'
                    ) AS full_name,
                    u.email, u.created_at, u.referral_code,
                    COALESCE(up.free_capital, 0) + COALESCE(up.invested_capital, 0) + 
                    COALESCE(up.referral_bonus, 0) + COALESCE(up.profits, 0) as total_balance,
                    COALESCE(up.invested_capital, 0) as total_invested,
                    COALESCE(up.profits, 0) as total_profits,
                    COALESCE(up.referral_bonus, 0) as bonus_earned
                FROM users u
                LEFT JOIN user_portfolios up ON up.user_id = u.id
                WHERE u.id = %s
            """, (user_id,))
            user = cur.fetchone()
            
            if not user:
                return jsonify({'error': 'Utente non trovato'}), 404
            
            # Ottieni utenti invitati da questo utente
            cur.execute("""
                SELECT 
                    u2.id,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u2.nome, u2.cognome)), ''),
                        u2.nome
                    ) AS nome,
                    COALESCE(
                        NULLIF(TRIM(CONCAT_WS(' ', u2.nome, u2.cognome)), ''),
                        u2.nome,
                        'Utente'
                    ) AS full_name,
                    u2.email, u2.created_at,
                    COALESCE(up2.free_capital, 0) + COALESCE(up2.invested_capital, 0) + 
                    COALESCE(up2.referral_bonus, 0) + COALESCE(up2.profits, 0) as total_balance,
                    COALESCE(up2.invested_capital, 0) as total_invested,
                    COALESCE(up2.profits, 0) as total_profits,
                    COALESCE(up2.referral_bonus, 0) as bonus_generated
                FROM users u2
                LEFT JOIN user_portfolios up2 ON up2.user_id = u2.id
                WHERE u2.referred_by = %s
                ORDER BY u2.created_at DESC
            """, (user_id,))
            invited_users = cur.fetchall()
            
            return jsonify({
                'user': user,
                'invited_users': invited_users
            })
                             
    except Exception as e:
        print(f"Errore nel caricamento dettagli utente: {e}")
        return jsonify({'error': 'Errore nel caricamento dei dettagli utente'}), 500

@admin_bp.get("/api/referral/stats")
@admin_required
def get_referral_stats():
    """Ottieni statistiche generali del sistema referral"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Statistiche generali
            cur.execute("""
                SELECT 
                    COUNT(*) as total_users,
                    COUNT(CASE WHEN referred_by IS NOT NULL THEN 1 END) as users_with_referrer,
                    COUNT(CASE WHEN referral_code IS NOT NULL THEN 1 END) as users_with_code
                FROM users
            """)
            user_stats = cur.fetchone()
            
            # Calcola referral attivi (utenti che hanno invitato qualcuno)
            cur.execute("""
                SELECT COUNT(DISTINCT referred_by) as active_referrals
                FROM users 
                WHERE referred_by IS NOT NULL
            """)
            active_referrals = cur.fetchone()
            
            # Totale investito da tutti gli utenti
            cur.execute("""
                SELECT 
                    COALESCE(SUM(invested_capital), 0) as total_invested,
                    COALESCE(SUM(profits), 0) as total_profits,
                    COALESCE(SUM(referral_bonus), 0) as total_bonus
                FROM user_portfolios
            """)
            financial_stats = cur.fetchone()
            
            return jsonify({
                'total_users': user_stats['total_users'],
                'active_referrals': active_referrals['active_referrals'],
                'total_invested': float(financial_stats['total_invested']),
                'total_profits': float(financial_stats['total_profits']),
                'total_bonus': float(financial_stats['total_bonus'])
            })
        
    except Exception as e:
        print(f"Errore nel caricamento statistiche referral: {e}")
        return jsonify({'error': 'Errore nel caricamento delle statistiche'}), 500

@admin_bp.post("/api/referral/users/<int:user_id>/move")
@admin_required
def move_user_referral(user_id):
    """Sposta un utente sotto un altro utente nel sistema referral"""
    try:
        data = request.get_json() or {}
        new_referrer_id = data.get('new_referrer_id')
        
        if not new_referrer_id:
            return jsonify({'error': 'ID referrer mancante'}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che l'utente esista
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Utente non trovato'}), 404
            
            # Verifica che il nuovo referrer esista
            cur.execute("SELECT id FROM users WHERE id = %s", (new_referrer_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Referrer non trovato'}), 404
            
            # Evita auto-referral
            if user_id == new_referrer_id:
                return jsonify({'error': 'Un utente non pu essere referrer di se stesso'}), 400
            
            # Aggiorna il referrer
            cur.execute("""
                UPDATE users 
                SET referred_by = %s 
                WHERE id = %s
            """, (new_referrer_id, user_id))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Utente spostato con successo'
            })
        
    except Exception as e:
        print(f"Errore nello spostamento utente: {e}")
        return jsonify({'error': 'Errore nello spostamento dell\'utente'}), 500

# ---- TASK 2.7 - API Referral (RIMOSSE) ----

# ---- TASK 2.7 - Configurazione IBAN ----
@admin_bp.get("/iban-config")
@admin_required
def iban_config_dashboard():
    """Dashboard per configurazione IBAN sistema"""
    try:
        # Ottieni metriche generali per il sidebar
        admin_metrics = get_admin_metrics()
        
        # Verifica se la tabella IBAN esiste
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'iban_configurations'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                # Tabella non esiste, restituisci dashboard vuota con metriche
                return render_template('admin/settings/iban_config.html', 
                                     iban_configs=[],
                                     current_config=None,
                                     metrics=admin_metrics)
            
            # Ottieni configurazione corrente
            cur.execute("""
                SELECT * FROM iban_configurations 
                WHERE is_active = true 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            current_config = cur.fetchone()
            
            # Ottieni storico configurazioni
            cur.execute("""
                SELECT * FROM iban_configurations 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            iban_configs = cur.fetchall()
        
        return render_template('admin/settings/iban_config.html', 
                             iban_configs=iban_configs,
                             current_config=current_config,
                             metrics=admin_metrics)
                             
    except Exception as e:
        print(f"Errore in iban_config_dashboard: {e}")
        # Restituisci dashboard vuota con metriche di default
        return render_template('admin/settings/iban_config.html', 
                             iban_configs=[],
                             current_config=None,
                             metrics=get_admin_metrics())

@admin_bp.post("/api/iban-config")
@admin_required
def save_iban_configuration():
    """Salva nuova configurazione IBAN"""
    try:
        data = request.get_json()
        
        # Validazione dati
        if not data.get('iban'):
            return jsonify({'error': 'IBAN  obbligatorio'}), 400
        
        # Validazione formato IBAN (base)
        iban = data['iban'].replace(' ', '').upper()
        if len(iban) < 15 or len(iban) > 34:
            return jsonify({'error': 'Formato IBAN non valido'}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica se la tabella esiste, altrimenti creala
            cur.execute("""
                CREATE TABLE IF NOT EXISTS iban_configurations (
                    id SERIAL PRIMARY KEY,
                    iban VARCHAR(34) NOT NULL,
                    bank_name VARCHAR(255),
                    account_holder VARCHAR(255),
                    notes TEXT,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Disattiva tutte le configurazioni precedenti
            cur.execute("""
                UPDATE iban_configurations 
                SET is_active = false, updated_at = CURRENT_TIMESTAMP
            """)
            
            # Inserisci nuova configurazione
            cur.execute("""
                INSERT INTO iban_configurations (iban, bank_name, account_holder, notes, is_active)
                VALUES (%s, %s, %s, %s, true)
                RETURNING id
            """, (
                iban,
                data.get('bank_name'),
                data.get('account_holder'),
                data.get('notes')
            ))
            
            conn.commit()
            
        return jsonify({'success': True, 'message': 'Configurazione IBAN salvata con successo'})
        
    except Exception as e:
        print(f"Errore salvataggio IBAN: {e}")
        return jsonify({'error': f'Errore nel salvataggio: {str(e)}'}), 500

@admin_bp.get("/api/iban-config")
@admin_required
def get_iban_configuration():
    """Recupera configurazione IBAN per ricariche"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT * FROM iban_configurations 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        config = cur.fetchone()
    
    return jsonify(config) if config else jsonify({'error': 'Nessuna configurazione IBAN trovata'}), 404

@admin_bp.post("/api/iban-config")
@admin_required
def set_iban_configuration():
    """Imposta configurazione IBAN unico per ricariche"""
    data = request.get_json() or {}
    iban = data.get('iban')
    bank_name = data.get('bank_name')
    account_holder = data.get('account_holder')
    
    if not all([iban, bank_name, account_holder]):
        return jsonify({'error': 'IBAN, nome banca e intestatario richiesti'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Disattiva configurazioni precedenti
            cur.execute("UPDATE iban_configurations SET is_active = false")
            
            # Inserisci nuova configurazione
            cur.execute("""
                INSERT INTO iban_configurations (iban, bank_name, account_holder, is_active, created_at, updated_at)
                VALUES (%s, %s, %s, true, NOW(), NOW())
                RETURNING id
            """, (iban, bank_name, account_holder))
            
            config_id = cur.fetchone()['id']
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Configurazione IBAN aggiornata',
            'config_id': config_id
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore nel salvataggio: {str(e)}'}), 500

# ---- TASK 2.7 - Monitoraggio Transazioni (RIMOSSO) ----

# ---- TASK 2.7 - Gestione Referral (RIMOSSA) ----

# API distribute-referral-bonus rimossa

# ---- TASK 2.7 - Enhanced KYC Management ----
@admin_bp.get("/api/kyc-requests/enhanced")
@admin_required
def kyc_requests_enhanced():
    """Lista documenti KYC da approvare - versione enhanced"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT u.id, u.nome, u.email, u.kyc_status, u.created_at,
                   COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id AND d.category_id = 1
            WHERE u.kyc_status IN ('pending', 'unverified')
            GROUP BY u.id, u.nome, u.email, u.kyc_status, u.created_at
            ORDER BY u.created_at ASC
        """)
        requests = cur.fetchall()
    
    return jsonify(requests)

@admin_bp.get("/api/kyc-requests/<int:user_id>/documents")
@admin_required
def kyc_user_documents(user_id):
    """Documenti KYC specifici utente"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT d.*, dc.name as category_name
            FROM documents d
            JOIN document_categories dc ON dc.id = d.category_id
            WHERE d.user_id = %s AND dc.is_kyc = true
            ORDER BY d.uploaded_at DESC
        """, (user_id,))
        documents = cur.fetchall()
    
    return jsonify(documents)

# =====================================================
# CREATE PROJECT - Creazione nuovo progetto
# =====================================================

@admin_bp.post("/projects/create")
@admin_required
def create_project():
    """Crea un nuovo progetto immobiliare"""
    try:
        # Ottieni i dati dal form con validazione
        code = request.form.get('code', '').strip() or f'PRJ{int(time.time())}'
        name = request.form.get('title', '').strip()
        if not name:
            flash('Il titolo del progetto è obbligatorio', 'error')
            return redirect(url_for('admin.projects_list'))
        description = request.form.get('description', '').strip() or 'Descrizione non fornita'
        total_amount = request.form.get('total_amount', type=float) or 100000
        min_investment = request.form.get('min_investment', type=float) or 1000
        location = request.form.get('location', '').strip() or 'Indirizzo non specificato'
        project_type = request.form.get('type', 'residential')
        roi = request.form.get('roi', type=float) or 8.0
        # Data di inizio - usa data di default se non fornita
        start_date = request.form.get('start_date') or date.today().isoformat()
        
        # Nessun campo obbligatorio - validazione solo per valori numerici se forniti
        
        # Validazione importi (solo se forniti)
        if total_amount and total_amount <= 0:
            return jsonify({
                'success': False,
                'message': 'L\'importo target deve essere maggiore di zero'
            }), 400
            
        if min_investment <= 0:
            return jsonify({
                'success': False,
                'message': 'L\'investimento minimo deve essere maggiore di zero'
            }), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il codice non esista gi
            cur.execute("SELECT id FROM projects WHERE code = %s", (code,))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'Un progetto con questo codice esiste gi'
                }), 400
            
            # Gestione upload foto
            image_url = None
            if 'photo' in request.files:
                photo_file = request.files['photo']
                if photo_file and photo_file.filename:
                    # Genera nome file unico
                    filename = secure_filename(photo_file.filename)
                    if filename:
                        # Estensione file
                        file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
                        unique_filename = f"project_{code}_{int(time.time())}.{file_ext}"
                        
                        # Salva file
                        photo_path = os.path.join(get_upload_folder(), 'projects', unique_filename)
                        os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                        photo_file.save(photo_path)
                        image_url = f"projects/{unique_filename}"
            
            # Inserisci progetto nel database
            cur.execute("""
                INSERT INTO projects (code, name, title, description, total_amount, min_investment, 
                                   location, type, roi, start_date, image_url, status, funded_amount, duration)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (code, name, name, description, total_amount, min_investment, 
                  location, project_type, roi, start_date, image_url, 'active', 0.0, 365))
            
            project_id = cur.fetchone()['id']
            
            # Log dell'azione (temporaneamente disabilitato - tabella admin_actions non esiste)
            # cur.execute("""
            #     INSERT INTO admin_actions (admin_id, action, target_type, target_id, details, created_at)
            #     VALUES (%s, 'project_created', 'project', %s, %s, CURRENT_TIMESTAMP)
            # """, (session.get('user_id'), project_id, f'Progetto creato: {name} (ID: {project_id})'))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Progetto creato con successo',
                'project_id': project_id
            })
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Errore nella creazione del progetto: {e}")
        logger.error(f"Traceback completo: {error_details}")
        return jsonify({
            'success': False,
            'message': f'Errore interno del server: {str(e)}'
        }), 500

# ---- Static uploads ----
@admin_bp.get('/uploads/<path:filename>')
@admin_required
def uploaded_file(filename):
    return send_from_directory(get_upload_folder(), filename)

# =====================================================
# TRANSACTIONS - Report e analisi transazioni
# =====================================================

@admin_bp.get('/transactions')
@admin_required
def transactions_dashboard():
    """Dashboard transazioni con report e grafici"""
    try:
        logger.info("Inizio caricamento dashboard transazioni")
        with get_conn() as conn:
            cur = conn.cursor()
            
            # 1. STATISTICHE DEPOSITI (solo utenti attivi)
            logger.info("Caricamento statistiche depositi")
            cur.execute("""
                SELECT 
                    COUNT(*) as total_deposits,
                    COALESCE(SUM(dr.amount), 0) as total_deposit_amount,
                    COUNT(CASE WHEN dr.status = 'completed' THEN 1 END) as completed_deposits,
                    COALESCE(SUM(CASE WHEN dr.status = 'completed' THEN dr.amount ELSE 0 END), 0) as completed_deposit_amount,
                    COUNT(CASE WHEN dr.status = 'pending' THEN 1 END) as pending_deposits,
                    COUNT(CASE WHEN dr.status = 'rejected' THEN 1 END) as rejected_deposits
                FROM deposit_requests dr
                INNER JOIN users u ON dr.user_id = u.id
                WHERE u.id IS NOT NULL
            """)
            deposits_data = cur.fetchone()
            deposits_stats = {
                'total_deposits': deposits_data['total_deposits'] or 0,
                'total_deposit_amount': float(deposits_data['total_deposit_amount'] or 0),
                'completed_deposits': deposits_data['completed_deposits'] or 0,
                'completed_deposit_amount': float(deposits_data['completed_deposit_amount'] or 0),
                'pending_deposits': deposits_data['pending_deposits'] or 0,
                'rejected_deposits': deposits_data['rejected_deposits'] or 0
            }
            logger.info(f"Statistiche depositi caricate: {deposits_stats}")
            
            # 2. STATISTICHE PRELIEVI (solo utenti attivi)
            cur.execute("""
                SELECT 
                    COUNT(*) as total_withdrawals,
                    COALESCE(SUM(wr.amount), 0) as total_withdrawal_amount,
                    COUNT(CASE WHEN wr.status = 'completed' THEN 1 END) as completed_withdrawals,
                    COALESCE(SUM(CASE WHEN wr.status = 'completed' THEN wr.amount ELSE 0 END), 0) as completed_withdrawal_amount
                FROM withdrawal_requests wr
                INNER JOIN users u ON wr.user_id = u.id
                WHERE u.id IS NOT NULL
            """)
            withdrawals_data = cur.fetchone()
            withdrawals_stats = {
                'total_withdrawals': withdrawals_data['total_withdrawals'] or 0,
                'total_withdrawal_amount': float(withdrawals_data['total_withdrawal_amount'] or 0),
                'completed_withdrawals': withdrawals_data['completed_withdrawals'] or 0,
                'completed_withdrawal_amount': float(withdrawals_data['completed_withdrawal_amount'] or 0)
            }
            
            # 3. STATISTICHE PORTFOLIO (solo utenti attivi)
            cur.execute("""
                SELECT 
                    COUNT(*) as total_transactions,
                    COALESCE(SUM(CASE WHEN pt.type = 'deposit' THEN pt.amount ELSE 0 END), 0) as total_deposit_amount,
                    COALESCE(SUM(CASE WHEN pt.type = 'withdrawal' THEN pt.amount ELSE 0 END), 0) as total_withdrawal_amount,
                    COUNT(CASE WHEN pt.type = 'deposit' THEN 1 END) as deposit_transactions,
                    COUNT(CASE WHEN pt.type = 'withdrawal' THEN 1 END) as withdrawal_transactions,
                    COUNT(CASE WHEN pt.type = 'investment' THEN 1 END) as investment_transactions,
                    COUNT(CASE WHEN pt.type = 'roi' THEN 1 END) as roi_transactions,
                    COUNT(CASE WHEN pt.type = 'referral' THEN 1 END) as referral_transactions
                FROM portfolio_transactions pt
                INNER JOIN users u ON pt.user_id = u.id
                WHERE u.id IS NOT NULL
            """)
            portfolio_data = cur.fetchone()
            portfolio_stats = {
                'total_transactions': portfolio_data['total_transactions'] or 0,
                'total_deposit_amount': float(portfolio_data['total_deposit_amount'] or 0),
                'total_withdrawal_amount': float(portfolio_data['total_withdrawal_amount'] or 0),
                'deposit_transactions': portfolio_data['deposit_transactions'] or 0,
                'withdrawal_transactions': portfolio_data['withdrawal_transactions'] or 0,
                'investment_transactions': portfolio_data['investment_transactions'] or 0,
                'roi_transactions': portfolio_data['roi_transactions'] or 0,
                'referral_transactions': portfolio_data['referral_transactions'] or 0
            }
            
            # 4. STATISTICHE VENDITE (se la tabella esiste)
            try:
                sales_stats = {
                    'total_sales': 0,
                    'total_sales_amount': 0.0,
                    'total_profits': 0.0
                }
            except Exception as e:
                logger.error(f"Errore nel caricamento statistiche vendite: {e}")
                sales_stats = {
                    'total_sales': 0,
                    'total_sales_amount': 0.0,
                    'total_profits': 0.0
                }
            
            # 5. STATISTICHE CAPITALE TOTALE (solo utenti attivi)
            cur.execute("""
                SELECT 
                    COALESCE(SUM(up.free_capital), 0) as total_free_capital,
                    COALESCE(SUM(up.invested_capital), 0) as total_invested_capital,
                    COALESCE(SUM(up.referral_bonus), 0) as total_referral_bonus,
                    COALESCE(SUM(up.profits), 0) as total_profits
                FROM user_portfolios up
                INNER JOIN users u ON up.user_id = u.id
                WHERE u.id IS NOT NULL
            """)
            capital_data = cur.fetchone()
            total_capital = (float(capital_data['total_free_capital'] or 0) + 
                           float(capital_data['total_invested_capital'] or 0) + 
                           float(capital_data['total_referral_bonus'] or 0) + 
                           float(capital_data['total_profits'] or 0))
            
            capital_stats = {
                'total_free_capital': float(capital_data['total_free_capital'] or 0),
                'total_invested_capital': float(capital_data['total_invested_capital'] or 0),
                'total_referral_bonus': float(capital_data['total_referral_bonus'] or 0),
                'total_profits': float(capital_data['total_profits'] or 0),
                'total_capital': total_capital
            }
            
        return render_template('admin/transactions/dashboard.html',
                             deposits_stats=deposits_stats,
                             withdrawals_stats=withdrawals_stats,
                             portfolio_stats=portfolio_stats,
                             sales_stats=sales_stats,
                             capital_stats=capital_stats)
        
    except Exception as e:
        logger.error(f"Errore nel caricamento dashboard transazioni: {e}")
        # Valori di default in caso di errore
        deposits_stats = {
            'total_deposits': 0,
            'total_deposit_amount': 0.0,
            'completed_deposits': 0,
            'completed_deposit_amount': 0.0,
            'pending_deposits': 0,
            'rejected_deposits': 0
        }
        withdrawals_stats = {
            'total_withdrawals': 0,
            'total_withdrawal_amount': 0.0,
            'completed_withdrawals': 0,
            'completed_withdrawal_amount': 0.0
        }
        portfolio_stats = {
            'total_transactions': 0,
            'total_transaction_amount': 0.0,
            'deposit_transactions': 0,
            'withdrawal_transactions': 0,
            'investment_transactions': 0,
            'roi_transactions': 0,
            'referral_transactions': 0
        }
        sales_stats = {
            'total_sales': 0,
            'total_sales_amount': 0.0,
            'total_profits': 0.0
        }
        capital_stats = {
            'total_free_capital': 0.0,
            'total_invested_capital': 0.0,
            'total_referral_bonus': 0.0,
            'total_profits': 0.0,
            'total_capital': 0.0
        }
        return render_template('admin/transactions/dashboard.html',
                             deposits_stats=deposits_stats,
                             withdrawals_stats=withdrawals_stats,
                             portfolio_stats=portfolio_stats,
                             sales_stats=sales_stats,
                             capital_stats=capital_stats,
                             error="Errore nel caricamento dei dati")


@admin_bp.get('/transactions/<int:transaction_id>')
@admin_required
def transaction_detail(transaction_id):
    """Dettaglio di una transazione specifica"""
    try:
        with get_conn() as conn:
            cur = conn.cursor()
            
            # Dettagli transazione
            cur.execute("""
                SELECT 
                    pt.*,
                    u.email as user_email,
                    u.nome as user_name,
                    u.nome,
                    u.cognome
                FROM portfolio_transactions pt
                JOIN users u ON pt.user_id = u.id
                WHERE pt.id = %s
            """, (transaction_id,))
            transaction = cur.fetchone()
            
            if not transaction:
                return render_template('admin/transactions/detail.html', 
                                     error="Transazione non trovata")
            
            # Transazioni correlate (stesso utente, stesso giorno)
            cur.execute("""
                SELECT 
                    pt.id,
                    pt.type,
                    pt.amount,
                    pt.description,
                    pt.created_at
                FROM portfolio_transactions pt
                WHERE pt.user_id = %s
                AND DATE(pt.created_at) = DATE(%s)
                AND pt.id != %s
                ORDER BY pt.created_at DESC
                LIMIT 10
            """, (transaction['user_id'], transaction['created_at'], transaction_id))
            related_transactions = cur.fetchall()
            
            # Portfolio dell'utente al momento della transazione
            cur.execute("""
                SELECT 
                    free_capital,
                    invested_capital,
                    referral_bonus,
                    profits
                FROM user_portfolios
                WHERE user_id = %s
            """, (transaction['user_id'],))
            user_portfolio = cur.fetchone()
            
        return render_template('admin/transactions/detail.html',
                             transaction=transaction,
                             related_transactions=related_transactions,
                             user_portfolio=user_portfolio)
        
    except Exception as e:
        logger.error(f"Errore nel caricamento dettaglio transazione: {e}")
        return render_template('admin/transactions/detail.html',
                             error="Errore nel caricamento dei dati")


# =====================================================
# CAMBIO PASSWORD ADMIN
# =====================================================

@admin_bp.route("/change-password", methods=["GET", "POST"])
@admin_required
def change_admin_password():
    """Pagina per cambiare la password admin"""
    if request.method == "POST":
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        # Validazioni
        if not all([old_password, new_password, confirm_password]):
            return jsonify({
                "success": False,
                "error": "Tutti i campi sono obbligatori"
            }), 400
        
        if new_password != confirm_password:
            return jsonify({
                "success": False,
                "error": "Le password nuove non coincidono"
            }), 400
        
        if len(new_password) < 8:
            return jsonify({
                "success": False,
                "error": "La nuova password deve essere di almeno 8 caratteri"
            }), 400
        
        try:
            admin_user_id = session.get('user_id')
            
            with get_conn() as conn, conn.cursor() as cur:
                # Verifica password attuale
                cur.execute("""
                    SELECT password_hash FROM users 
                    WHERE id = %s AND role = 'admin'
                """, (admin_user_id,))
                user = cur.fetchone()
                
                if not user:
                    return jsonify({
                        "success": False,
                        "error": "Utente admin non trovato"
                    }), 404
                
                # Verifica password attuale usando SHA-256
                import hashlib
                if user['password_hash'] != hashlib.sha256(old_password.encode()).hexdigest():
                    return jsonify({
                        "success": False,
                        "error": "Password attuale non corretta"
                    }), 400
                
                # Aggiorna password usando SHA-256 (come nel sistema di login)
                new_password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                cur.execute("""
                    UPDATE users 
                    SET password_hash = %s, updated_at = NOW()
                    WHERE id = %s
                """, (new_password_hash, admin_user_id))
                
                conn.commit()
                
                return jsonify({
                    "success": True,
                    "message": "Password aggiornata con successo"
                })
                
        except Exception as e:
            logger.error(f"Errore cambio password admin: {e}")
            return jsonify({
                "success": False,
                "error": "Errore interno del server"
            }), 500
    
    # GET - Mostra form
    return render_template('admin/config/change_password.html',
                         current_page="config")

# ---- ENDPOINT ELIMINAZIONE DEPOSITI ----
@admin_bp.delete("/api/deposits/delete/<int:deposit_id>")
@admin_required
def deposits_api_delete(deposit_id):
    """API per eliminare un singolo deposito"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il deposito esista
            cur.execute("SELECT id FROM deposit_requests WHERE id = %s", (deposit_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Deposito non trovato'}), 404
            
            # Elimina il deposito
            cur.execute("DELETE FROM deposit_requests WHERE id = %s", (deposit_id,))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Deposito eliminato con successo'})
            
    except Exception as e:
        logger.exception("Errore nell'eliminazione deposito: %s", e)
        return jsonify({'error': 'delete_failed', 'debug': str(e)}), 500

@admin_bp.delete("/api/deposits/delete-multiple")
@admin_required
def deposits_api_delete_multiple():
    """API per eliminare più depositi"""
    try:
        data = request.get_json()
        deposit_ids = data.get('deposit_ids', [])
        
        if not deposit_ids:
            return jsonify({'error': 'Nessun deposito selezionato'}), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che tutti i depositi esistano
            placeholders = ','.join(['%s'] * len(deposit_ids))
            cur.execute(f"SELECT id FROM deposit_requests WHERE id IN ({placeholders})", deposit_ids)
            existing_ids = [row['id'] for row in cur.fetchall()]
            
            if len(existing_ids) != len(deposit_ids):
                return jsonify({'error': 'Alcuni depositi non sono stati trovati'}), 400
            
            # Elimina i depositi
            cur.execute(f"DELETE FROM deposit_requests WHERE id IN ({placeholders})", deposit_ids)
            conn.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Eliminati {len(deposit_ids)} depositi con successo',
                'deleted_count': len(deposit_ids)
            })
            
    except Exception as e:
        logger.exception("Errore nell'eliminazione multipla depositi: %s", e)
        return jsonify({'error': 'delete_multiple_failed', 'debug': str(e)}), 500

