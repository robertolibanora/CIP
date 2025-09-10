import os
import uuid
import time
import logging
import json
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, session, abort, send_from_directory, jsonify, render_template
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS admin_actions (
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
    except Exception:
        pass

# -----------------------------
# ADMIN BLUEPRINT (protected)
# -----------------------------
admin_bp = Blueprint("admin", __name__)

# Importa decoratori di autorizzazione
from backend.auth.decorators import admin_required
from backend.auth.routes import hash_password

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione admin

@admin_bp.get("/")
@admin_required
def admin_dashboard():
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
        sql = f"SELECT * FROM projects {where} ORDER BY created_at DESC"
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
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
    
    metrics = {
        'projects_total': projects_total,
        'projects_active': projects_active,
        'projects_draft': projects_draft,
        'projects_completed': projects_completed,
        'projects_active': projects_active  # Per compatibilità con sidebar
    }
    
    return render_template("admin/projects/list.html", metrics=metrics)

@admin_bp.post("/projects/new")
@admin_required
def projects_new():
    data = request.form or request.json or {}
    
    # Validazione campi obbligatori (allineati allo schema attuale)
    required_fields = ['code', 'title', 'description', 'target_amount', 'min_investment', 'start_date', 'end_date']
    for field in required_fields:
        if not data.get(field):
            abort(400, description=f"Campo obbligatorio mancante: {field}")
    
    # Gestione file upload
    photo = request.files.get('photo')
    documents = request.files.get('documents')
    
    if not photo or not documents:
        abort(400, description="Foto immobile e documenti tecnici sono obbligatori")
    
    # Salva i file (in uploads/projects)
    photo_filename = None
    documents_filename = None
    
    try:
        if photo:
            ext = os.path.splitext(photo.filename)[1].lower() or '.jpg'
            photo_filename = secure_filename(f"{data['code']}_photo_{int(time.time())}{ext}")
            photo_path = os.path.join(get_upload_folder(), 'projects', photo_filename)
            os.makedirs(os.path.dirname(photo_path), exist_ok=True)
            photo.save(photo_path)
        
        if documents:
            extd = os.path.splitext(documents.filename)[1].lower() or '.pdf'
            documents_filename = secure_filename(f"{data['code']}_docs_{int(time.time())}{extd}")
            documents_path = os.path.join(get_upload_folder(), 'projects', documents_filename)
            os.makedirs(os.path.dirname(documents_path), exist_ok=True)
            documents.save(documents_path)
    
    except Exception as e:
        abort(500, description=f"Errore nel salvataggio dei file: {str(e)}")
    
    # Mappa address -> location (compatibilità schema)
    location_value = data.get('address') or data.get('location') or ''
    status_value = data.get('status', 'draft')
    
    # Campi opzionali schema esteso
    roi_value = data.get('roi')
    duration_value = data.get('duration')
    project_type = data.get('type')
    
    # Prepara documents JSONB come array semplice di filenames
    documents_json = [documents_filename] if documents_filename else None
    
    # Inserisci nel database (schema con location, image_url, documents JSONB)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects (
                code, name, description, status, total_amount, start_date, end_date,
                location, min_investment, image_url, documents, roi, duration, type
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
            """,
            (
                data['code'], data['title'], data['description'], status_value,
                data['target_amount'], data.get('start_date'), data.get('end_date'),
                location_value, data.get('min_investment'), photo_filename, json.dumps(documents_json) if documents_json else None,
                roi_value, duration_value, project_type
            )
        )
        pid = cur.fetchone()['id']
    
    return jsonify({"id": pid, "message": "Progetto creato con successo"})

@admin_bp.get("/uploads/projects/<filename>")
@admin_required
def serve_project_file(filename):
    """Serve i file upload dei progetti (foto e documenti)"""
    upload_folder = get_upload_folder()
    projects_folder = os.path.join(upload_folder, 'projects')
    
    if not os.path.exists(os.path.join(projects_folder, filename)):
        abort(404)
    
    return send_from_directory(projects_folder, filename)

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
                SELECT i.id, i.amount, i.status, i.created_at, i.activated_at,
                       u.id as user_id, u.full_name, u.email, u.kyc_status
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
    data = request.form or request.json or {}
    fields = [
        ('code','code'),('title','name'),('description','description'),('status','status'),
        ('total_amount','total_amount'),('start_date','start_date'),('end_date','end_date')
    ]
    sets = []
    params = []
    for key, col in fields:
        if key in data and data.get(key) is not None:
            sets.append(f"{col}=%s"); params.append(data.get(key))
    if not sets:
        abort(400)
    params.append(pid)
    sql = f"UPDATE projects SET {', '.join(sets)} WHERE id=%s"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
    return jsonify({"updated": True})

@admin_bp.delete("/projects/<int:pid>")
@admin_required
def projects_delete(pid):
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica se ci sono investimenti attivi
        cur.execute("SELECT COUNT(*) as count FROM investments WHERE project_id=%s AND status='active'", (pid,))
        active_investments = cur.fetchone()['count']
        
        if active_investments > 0:
            return jsonify({"error": "Impossibile eliminare: ci sono investimenti attivi"}), 400
        
        # Elimina il progetto
        cur.execute("DELETE FROM projects WHERE id=%s", (pid,))
        
        if cur.rowcount == 0:
            abort(404)
    
    return jsonify({"deleted": True})

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
        'total_users': users_total  # Per compatibilità con sidebar
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
            SELECT pt.*, u.full_name as user_name, u.email as user_email
            FROM portfolio_transactions pt
            JOIN users u ON u.id = pt.user_id
            ORDER BY pt.created_at DESC
            LIMIT 20
        """)
        transactions = cur.fetchall()
        
        # Top utenti per portfolio
        cur.execute("""
            SELECT 
                u.id, u.full_name as name, u.email,
                (up.free_capital + up.invested_capital + up.referral_bonus + up.profits) as total_balance,
                COUNT(i.id) as active_investments
            FROM users u
            JOIN user_portfolios up ON up.user_id = u.id
            LEFT JOIN investments i ON i.user_id = u.id AND i.status = 'active'
            GROUP BY u.id, u.full_name, u.email, up.free_capital, up.invested_capital, up.referral_bonus, up.profits
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

@admin_bp.post("/portfolio/movements")
@admin_required
def create_portfolio_movement():
    """Crea nuovo movimento portfolio"""
    data = request.json
    
    required_fields = ['user_id', 'type', 'section', 'amount', 'description']
    for field in required_fields:
        if not data.get(field):
            return jsonify({"error": f"Campo {field} obbligatorio"}), 400
    
    user_id = int(data['user_id'])
    movement_type = data['type']
    section = data['section']
    amount = float(data['amount'])
    description = data['description']
    admin_notes = data.get('admin_notes', '')
    
    # Validation
    if amount <= 0:
        return jsonify({"error": "L'importo deve essere positivo"}), 400
    
    # Adjust amount for withdrawals
    if movement_type in ['withdrawal']:
        amount = -amount
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica esistenza utente e portfolio
        cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        if not cur.fetchone():
            return jsonify({"error": "Utente non trovato"}), 404
        
        # Crea portfolio se non esiste
        cur.execute("""
            INSERT INTO user_portfolios (user_id, free_capital, invested_capital, referral_bonus, profits)
            VALUES (%s, 0, 0, 0, 0)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id,))
        
        # Aggiorna sezione portfolio
        cur.execute(f"""
            UPDATE user_portfolios 
            SET {section} = {section} + %s, updated_at = NOW()
            WHERE user_id = %s
        """, (amount, user_id))
        
        # Registra transazione
        cur.execute("""
            INSERT INTO portfolio_transactions 
            (user_id, type, amount, description, section, admin_notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, (user_id, movement_type, amount, description, section, admin_notes))
        
        transaction_id = cur.fetchone()['id']
    
    return jsonify({
        "success": True,
        "transaction_id": transaction_id,
        "message": "Movimento creato con successo"
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
            'ID', 'Codice', 'Nome', 'Descrizione', 'Località', 'Tipologia',
            'Importo Totale', 'Min Investment', 'ROI', 'Durata', 'Stato',
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
                project.get('duration', ''),
                project.get('status', ''),
                project.get('start_date', ''),
                project.get('end_date', ''),
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
        'total_users': users_total  # Per compatibilità con sidebar
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
            SELECT id, full_name, email, telefono, address, kyc_status, 
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
                u.id, u.full_name, u.email, u.telefono, u.address,
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
            GROUP BY u.id, u.full_name, u.email, u.telefono, u.address, 
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
    
    valid_actions = ['approve', 'reject', 'pending', 'export', 'notify']
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
                SELECT id, full_name, email, telefono, kyc_status, created_at
                FROM users 
                WHERE id IN ({placeholders}) AND role = 'investor'
                ORDER BY created_at DESC
            """, request_ids)
            
            users = cur.fetchall()
            return jsonify({"users": users, "action": "export"})
        
        elif action == 'notify':
            # TODO: Implementare sistema notifiche
            pass
        
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
                (u.full_name ILIKE %s OR u.email ILIKE %s OR u.telefono ILIKE %s)
            """)
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        where_clause = " AND ".join(where_conditions)
        
        cur.execute(f"""
            SELECT 
                u.id, u.full_name, u.email, u.telefono, u.address,
                u.kyc_status, u.created_at, u.kyc_notes,
                COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            LEFT JOIN doc_categories dc ON dc.id = d.category_id AND dc.is_kyc = true
            WHERE {where_clause}
            GROUP BY u.id, u.full_name, u.email, u.telefono, u.address, 
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
                user.get('full_name', ''),
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
                (u.full_name ILIKE %s OR u.email ILIKE %s OR u.telefono ILIKE %s)
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
            'name_asc': 'u.full_name ASC',
            'name_desc': 'u.full_name DESC',
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
                u.id, u.full_name, u.email, u.telefono, u.address,
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
        
        # Attività recente (mock data)
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
            return jsonify({"error": "Non è possibile sospendere un amministratore"}), 400
        
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
    
    valid_actions = ['approve_kyc', 'reject_kyc', 'suspend', 'activate', 'export', 'send_notification']
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
                SELECT id, full_name, email, telefono, kyc_status, created_at
                FROM users 
                WHERE id IN ({placeholders})
                ORDER BY created_at DESC
            """, user_ids)
            
            users = cur.fetchall()
            return jsonify({"users": users, "action": "export"})
        
        elif action == 'send_notification':
            # TODO: Implementare sistema notifiche
            pass
        
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
                user.get('full_name', ''),
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

@admin_bp.get("/api/admin/users")
@admin_required
def api_admin_users_list():
    """Lista utenti con ricerca e filtri per dashboard admin.
    Supporta query: search, role, kyc, page, page_size.
    """
    # Normalizza parametri
    search = request.args.get('search')
    role_param = request.args.get('role')  # expected: 'investor' or 'non-investor'
    kyc_param = request.args.get('kyc')    # expected: 'verified' | 'unverified' | 'pending' | 'rejected'
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 25))

    # Mappa ai parametri esistenti di get_users_list
    # get_users_list usa: role, kyc_status, search
    # Gestiamo anche conteggio totale per paginazione
    with get_conn() as conn, conn.cursor() as cur:
        where_conditions = []
        params = []

        # Il filtro 'investor' qui NON usa il ruolo utente, ma il saldo portafoglio.
        # Applicheremo questo filtro dopo la query perché dipende da un calcolo.

        if kyc_param:
            # mappa 'verified' e 'unverified' alle nostre opzioni
            if kyc_param == 'unverified':
                where_conditions.append("u.kyc_status = 'unverified'")
            elif kyc_param in ('verified', 'pending', 'rejected'):
                where_conditions.append("u.kyc_status = %s")
                params.append(kyc_param)

        if search:
            where_conditions.append("(u.email ILIKE %s OR u.full_name ILIKE %s OR u.nome_telegram ILIKE %s)")
            like = f"%{search}%"
            params.extend([like, like, like])

        where_clause = ("WHERE " + " AND ".join(where_conditions)) if where_conditions else ""

        # Conteggio totale
        cur.execute(f"SELECT COUNT(*) AS total FROM users u {where_clause}", params)
        total = cur.fetchone()['total']

        # Paginazione
        offset = (page - 1) * page_size

        # Dati principali per tabella (includiamo saldo portafoglio)
        cur.execute(f"""
            SELECT 
                u.id,
                u.nome || ' ' || u.cognome AS nome_completo,
                u.nome_telegram,
                u.kyc_status,
                u.created_at,
                COALESCE(up.free_capital, 0) + COALESCE(up.invested_capital, 0) +
                COALESCE(up.referral_bonus, 0) + COALESCE(up.profits, 0) AS portfolio_total
            FROM users u
            LEFT JOIN user_portfolios up ON up.user_id = u.id
            {where_clause}
            ORDER BY u.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [page_size, offset])
        rows = cur.fetchall()

    # Normalizza risposta
    items = []
    for r in rows:
        portfolio_total = float(r.get('portfolio_total', 0) or 0)
        is_investor = portfolio_total >= 100.0
        # Applica filtro investitori/non investitori se richiesto
        if role_param == 'investor' and not is_investor:
            continue
        if role_param in ('non-investor', 'non_investor', 'notinvestor', 'non') and is_investor:
            continue
        items.append({
            'id': r['id'],
            'full_name': r.get('nome_completo') or '',
            'telegram_username': r.get('nome_telegram') or '',
            'investor_status': 'si' if is_investor else 'no',
            'kyc_status': r.get('kyc_status'),
            'created_at': r.get('created_at').isoformat() if r.get('created_at') else None,
            'portfolio_total': portfolio_total,
        })

    return jsonify({
        'items': items,
        'total': total,
        'page': page,
        'page_size': page_size
    })


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
                u.address
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
        'address': u['address']
    })


@admin_bp.patch("/api/admin/users/<int:user_id>")
@admin_required
def api_admin_user_update(user_id: int):
    """Aggiorna dati utente. Solo admin."""
    data = request.get_json() or {}

    allowed_fields = ['name', 'nome', 'cognome', 'email', 'phone', 'telegram', 'investor_status', 'kyc_status', 'address']
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

    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
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

    return jsonify({'success': True, 'message': 'Utente aggiornato con successo'})


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
            SELECT i.id, i.amount, i.status, i.created_at, p.name AS project_name
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
        cur.execute(
            """
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'portfolio_update', 'user', %s, %s)
            """,
            (session.get('user_id'), user_id, 'Aggiornati saldi portafoglio')
        )

    return jsonify({'success': True, 'message': 'Portafoglio aggiornato'})


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
    """Aggiunge o rimuove un importo dalla sezione profits di più utenti.
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
        # Log per-utente per tracciabilità dettagliata
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
    data = request.get_json() or {}
    admin_password = data.get('admin_password')
    if not admin_password:
        return jsonify({'error': 'Password admin richiesta'}), 400

    admin_id = session.get('user_id')
    if not admin_id:
        return jsonify({'error': 'Non autenticato'}), 401

    with get_conn() as conn, conn.cursor() as cur:
        ensure_admin_actions_table(cur)
        # Verifica password admin
        cur.execute("SELECT password_hash, role FROM users WHERE id = %s", (admin_id,))
        admin_row = cur.fetchone()
        if not admin_row or admin_row.get('role') != 'admin':
            return jsonify({'error': 'Permesso negato'}), 403
        if admin_row.get('password_hash') != hash_password(admin_password):
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

        # Elimina record correlati essenziali (investments, documents, portfolio) e infine l'utente
        cur.execute("DELETE FROM investments WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM documents WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM user_portfolios WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        # Log eliminazione (immutabile; nessuna delete di admin_actions)
        cur.execute(
            """
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, 'user_delete', 'user', %s, 'Utente eliminato definitivamente')
            """,
            (session.get('user_id'), user_id)
        )

    return jsonify({'success': True, 'message': 'Utente eliminato'})


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


## Endpoint rimosso: clear dello storico non più disponibile

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
        'total_users': users_total  # Per compatibilità con sidebar
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
@admin_required
def users_management_page():
    """Render della pagina Gestione Utenti"""
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
    
    # Average ROI
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
    
    # Projects Performance (top 10 projects by ROI)
    cur.execute("""
        SELECT p.name, p.roi, 
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
        writer.writerow(['Codice', 'Titolo', 'ROI %', 'Volume €', 'Investitori', 'Finanziamento %', 'Stato'])
        
        for project in analytics_data.get('top_projects', []):
            writer.writerow([
                project['code'],
                project['name'],
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
        writer.writerow(['Revenue Totale', f"€{kpis.get('total_revenue', 0):,.2f}", f"{kpis.get('revenue_change', 0):.1f}%"])
        writer.writerow(['Nuovi Utenti', kpis.get('new_users', 0), f"{kpis.get('users_change', 0):.1f}%"])
        writer.writerow(['Volume Investimenti', f"€{kpis.get('investment_volume', 0):,.2f}", f"{kpis.get('investment_change', 0):.1f}%"])
        writer.writerow(['Progetti Attivi', kpis.get('active_projects', 0), kpis.get('projects_change', 0)])
        
        writer.writerow([])  # Empty row
        writer.writerow(['Metriche Secondarie', 'Valore', ''])
        
        metrics = analytics_data.get('metrics', {})
        writer.writerow(['Tasso Conversione', f"{metrics.get('conversion_rate', 0):.1f}%", ''])
        writer.writerow(['Investimento Medio', f"€{metrics.get('avg_investment', 0):,.2f}", ''])
        writer.writerow(['ROI Medio', f"{metrics.get('avg_roi', 0):.1f}%", ''])
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

# ---- Sistema Configurazione ----
@admin_bp.get("/settings")
@admin_required
def settings_dashboard():
    """Dashboard configurazione admin"""
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(get_settings_data())
    
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
        'total_users': users_total  # Per compatibilità con sidebar
    }
    
    return render_template("admin/settings/dashboard.html", metrics=metrics)

@admin_bp.get("/settings/data")
@admin_required
def settings_data():
    """Dati configurazione sistema"""
    return jsonify(get_settings_data())

def get_settings_data():
    """Helper per ottenere dati configurazione"""
    with get_conn() as conn, conn.cursor() as cur:
        try:
            # Carica tutte le impostazioni dalla tabella settings
            cur.execute("""
                SELECT category, key, value, value_type
                FROM system_settings
                ORDER BY category, key
            """)
            settings_raw = cur.fetchall()
        except Exception as e:
            # Se tabella non esiste, usa valori predefiniti
            logger.warning(f"Tabella system_settings non esiste: {e}")
            settings_raw = []
        
        # Organizza le impostazioni per categoria
        settings = {
            'general': {},
            'iban': {},
            'financial': {},
            'security': {},
            'system': {}
        }
        
        for setting in settings_raw:
            category = setting['category']
            key = setting['key']
            value = setting['value']
            value_type = setting['value_type']
            
            # Converti il valore nel tipo corretto
            if value_type == 'boolean':
                value = value.lower() == 'true'
            elif value_type == 'integer':
                value = int(value) if value else 0
            elif value_type == 'float':
                value = float(value) if value else 0.0
            
            if category in settings:
                settings[category][key] = value
        
        # Valori predefiniti se non esistono
        if not settings['general']:
            settings['general'] = {
                'platform_name': 'CIP Immobiliare',
                'description': 'Piattaforma di investimenti immobiliari innovativa',
                'contact_email': 'info@cipimmobiliare.it',
                'support_phone': '+39 02 1234567',
                'company_address': 'Via Roma 123, 20121 Milano (MI)'
            }
        
        if not settings['financial']:
            settings['financial'] = {
                'min_investment': 500,
                'max_investment': 100000,
                'daily_limit': 10000,
                'monthly_limit': 50000,
                'platform_commission': 2.0,
                'referral_commission': 1.0,
                'withdrawal_fee': 5.0,
                'free_withdrawal_threshold': 1000,
                'referral_active': True
            }
        
        if not settings['security']:
            settings['security'] = {
                'kyc_timeout': 7,
                'no_kyc_limit': 0,
                'auto_approve_kyc': 'never',
                'session_duration': 24,
                'max_login_attempts': 5,
                'account_lockout_duration': 30,
                'min_password_length': 8,
                'require_id_card': True,
                'require_fiscal_code': True,
                'require_address_proof': False,
                'require_income_proof': False,
                'require_password_uppercase': True,
                'require_password_numbers': True,
                'require_password_symbols': False,
                'enable_2fa': False
            }
        
        return settings

@admin_bp.post("/settings/save")
@admin_required
def settings_save():
    """Salva configurazione sistema"""
    data = request.json or {}
    category = data.get('category')
    settings_data = data.get('data', {})
    
    if not category:
        return jsonify({"error": "Categoria richiesta"}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        try:
            # Salva ogni impostazione nella tabella
            for key, value in settings_data.items():
                # Determina il tipo di valore
                if isinstance(value, bool):
                    value_type = 'boolean'
                    value_str = str(value).lower()
                elif isinstance(value, int):
                    value_type = 'integer'
                    value_str = str(value)
                elif isinstance(value, float):
                    value_type = 'float'
                    value_str = str(value)
                else:
                    value_type = 'string'
                    value_str = str(value)
                
                # Inserisci o aggiorna l'impostazione
                cur.execute("""
                    INSERT INTO system_settings (category, key, value, value_type, updated_at, updated_by)
                    VALUES (%s, %s, %s, %s, NOW(), %s)
                    ON CONFLICT (category, key) 
                    DO UPDATE SET 
                        value = EXCLUDED.value,
                        value_type = EXCLUDED.value_type,
                        updated_at = EXCLUDED.updated_at,
                        updated_by = EXCLUDED.updated_by
                """, (category, key, value_str, value_type, session.get('user_id')))
            
            # Log dell'azione admin
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'settings_update', 'system', %s, %s)
            """, (session.get('user_id'), 0, f"Aggiornate impostazioni {category}"))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            return jsonify({"error": f"Errore nel salvataggio: {str(e)}"}), 500
    
    return jsonify({"success": True, "message": f"Impostazioni {category} salvate"})

@admin_bp.post("/settings/backup")
@admin_required
def settings_backup():
    """Crea backup del sistema"""
    data = request.json or {}
    backup_type = data.get('type', 'full')
    compression = data.get('compression', 'gzip')
    notes = data.get('notes', '')
    
    try:
        import subprocess
        import os
        from datetime import datetime
        
        # Timestamp per il nome del backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"cip_backup_{backup_type}_{timestamp}"
        
        # Directory backup (assicurati che esista)
        backup_dir = "/tmp/cip_backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        if backup_type in ['full', 'database']:
            # Backup database (mock command - sostituisci con i tuoi parametri)
            db_backup_cmd = [
                'pg_dump',
                '-h', 'localhost',
                '-U', 'cip_user',
                '-d', 'cip_database',
                '-f', f"{backup_dir}/{backup_filename}_db.sql"
            ]
            
            # Per demo, creiamo un file vuoto
            with open(f"{backup_dir}/{backup_filename}_db.sql", 'w') as f:
                f.write(f"-- CIP Database Backup\n-- Created: {datetime.now()}\n-- Notes: {notes}\n")
        
        if backup_type in ['full', 'files']:
            # Backup file uploads
            files_backup_cmd = [
                'tar', '-czf',
                f"{backup_dir}/{backup_filename}_files.tar.gz",
                'uploads/'  # Ajusta el path según tu estructura
            ]
            # subprocess.run(files_backup_cmd, check=True)
        
        # Registra il backup nel database
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO system_backups (filename, backup_type, size_bytes, created_by, notes)
                VALUES (%s, %s, %s, %s, %s)
            """, (backup_filename, backup_type, 1024, session.get('user_id'), notes))
            
            # Log dell'azione
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
                VALUES (%s, 'backup_create', 'system', %s, %s)
            """, (session.get('user_id'), 0, f"Backup {backup_type} creato: {backup_filename}"))
        
        return jsonify({
            "success": True, 
            "message": "Backup creato con successo",
            "filename": backup_filename
        })
        
    except Exception as e:
        return jsonify({"error": f"Errore nella creazione del backup: {str(e)}"}), 500

@admin_bp.get("/settings/backup/download")
@admin_required
def settings_backup_download():
    """Download ultimo backup"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT filename, backup_type, created_at
                FROM system_backups
                ORDER BY created_at DESC
                LIMIT 1
            """)
            backup = cur.fetchone()
            
            if not backup:
                return jsonify({"error": "Nessun backup disponibile"}), 404
            
            # Per demo, restituiamo informazioni sul backup
            return jsonify({
                "filename": backup['filename'],
                "type": backup['backup_type'],
                "created_at": backup['created_at'].isoformat(),
                "download_url": f"/admin/uploads/backups/{backup['filename']}.zip"
            })
    
    except Exception as e:
        return jsonify({"error": f"Errore nel download: {str(e)}"}), 500

@admin_bp.get("/settings/logs")
@admin_required
def settings_logs():
    """Visualizza log sistema"""
    log_type = request.args.get('type')
    period = request.args.get('period', 'week')
    search = request.args.get('search')
    
    # Calcola il range di date
    from datetime import datetime, timedelta
    now = datetime.now()
    
    if period == 'today':
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    else:  # all
        start_date = datetime(2020, 1, 1)
    
    with get_conn() as conn, conn.cursor() as cur:
        # Build query conditions
        where_conditions = ["created_at >= %s"]
        params = [start_date]
        
        if log_type:
            where_conditions.append("level = %s")
            params.append(log_type)
        
        if search:
            where_conditions.append("(message ILIKE %s OR details ILIKE %s)")
            search_param = f"%{search}%"
            params.extend([search_param, search_param])
        
        where_clause = " AND ".join(where_conditions)
        
        try:
            # Query dei log (assumendo una tabella system_logs)
            cur.execute(f"""
                SELECT level, message, details, source, created_at
                FROM system_logs
                WHERE {where_clause}
                ORDER BY created_at DESC
                LIMIT 200
            """, params)
            
            logs = cur.fetchall()
        except Exception as e:
            # Se tabella non esiste, usa log di esempio
            logger.warning(f"Tabella system_logs non esiste: {e}")
            logs = []
        
        # Se non ci sono log nella tabella, restituiamo log di esempio
        if not logs:
            logs = generate_mock_logs()
    
    return jsonify([
        {
            'level': log.get('level', 'info'),
            'message': log.get('message', ''),
            'details': log.get('details'),
            'source': log.get('source', 'Sistema'),
            'timestamp': log.get('created_at', now).isoformat() if hasattr(log.get('created_at', now), 'isoformat') else str(log.get('created_at', now))
        }
        for log in logs
    ])

def generate_mock_logs():
    """Genera log di esempio per demo"""
    from datetime import datetime, timedelta
    import random
    
    now = datetime.now()
    levels = ['info', 'warning', 'error', 'security', 'admin']
    sources = ['Sistema', 'Database', 'Auth', 'API', 'Backup']
    
    messages = {
        'info': ['Sistema avviato con successo', 'Backup completato', 'Utente registrato', 'Investimento processato'],
        'warning': ['Memoria RAM alta (85%)', 'Tentativo login fallito', 'Disco quasi pieno', 'Connessione lenta database'],
        'error': ['Errore connessione database', 'Upload file fallito', 'Timeout API esterna', 'Errore elaborazione pagamento'],
        'security': ['Tentativo accesso non autorizzato', 'IP bloccato per troppi tentativi', 'Password debole rilevata', 'Attività sospetta rilevata'],
        'admin': ['Impostazioni aggiornate', 'Backup manuale creato', 'Utente sospeso', 'Progetto approvato']
    }
    
    logs = []
    for i in range(50):
        level = random.choice(levels)
        message = random.choice(messages[level])
        timestamp = now - timedelta(minutes=random.randint(1, 10080))  # Ultima settimana
        
        logs.append({
            'level': level,
            'message': message,
            'details': f"Dettagli aggiuntivi per: {message}" if random.random() > 0.5 else None,
            'source': random.choice(sources),
            'created_at': timestamp
        })
    
    return sorted(logs, key=lambda x: x['created_at'], reverse=True)

@admin_bp.get("/settings/logs/export")
@admin_required
def settings_logs_export():
    """Esporta log in CSV"""
    format_type = request.args.get('format', 'csv')
    
    # Ottieni i log (riusa la logica di settings_logs)
    logs_data = settings_logs()
    logs = logs_data.get_json()
    
    if format_type == 'csv':
        import csv
        from io import StringIO
        from flask import Response
        
        output = StringIO()
        writer = csv.writer(output)
        
        # Header CSV
        writer.writerow(['Timestamp', 'Livello', 'Sorgente', 'Messaggio', 'Dettagli'])
        
        # Dati log
        for log in logs:
            writer.writerow([
                log['timestamp'],
                log['level'],
                log['source'],
                log['message'],
                log['details'] or ''
            ])
        
        output.seek(0)
        
        filename = f"system_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    
    return jsonify(logs)

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
        where = "WHERE email ILIKE %s OR full_name ILIKE %s"
        params = [f"%{q}%", f"%{q}%"]
    sql = f"SELECT id, email, full_name, role, kyc_status, currency_code FROM users {where} ORDER BY id"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify(rows)

@admin_bp.get("/users/<int:uid>")
@admin_required
def user_detail_legacy(uid):
    """Dettaglio utente legacy - mantenuto per compatibilità"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id,email,full_name,phone,address,role,kyc_status,currency_code,referral_code,referred_by FROM users WHERE id=%s", (uid,))
        u = cur.fetchone()
        cur.execute("""
            SELECT i.id, p.name, i.amount, i.status, i.created_at
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
        SELECT i.id, u.full_name, p.name, i.amount, i.status, i.created_at
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
            SELECT i.*, u.full_name, p.name AS project_title
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
        cur.execute("UPDATE investments SET status='active', activated_at=NOW() WHERE id=%s", (iid,))
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
            SELECT r.id, u.full_name, p.name AS project, r.amount, r.state, r.created_at
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
    """KYC reject legacy - mantenuto per compatibilità"""
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

# ---- Sistema Notifiche ----
@admin_bp.post("/notifications/new")
@admin_required
def notifications_new():
    data = request.form or request.json or {}
    user_id = data.get('user_id')  # None => broadcast
    title = data.get('title'); body = data.get('body'); priority = data.get('priority','low')
    scheduled_at = data.get('scheduled_at')  # ISO string optional
    if not title:
        abort(400)
    if scheduled_at:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_notifications (
                  id SERIAL PRIMARY KEY,
                  user_id INT REFERENCES users(id) ON DELETE CASCADE,
                  priority TEXT NOT NULL,
                  title TEXT NOT NULL,
                  body TEXT,
                  scheduled_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cur.execute(
                "INSERT INTO scheduled_notifications(user_id,priority,title,body,scheduled_at) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                (user_id, priority, title, body, scheduled_at)
            )
            nid = cur.fetchone()['id']
        return jsonify({"scheduled_id": nid})
    else:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO notifications(user_id,priority,title,body) VALUES (%s,%s,%s,%s) RETURNING id",
                        (user_id, priority, title, body))
            nid = cur.fetchone()['id']
        return jsonify({"notification_id": nid})

@admin_bp.post("/notifications/run_scheduler")
@admin_required
def notifications_run_scheduler():
    # move due scheduled to notifications
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_notifications (
              id SERIAL PRIMARY KEY,
              user_id INT REFERENCES users(id) ON DELETE CASCADE,
              priority TEXT NOT NULL,
              title TEXT NOT NULL,
              body TEXT,
              scheduled_at TIMESTAMPTZ NOT NULL
            )
        """)
        cur.execute("SELECT id, user_id, priority, title, body FROM scheduled_notifications WHERE scheduled_at <= NOW()")
        due = cur.fetchall()
        for d in due:
            cur.execute("INSERT INTO notifications(user_id,priority,title,body) VALUES (%s,%s,%s,%s)",
                        (d['user_id'], d['priority'], d['title'], d['body']))
            cur.execute("DELETE FROM scheduled_notifications WHERE id=%s", (d['id'],))
    return jsonify({"moved": len(due) if due else 0})

@admin_bp.route("/notifications/templates", methods=['GET', 'POST'])
@admin_required
def notifications_templates(tid=None):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notification_templates (
              id SERIAL PRIMARY KEY,
              name TEXT NOT NULL,
              title TEXT NOT NULL,
              body TEXT NOT NULL,
              priority TEXT NOT NULL DEFAULT 'low'
            )
        """)
    if request.method == 'GET':
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM notification_templates ORDER BY id DESC")
            rows = cur.fetchall()
        return jsonify(rows)
    data = request.form or request.json or {}
    if tid:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE notification_templates SET name=%s, title=%s, body=%s, priority=%s WHERE id=%s",
                        (data.get('name'), data.get('title'), data.get('body'), data.get('priority','low'), tid))
        return jsonify({"updated": tid})
    else:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO notification_templates(name,title,body,priority) VALUES (%s,%s,%s,%s) RETURNING id",
                        (data.get('name'), data.get('title'), data.get('body'), data.get('priority','low')))
            nid = cur.fetchone()['id']
        return jsonify({"id": nid})

@admin_bp.post("/notifications/templates/<int:tid>/edit")
@admin_required
def notifications_templates_edit(tid):
    data = request.form or request.json or {}
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notification_templates SET name=%s, title=%s, body=%s, priority=%s WHERE id=%s",
                    (data.get('name'), data.get('title'), data.get('body'), data.get('priority','low'), tid))
    return jsonify({"updated": tid})

@admin_bp.post("/notifications/templates/<int:tid>/delete")
@admin_required
def notifications_templates_delete(tid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM notification_templates WHERE id=%s", (tid,))
    return jsonify({"deleted": tid})

# ---- Analytics Legacy ----
@admin_bp.get("/analytics/legacy")
@admin_required
def analytics_legacy():
    """Analytics legacy - mantenuto per compatibilità"""
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
    """Pagina Depositi disattivata: restituisce pagina vuota senza logica."""
    return render_template('admin/deposits/dashboard.html')

@admin_bp.get("/deposits/history")
@admin_required
def deposits_history():
    """Pagina storico depositi"""
    return render_template('admin/deposits/history.html')

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

# ---- TASK 2.7 - Transazioni Sistema ----
@admin_bp.get("/transactions")
@admin_required
def transactions_dashboard():
    """Dashboard per visualizzazione transazioni sistema"""
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica se le tabelle esistono
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'portfolio_transactions'
                );
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                return render_template('admin/transactions/dashboard.html', 
                                     transactions=[],
                                     metrics={
                                         'total_transactions': 0,
                                         'today_transactions': 0,
                                         'total_volume': 0.0,
                                         'pending_transactions': 0
                                     })
            
            # Statistiche transazioni
            cur.execute("""
                SELECT 
                    COUNT(*) as total_transactions,
                    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) as today_transactions,
                    COALESCE(SUM(ABS(amount)), 0) as total_volume,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_transactions
                FROM portfolio_transactions
            """)
            metrics = cur.fetchone()
            
            # Lista transazioni recenti
            page = request.args.get('page', 1, type=int)
            per_page = 20
            offset = (page - 1) * per_page
            
            cur.execute("""
                SELECT pt.*, u.full_name, u.email
                FROM portfolio_transactions pt
                JOIN users u ON u.id = pt.user_id
                ORDER BY pt.created_at DESC
                LIMIT %s OFFSET %s
            """, (per_page, offset))
            transactions = cur.fetchall()
            
            # Conta totale per paginazione
            cur.execute("SELECT COUNT(*) FROM portfolio_transactions")
            total_count_result = cur.fetchone()
            total_count = total_count_result[0] if total_count_result else 0
        
        # Ottieni metriche generali per il sidebar
        admin_metrics = get_admin_metrics()
        
        return render_template('admin/transactions/dashboard.html', 
                             transactions=transactions,
                             metrics={
                                 'total_transactions': metrics[0] if metrics else 0,
                                 'today_transactions': metrics[1] if metrics else 0,
                                 'total_volume': float(metrics[2]) if metrics and metrics[2] else 0.0,
                                 'pending_transactions': metrics[3] if metrics else 0,
                                 **admin_metrics  # Unpack metriche generali
                             },
                             page=page,
                             per_page=per_page,
                             total_count=total_count)
                             
    except Exception as e:
        print(f"Errore in transactions_dashboard: {e}")
        return render_template('admin/transactions/dashboard.html', 
                             transactions=[],
                             metrics={
                                 'total_transactions': 0,
                                 'today_transactions': 0,
                                 'total_volume': 0.0,
                                 'pending_transactions': 0,
                                 **get_admin_metrics()  # Unpack metriche generali
                             },
                             page=1,
                             per_page=20,
                             total_count=0)

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
                        u.full_name
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
                        u.full_name
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
                        u2.full_name
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
                return jsonify({'error': 'Un utente non può essere referrer di se stesso'}), 400
            
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
            return jsonify({'error': 'IBAN è obbligatorio'}), 400
        
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

# ---- TASK 2.7 - Monitoraggio Transazioni ----
@admin_bp.get("/api/transactions-overview")
@admin_required
def transactions_overview():
    """Monitoraggio transazioni: overview completo"""
    with get_conn() as conn, conn.cursor() as cur:
        # Statistiche ricariche
        cur.execute("""
            SELECT status, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM deposit_requests 
            GROUP BY status
        """)
        deposits_stats = cur.fetchall()
        
        # Statistiche prelievi
        cur.execute("""
            SELECT status, COUNT(*) as count, COALESCE(SUM(amount), 0) as total
            FROM withdrawal_requests 
            GROUP BY status
        """)
        withdrawals_stats = cur.fetchall()
        
        # Transazioni recenti
        cur.execute("""
            SELECT pt.*, u.full_name, u.email
            FROM portfolio_transactions pt
            JOIN users u ON u.id = pt.user_id
            ORDER BY pt.created_at DESC
            LIMIT 50
        """)
        recent_transactions = cur.fetchall()
    
    return jsonify({
        'deposits_stats': deposits_stats,
        'withdrawals_stats': withdrawals_stats,
        'recent_transactions': recent_transactions
    })

@admin_bp.get("/api/transactions")
@admin_required
def transactions_filtered():
    """Monitoraggio transazioni con filtri"""
    status = request.args.get('status')
    transaction_type = request.args.get('type')
    user_id = request.args.get('user_id')
    
    where_conditions = []
    params = []
    
    if status:
        where_conditions.append("pt.status = %s")
        params.append(status)
    
    if transaction_type:
        where_conditions.append("pt.type = %s")
        params.append(transaction_type)
    
    if user_id:
        where_conditions.append("pt.user_id = %s")
        params.append(user_id)
    
    where_clause = " AND ".join(where_conditions)
    if where_clause:
        where_clause = "WHERE " + where_clause
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(f"""
            SELECT pt.*, u.full_name, u.email
            FROM portfolio_transactions pt
            JOIN users u ON u.id = pt.user_id
            {where_clause}
            ORDER BY pt.created_at DESC
            LIMIT 100
        """, params)
        transactions = cur.fetchall()
    
    return jsonify(transactions)

# ---- TASK 2.7 - Gestione Referral (RIMOSSA) ----

# API distribute-referral-bonus rimossa

# ---- TASK 2.7 - Enhanced KYC Management ----
@admin_bp.get("/api/kyc-requests/enhanced")
@admin_required
def kyc_requests_enhanced():
    """Lista documenti KYC da approvare - versione enhanced"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT u.id, u.full_name, u.email, u.kyc_status, u.created_at,
                   COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id AND d.category_id = 1
            WHERE u.kyc_status IN ('pending', 'unverified')
            GROUP BY u.id, u.full_name, u.email, u.kyc_status, u.created_at
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
        # Ottieni i dati dal form
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        total_amount = request.form.get('total_amount', type=float)
        min_investment = request.form.get('min_investment', type=float) or 1000
        location = request.form.get('location', '').strip()
        project_type = request.form.get('type', 'residential')
        roi = request.form.get('roi', type=float) or 8.0
        duration = request.form.get('duration', type=int) or 12
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        
        # Validazione campi obbligatori
        if not code or not name or not total_amount:
            return jsonify({
                'success': False,
                'message': 'Codice, nome e importo totale sono obbligatori'
            }), 400
        
        # Validazione importi
        if total_amount <= 0 or min_investment <= 0:
            return jsonify({
                'success': False,
                'message': 'Gli importi devono essere maggiori di zero'
            }), 400
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica che il codice non esista già
            cur.execute("SELECT id FROM projects WHERE code = %s", (code,))
            if cur.fetchone():
                return jsonify({
                    'success': False,
                    'message': 'Un progetto con questo codice esiste già'
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
                INSERT INTO projects (code, name, description, total_amount, min_investment, 
                                   location, type, roi, duration, start_date, end_date, image_url, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """, (code, name, description, total_amount, min_investment, 
                  location, project_type, roi, duration, start_date, end_date, image_url))
            
            project_id = cur.lastrowid
            
            # Log dell'azione
            cur.execute("""
                INSERT INTO admin_actions (admin_id, action, details, created_at)
                VALUES (%s, 'project_created', %s, CURRENT_TIMESTAMP)
            """, (session.get('user_id'), f'Progetto creato: {name} (ID: {project_id})'))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Progetto creato con successo',
                'project_id': project_id
            })
            
    except Exception as e:
        logger.error(f"Errore nella creazione del progetto: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore interno del server'
        }), 500

# ---- Static uploads ----
@admin_bp.get('/uploads/<path:filename>')
@admin_required
def uploaded_file(filename):
    return send_from_directory(get_upload_folder(), filename)

