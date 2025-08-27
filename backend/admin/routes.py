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

@admin_bp.post("/projects/<int:pid>/edit")
@admin_required
def projects_edit(pid):
    data = request.form or request.json or {}
    fields = [
        ('title','title'),('description','description'),('status','status'),
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

# ---- Gestione Utenti ----
@admin_bp.get("/users")
@admin_required
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
        SELECT i.id, u.full_name, p.title, i.amount, i.status, i.created_at
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
            SELECT i.*, u.full_name, p.title AS project_title
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
            SELECT r.id, u.full_name, p.title AS project, r.amount, r.state, r.created_at
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
