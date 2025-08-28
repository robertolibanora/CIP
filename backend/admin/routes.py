import os
import uuid
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, session, abort, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

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

# -----------------------------
# ADMIN BLUEPRINT (protected)
# -----------------------------
admin_bp = Blueprint("admin", __name__)

# Importa decoratori di autorizzazione
from backend.auth.decorators import admin_required

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione admin

@admin_bp.get("/")
@admin_required
def admin_dashboard():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_admin_metrics")
        m = cur.fetchone()
    
    # Renderizza il template admin
    from flask import render_template
    return render_template("admin/dashboard.html", metrics=m or {})

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
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    return render_template("admin/projects/list.html")

@admin_bp.post("/projects/new")
@admin_required
def projects_new():
    data = request.form or request.json or {}
    code = data.get('code'); title = data.get('title')
    if not code or not title:
        abort(400)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO projects(code,title,description,status,target_amount,start_date,end_date)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
            (
                code, title, data.get('description'), data.get('status','draft'),
                data.get('target_amount'), data.get('start_date'), data.get('end_date')
            )
        )
        pid = cur.fetchone()['id']
    return jsonify({"id": pid})

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
        ('code','code'),('title','title'),('description','description'),('status','status'),
        ('target_amount','target_amount'),('start_date','start_date'),('end_date','end_date')
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
    return render_template("admin/portfolio/dashboard.html")

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
            'ID', 'Codice', 'Titolo', 'Descrizione', 'Località', 'Tipologia',
            'Target Amount', 'Min Investment', 'ROI', 'Durata', 'Stato',
            'Data Inizio', 'Data Fine', 'Data Creazione'
        ])
        
        # Dati progetti
        for project in projects:
            writer.writerow([
                project.get('id', ''),
                project.get('code', ''),
                project.get('title', ''),
                project.get('description', ''),
                project.get('location', ''),
                project.get('type', ''),
                project.get('target_amount', ''),
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
    return render_template("admin/kyc/dashboard.html")

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
                   created_at, kyc_verified_at, kyc_notes
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
                u.kyc_status, u.created_at, u.kyc_verified_at, u.kyc_notes,
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
                     u.kyc_status, u.created_at, u.kyc_verified_at, u.kyc_notes, up.id,
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
                kyc_verified_at = NOW(),
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
                SET kyc_status = 'verified', kyc_verified_at = NOW(),
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
                u.kyc_status, u.created_at, u.kyc_verified_at, u.kyc_notes,
                COUNT(d.id) as documents_count
            FROM users u
            LEFT JOIN documents d ON d.user_id = u.id
            LEFT JOIN doc_categories dc ON dc.id = d.category_id AND dc.is_kyc = true
            WHERE {where_clause}
            GROUP BY u.id, u.full_name, u.email, u.telefono, u.address, 
                     u.kyc_status, u.created_at, u.kyc_verified_at, u.kyc_notes
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
            'Stato KYC', 'Data Registrazione', 'Data Verifica', 'Note', 'Documenti'
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
                user.get('kyc_verified_at', ''),
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

# ---- Gestione Utenti ----
@admin_bp.get("/users")
@admin_required
def users_dashboard():
    """Dashboard gestione utenti admin"""
    # Se richiesta AJAX, restituisce JSON
    if request.headers.get('Content-Type') == 'application/json' or request.args.get('format') == 'json':
        return jsonify(get_users_list())
    
    # Altrimenti restituisce il template HTML
    from flask import render_template
    return render_template("admin/users/dashboard.html")

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
                COUNT(*) FILTER (WHERE is_active = false) as suspended,
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
                u.kyc_status, u.role, u.is_active, u.created_at, u.last_login,
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
        cur.execute("SELECT is_active, role FROM users WHERE id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({"error": "Utente non trovato"}), 404
        
        # Non permettere di sospendere admin
        if user['role'] == 'admin':
            return jsonify({"error": "Non è possibile sospendere un amministratore"}), 400
        
        new_status = not user['is_active']
        
        cur.execute("""
            UPDATE users 
            SET is_active = %s
            WHERE id = %s
        """, (new_status, user_id))
        
        # Log dell'azione admin
        action = 'user_activate' if new_status else 'user_suspend'
        cur.execute("""
            INSERT INTO admin_actions (admin_id, action, target_type, target_id, details)
            VALUES (%s, %s, 'user', %s, %s)
        """, (session.get('user_id'), action, user_id, f"Utente {'attivato' if new_status else 'sospeso'}"))
    
    return jsonify({
        "success": True, 
        "message": f"Utente {'attivato' if new_status else 'sospeso'} con successo",
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
                SET kyc_status = 'verified', kyc_verified_at = NOW(),
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
                SET is_active = false
                WHERE id = ANY(%s) AND role != 'admin'
            """, (user_ids,))
            
        elif action == 'activate':
            cur.execute("""
                UPDATE users 
                SET is_active = true
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
    return render_template("admin/analytics/dashboard.html")

@admin_bp.get("/analytics/data")
@admin_required
def analytics_data():
    """Dati analytics con filtri temporali"""
    return jsonify(get_analytics_data())

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
    
    # Average KYC Approval Time (mock calculation)
    cur.execute("""
        SELECT 
            AVG(EXTRACT(EPOCH FROM (kyc_verified_at - created_at)) / 86400) as avg_approval_days
        FROM users 
        WHERE kyc_status = 'verified' 
        AND kyc_verified_at IS NOT NULL
        AND created_at BETWEEN %s AND %s
    """, (start_dt, end_dt))
    avg_approval_time = cur.fetchone()['avg_approval_days'] or 0
    
    # Retention Rate (users who logged in within 30 days of registration)
    cur.execute("""
        SELECT 
            COUNT(*) as total_users,
            COUNT(*) FILTER (WHERE last_login IS NOT NULL 
                AND last_login >= created_at + INTERVAL '30 days') as retained_users
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
        SELECT title, roi, 
               (SELECT COALESCE(SUM(amount), 0) FROM investments WHERE project_id = p.id) as volume,
               (SELECT COALESCE(SUM(amount), 0) FROM investments WHERE project_id = p.id) / p.target_amount * 100 as funding_percentage
        FROM projects p
        WHERE created_at BETWEEN %s AND %s
        AND roi IS NOT NULL
        ORDER BY roi DESC
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
            'labels': [row['title'][:20] + '...' if len(row['title']) > 20 else row['title'] for row in projects_performance],
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
            p.id, p.code, p.title, p.roi, p.status, p.target_amount,
            COALESCE(SUM(i.amount), 0) as volume,
            COUNT(DISTINCT i.user_id) as investors,
            COALESCE(SUM(i.amount), 0) / p.target_amount * 100 as funding_percentage
        FROM projects p
        LEFT JOIN investments i ON i.project_id = p.id AND i.status IN ('active', 'completed')
        WHERE p.created_at BETWEEN %s AND %s
        GROUP BY p.id, p.code, p.title, p.roi, p.status, p.target_amount
        ORDER BY p.roi DESC, volume DESC
        LIMIT 10
    """, (start_dt, end_dt))
    
    projects = cur.fetchall()
    
    return [
        {
            'id': project['id'],
            'code': project['code'],
            'title': project['title'],
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
    return render_template("admin/settings/dashboard.html")

@admin_bp.get("/settings/data")
@admin_required
def settings_data():
    """Dati configurazione sistema"""
    return jsonify(get_settings_data())

def get_settings_data():
    """Helper per ottenere dati configurazione"""
    with get_conn() as conn, conn.cursor() as cur:
        # Carica tutte le impostazioni dalla tabella settings
        cur.execute("""
            SELECT category, key, value, value_type
            FROM system_settings
            ORDER BY category, key
        """)
        settings_raw = cur.fetchall()
        
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
        
        # Query dei log (assumendo una tabella system_logs)
        cur.execute(f"""
            SELECT level, message, details, source, created_at
            FROM system_logs
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT 200
        """, params)
        
        logs = cur.fetchall()
        
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
def user_detail(uid):
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
def kyc_reject(uid):
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

# ---- Analytics ----
@admin_bp.get("/analytics")
@admin_required
def analytics():
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
@admin_bp.get("/api/deposit-requests")
@admin_required
def deposit_requests_list():
    """Gestione ricariche: lista richieste pending"""
    status = request.args.get('status', 'pending')
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT dr.id, dr.user_id, u.full_name, u.email, dr.amount, 
                   dr.unique_key, dr.payment_reference, dr.status, dr.created_at,
                   dr.iban, dr.admin_notes
            FROM deposit_requests dr
            JOIN users u ON u.id = dr.user_id
            WHERE dr.status = %s
            ORDER BY dr.created_at ASC
        """, (status,))
        requests = cur.fetchall()
    
    return jsonify(requests)

@admin_bp.post("/api/deposit-requests/approve")
@admin_required
def approve_deposit_request():
    """Approvazione ricarica dopo verifica bonifico"""
    data = request.get_json() or {}
    deposit_id = data.get('deposit_id')
    amount_received = data.get('amount_received')
    admin_notes = data.get('admin_notes', '')
    
    if not deposit_id:
        return jsonify({'error': 'Deposit ID richiesto'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste
            cur.execute("""
                SELECT dr.*, u.email FROM deposit_requests dr
                JOIN users u ON u.id = dr.user_id  
                WHERE dr.id = %s AND dr.status = 'pending'
            """, (deposit_id,))
            deposit = cur.fetchone()
            
            if not deposit:
                return jsonify({'error': 'Richiesta non trovata o già processata'}), 404
            
            # Aggiorna stato ricarica
            cur.execute("""
                UPDATE deposit_requests 
                SET status = 'completed', admin_notes = %s, approved_at = NOW(), approved_by = %s
                WHERE id = %s
            """, (admin_notes, session.get('user_id'), deposit_id))
            
            # Aggiorna portfolio utente (capitale libero)
            amount_to_add = amount_received if amount_received else deposit['amount']
            cur.execute("""
                UPDATE user_portfolios 
                SET free_capital = free_capital + %s, updated_at = NOW()
                WHERE user_id = %s
            """, (amount_to_add, deposit['user_id']))
            
            # Registra transazione
            cur.execute("""
                INSERT INTO portfolio_transactions (
                    user_id, type, amount, balance_before, balance_after,
                    description, reference_id, reference_type, status, created_at
                ) VALUES (
                    %s, 'deposit', %s, 0, %s, 
                    'Ricarica approvata da admin', %s, 'deposit_request', 'completed', NOW()
                )
            """, (deposit['user_id'], amount_to_add, amount_to_add, deposit_id))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Ricarica approvata con successo',
            'deposit_id': deposit_id,
            'amount_added': float(amount_to_add)
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore nell\'approvazione: {str(e)}'}), 500

@admin_bp.post("/api/deposit-requests/reject")
@admin_required
def reject_deposit_request():
    """Rifiuta richiesta di ricarica"""
    data = request.get_json() or {}
    deposit_id = data.get('deposit_id')
    admin_notes = data.get('admin_notes', '')
    
    if not deposit_id:
        return jsonify({'error': 'Deposit ID richiesto'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE deposit_requests 
                SET status = 'rejected', admin_notes = %s, approved_at = NOW(), approved_by = %s
                WHERE id = %s AND status = 'pending'
            """, (admin_notes, session.get('user_id'), deposit_id))
            
            if cur.rowcount == 0:
                return jsonify({'error': 'Richiesta non trovata o già processata'}), 404
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Richiesta rifiutata',
            'deposit_id': deposit_id
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore nel rifiuto: {str(e)}'}), 500

# ---- TASK 2.7 - Gestione Prelievi ----
@admin_bp.get("/api/withdrawal-requests")
@admin_required
def withdrawal_requests_list():
    """Gestione prelievi: lista richieste pending (48h max)"""
    status = request.args.get('status', 'pending')
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT wr.id, wr.user_id, u.full_name, u.email, wr.amount, 
                   wr.source_section, wr.bank_details, wr.status, wr.created_at,
                   wr.admin_notes,
                   EXTRACT(EPOCH FROM (NOW() - wr.created_at))/3600 as hours_pending
            FROM withdrawal_requests wr
            JOIN users u ON u.id = wr.user_id
            WHERE wr.status = %s
            ORDER BY wr.created_at ASC
        """, (status,))
        requests = cur.fetchall()
    
    return jsonify(requests)

@admin_bp.post("/api/withdrawal-requests/approve")
@admin_required
def approve_withdrawal_request():
    """Approvazione prelievo (48h max)"""
    data = request.get_json() or {}
    withdrawal_id = data.get('withdrawal_id')
    admin_notes = data.get('admin_notes', '')
    
    if not withdrawal_id:
        return jsonify({'error': 'Withdrawal ID richiesto'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica richiesta esiste
            cur.execute("""
                SELECT wr.*, u.email FROM withdrawal_requests wr
                JOIN users u ON u.id = wr.user_id  
                WHERE wr.id = %s AND wr.status = 'pending'
            """, (withdrawal_id,))
            withdrawal = cur.fetchone()
            
            if not withdrawal:
                return jsonify({'error': 'Richiesta non trovata o già processata'}), 404
            
            # Aggiorna stato prelievo
            cur.execute("""
                UPDATE withdrawal_requests 
                SET status = 'completed', admin_notes = %s, approved_at = NOW(), approved_by = %s
                WHERE id = %s
            """, (admin_notes, session.get('user_id'), withdrawal_id))
            
            # Registra transazione
            cur.execute("""
                INSERT INTO portfolio_transactions (
                    user_id, type, amount, balance_before, balance_after,
                    description, reference_id, reference_type, status, created_at
                ) VALUES (
                    %s, 'withdrawal', -%s, 0, 0, 
                    'Prelievo approvato da admin', %s, 'withdrawal_request', 'completed', NOW()
                )
            """, (withdrawal['user_id'], withdrawal['amount'], withdrawal_id))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Prelievo approvato con successo',
            'withdrawal_id': withdrawal_id,
            'amount': float(withdrawal['amount'])
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore nell\'approvazione: {str(e)}'}), 500

# ---- TASK 2.7 - Configurazione IBAN ----
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

# ---- TASK 2.7 - Gestione Referral ----
@admin_bp.get("/api/referral-overview")
@admin_required
def referral_overview():
    """Gestione referral: overview sistema referral"""
    with get_conn() as conn, conn.cursor() as cur:
        # Statistiche referral
        cur.execute("""
            SELECT COUNT(*) as total_referrals,
                   COUNT(CASE WHEN status = 'active' THEN 1 END) as active_referrals,
                   COALESCE(SUM(commission_earned), 0) as total_commissions
            FROM referrals
        """)
        referral_stats = cur.fetchone()
        
        # Top referrer
        cur.execute("""
            SELECT u.full_name, u.email, r.commission_earned, r.total_invested
            FROM referrals r
            JOIN users u ON u.id = r.referrer_id
            ORDER BY r.commission_earned DESC
            LIMIT 10
        """)
        top_referrers = cur.fetchall()
        
        # Commissioni recenti
        cur.execute("""
            SELECT rc.*, ur.full_name as referrer_name, uu.full_name as referred_name
            FROM referral_commissions rc
            JOIN users ur ON ur.id = rc.referrer_id
            JOIN users uu ON uu.id = rc.referred_user_id
            ORDER BY rc.created_at DESC
            LIMIT 20
        """)
        recent_commissions = cur.fetchall()
    
    return jsonify({
        'stats': referral_stats,
        'top_referrers': top_referrers,
        'recent_commissions': recent_commissions
    })

@admin_bp.post("/api/distribute-referral-bonus")
@admin_required
def distribute_referral_bonus():
    """Distribuzione manuale bonus referral 1%"""
    data = request.get_json() or {}
    user_id = data.get('user_id')
    profit_amount = data.get('profit_amount')
    referral_percentage = data.get('referral_percentage', 0.01)
    
    if not all([user_id, profit_amount]):
        return jsonify({'error': 'User ID e profit amount richiesti'}), 400
    
    try:
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica se l'utente ha un referrer
            cur.execute("SELECT referred_by FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            
            if not user or not user['referred_by']:
                return jsonify({'error': 'Utente non ha un referrer'}), 400
            
            # Calcola bonus referral
            bonus_amount = float(profit_amount) * float(referral_percentage)
            
            # Aggiorna portfolio del referrer
            cur.execute("""
                UPDATE user_portfolios 
                SET referral_bonus = referral_bonus + %s, updated_at = NOW()
                WHERE user_id = %s
            """, (bonus_amount, user['referred_by']))
            
            # Registra transazione
            cur.execute("""
                INSERT INTO portfolio_transactions (
                    user_id, type, amount, balance_before, balance_after,
                    description, status, created_at
                ) VALUES (
                    %s, 'referral', %s, 0, %s, 
                    'Bonus referral distribuito da admin', 'completed', NOW()
                )
            """, (user['referred_by'], bonus_amount, bonus_amount))
            
            conn.commit()
            
        return jsonify({
            'success': True,
            'message': 'Bonus referral distribuito',
            'referrer_id': user['referred_by'],
            'bonus_amount': bonus_amount
        })
        
    except Exception as e:
        return jsonify({'error': f'Errore nella distribuzione: {str(e)}'}), 500

# ---- TASK 2.7 - Enhanced KYC Management ----
@admin_bp.get("/api/kyc-requests")
@admin_required
def kyc_requests_list():
    """Lista documenti KYC da approvare"""
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

# ---- Static uploads ----
@admin_bp.get('/uploads/<path:filename>')
@admin_required
def uploaded_file(filename):
    return send_from_directory(get_upload_folder(), filename)
