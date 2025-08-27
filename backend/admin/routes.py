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

@admin_bp.get("/users/<int:uid>/bonuses")
@admin_required
@admin_bp.post("/users/<int:uid>/bonuses")
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

@admin_bp.get("/notifications/templates")
@admin_required
@admin_bp.post("/notifications/templates")
@admin_required
@admin_bp.post("/notifications/templates/<int:tid>/edit")
@admin_required
@admin_bp.post("/notifications/templates/<int:tid>/delete")
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
    if request.path.endswith('/delete'):
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM notification_templates WHERE id=%s", (tid,))
        return jsonify({"deleted": tid})
    data = request.form or request.json or {}
    if tid and request.path.endswith('/edit'):
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

# ---- Static uploads ----
@admin_bp.get('/uploads/<path:filename>')
@admin_required
def uploaded_file(filename):
    return send_from_directory(get_upload_folder(), filename)
