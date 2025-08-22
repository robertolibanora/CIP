# CIP Immobiliare — Codice Completo (Flask + Postgres)

## admin.py
```python
import os
import uuid
from datetime import datetime
from flask import Flask, Blueprint, request, redirect, url_for, session, abort, send_from_directory, jsonify
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev")
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# -----------------------------
# DB
# -----------------------------

def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL non impostata")
    return psycopg.connect(dsn, row_factory=dict_row)

# -----------------------------
# AUTH BLUEPRINT
# -----------------------------
from auth import auth_bp  # type: ignore
app.register_blueprint(auth_bp)

# -----------------------------
# ADMIN BLUEPRINT (protected)
# -----------------------------
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

@admin_bp.before_request
def require_admin():
    if request.endpoint and request.endpoint.startswith('auth.'):
        return
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    if session.get('role') != 'admin':
        abort(403)

@admin_bp.get("/")
def admin_dashboard():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_admin_metrics")
        m = cur.fetchone()
    return jsonify(m or {})

@admin_bp.get("/metrics")
def metrics():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM v_admin_metrics")
        m = cur.fetchone()
    return jsonify(m or {})

# ---- Gestione Progetti ----
@admin_bp.get("/projects")
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
def user_change_referrer(uid):
    data = request.form or request.json or {}
    referred_by = data.get('referred_by')
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET referred_by=%s WHERE id=%s", (referred_by, uid))
    return jsonify({"ok": True})

@admin_bp.get("/users/<int:uid>/bonuses")
@admin_bp.post("/users/<int:uid>/bonuses")
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
def investment_confirm_wire(iid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE investments SET status='active', activated_at=NOW() WHERE id=%s", (iid,))
    return jsonify({"status": "active"})

@admin_bp.post("/investments/<int:iid>/yield")
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
def requests_reject(rid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE investment_requests SET state='rejected', updated_at=NOW() WHERE id=%s", (rid,))
    return jsonify({"rejected_request": rid})

# ---- KYC ----
@admin_bp.post("/kyc/<int:uid>/verify")
def kyc_verify(uid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET kyc_status='verified' WHERE id=%s", (uid,))
    return jsonify({"kyc_status": "verified"})

@admin_bp.post("/kyc/<int:uid>/reject")
def kyc_reject(uid):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE users SET kyc_status='rejected' WHERE id=%s", (uid,))
    return jsonify({"kyc_status": "rejected"})

# ---- Documenti (admin) ----
@admin_bp.get("/documents")
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
def admin_documents_upload():
    user_id = request.form.get('user_id')
    category_id = request.form.get('category_id')
    title = request.form.get('title')
    file = request.files.get('file')
    if not (user_id and category_id and file):
        abort(400)
    filename = secure_filename(file.filename)
    path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uuid.uuid4()}-{filename}")
    file.save(path)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO documents(user_id, category_id, title, file_path, visibility)
            VALUES (%s,%s,%s,%s,%s) RETURNING id
        """, (user_id, category_id, title or filename, path, request.form.get('visibility','admin')))
        did = cur.fetchone()['id']
    return jsonify({"id": did, "file_path": path})

@admin_bp.post("/documents/<int:doc_id>/visibility")
def admin_documents_visibility(doc_id):
    visibility = request.form.get('visibility', 'private')
    verified = request.form.get('verified_by_admin')
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE documents SET visibility=%s, verified_by_admin=COALESCE(%s, verified_by_admin) WHERE id=%s",
                    (visibility, True if verified in ('1','true','True') else None, doc_id))
    return jsonify({"updated": True})

# ---- Sistema Notifiche ----
@admin_bp.post("/notifications/new")
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
@admin_bp.post("/notifications/templates")
@admin_bp.post("/notifications/templates/<int:tid>/edit")
@admin_bp.post("/notifications/templates/<int:tid>/delete")
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

# ---- Register blueprints ----
app.register_blueprint(admin_bp)

# ---- Static uploads ----
@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---- USER BLUEPRINT ----
from user import user_bp  # type: ignore
app.register_blueprint(user_bp)

if __name__ == "__main__":
    app.run(debug=True)
```

## user.py
```python
import os
import uuid
from flask import Blueprint, request, session, redirect, url_for, jsonify
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

load_dotenv()
user_bp = Blueprint("user", __name__, url_prefix="/")

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    return psycopg.connect(dsn, row_factory=dict_row)

@user_bp.before_request
def require_login():
    # Skip for auth pages handled in auth blueprint
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

# --- Dashboard Principale ---
@user_bp.get("/")
def dashboard():
    uid = session.get("user_id")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT total_invested, active_count FROM v_user_invested WHERE user_id=%s", (uid,))
        inv = cur.fetchone() or {"total_invested": 0, "active_count": 0}
        cur.execute("SELECT COALESCE(SUM(amount),0) AS total_yields FROM investment_yields iy JOIN investments i ON i.id=iy.investment_id WHERE i.user_id=%s", (uid,))
        yields = cur.fetchone()
        cur.execute("SELECT bonus_total FROM v_user_bonus WHERE user_id=%s", (uid,))
        bonus = cur.fetchone()
    return jsonify({
        "total_invested": inv.get('total_invested',0),
        "active_investments": inv.get('active_count',0),
        "total_yields": (yields and yields['total_yields'] or 0),
        "referral_bonus": (bonus and bonus['bonus_total'] or 0)
    })

# --- Portafoglio ---
@user_bp.get("/portfolio")
def portfolio():
    uid = session.get("user_id")
    tab = request.args.get("tab", "attivi")
    statuses = ('active',) if tab == 'attivi' else ('completed','cancelled','rejected')
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.id, p.title, i.amount, i.status, i.created_at
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.user_id=%s AND i.status = ANY(%s)
            ORDER BY i.created_at DESC
        """, (uid, list(statuses)))
        rows = cur.fetchall()
    return jsonify({"tab": tab, "items": rows})

@user_bp.get("/portfolio/<int:investment_id>")
def portfolio_detail(investment_id):
    uid = session.get("user_id")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT i.*, p.title AS project_title
            FROM investments i JOIN projects p ON p.id=i.project_id
            WHERE i.id=%s AND i.user_id=%s
        """, (investment_id, uid))
        inv = cur.fetchone()
        cur.execute("SELECT * FROM investment_yields WHERE investment_id=%s ORDER BY period_end DESC", (investment_id,))
        y = cur.fetchall()
    return jsonify({"investment": inv, "yields": y})

# --- Richieste Investimento (wizard semplificato) ---
@user_bp.get("/requests")
def requests_list():
    uid = session.get("user_id")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT r.id, p.title AS project, r.amount, r.state, r.created_at
            FROM investment_requests r JOIN projects p ON p.id=r.project_id
            WHERE r.user_id=%s ORDER BY r.created_at DESC
        """, (uid,))
        rows = cur.fetchall()
    return jsonify(rows)

@user_bp.route("/requests/new", methods=["GET","POST"])
def requests_new():
    if request.method == "GET":
        step = int(request.args.get('step', 1))
        return jsonify({"step": step})
    # POST final submit
    uid = session.get("user_id")
    project_id = request.form.get("project_id") or (request.json and request.json.get('project_id'))
    amount = request.form.get("amount") or (request.json and request.json.get('amount'))
    file = request.files.get("cro") if 'cro' in request.files else None
    cro_path = None
    if file and file.filename:
        filename = secure_filename(file.filename)
        cro_path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}-{filename}")
        file.save(cro_path)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO investment_requests(user_id, project_id, amount, cro_file_path) VALUES (%s,%s,%s,%s) RETURNING id",
            (uid, project_id, amount, cro_path)
        )
        rid = cur.fetchone()['id']
    return jsonify({"request_id": rid, "state": "in_review"})

# --- Documenti & KYC ---
@user_bp.route("/documents", methods=["GET","POST"])
def documents():
    uid = session.get("user_id")
    if request.method == 'POST':
        category_id = request.form.get('category_id')
        title = request.form.get('title')
        file = request.files.get('file')
        if not (category_id and file):
            return ("bad request", 400)
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, f"{uuid.uuid4()}-{filename}")
        file.save(path)
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO documents(user_id,category_id,title,file_path) VALUES (%s,%s,%s,%s) RETURNING id",
                        (uid, category_id, title or filename, path))
            did = cur.fetchone()['id']
        return jsonify({"id": did, "file_path": path})
    # GET
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT d.*, c.slug, c.name FROM documents d JOIN doc_categories c ON c.id=d.category_id WHERE d.user_id=%s ORDER BY d.uploaded_at DESC", (uid,))
        docs = cur.fetchall()
    return jsonify(docs)

@user_bp.get("/documents/categories")
def doc_categories():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM doc_categories ORDER BY name")
        cats = cur.fetchall()
    return jsonify(cats)

# --- Bonus Immobiliari ---
@user_bp.get("/bonuses")
def bonuses():
    uid = session.get("user_id")
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM referral_bonuses WHERE receiver_user_id=%s ORDER BY month_ref DESC", (uid,))
        rows = cur.fetchall()
        cur.execute("SELECT date_trunc('month', month_ref) AS month, SUM(amount) AS total FROM referral_bonuses WHERE receiver_user_id=%s GROUP BY 1 ORDER BY 1 DESC", (uid,))
        monthly = cur.fetchall()
    return jsonify({"items": rows, "monthly": monthly})

# --- Struttura Immobiliare (Referral) ---
@user_bp.get("/network")
@user_bp.get("/network/stats")
@user_bp.get("/network/edges")
def network():
    uid = session.get("user_id")
    path = request.path
    with get_conn() as conn, conn.cursor() as cur:
        if path.endswith('/stats'):
            cur.execute("""
                WITH RECURSIVE tree AS (
                  SELECT id, referred_by, 1 AS level FROM users WHERE referred_by = %s
                  UNION ALL
                  SELECT u.id, u.referred_by, t.level+1 FROM users u
                  JOIN tree t ON u.referred_by = t.id
                ) SELECT level, COUNT(*) AS count FROM tree GROUP BY level ORDER BY level
            """, (uid,))
            return jsonify(cur.fetchall())
        if path.endswith('/edges'):
            cur.execute("SELECT id FROM users WHERE id=%s", (uid,))
            cur.execute("""
                WITH RECURSIVE tree AS (
                  SELECT id, referred_by FROM users WHERE referred_by = %s
                  UNION ALL
                  SELECT u.id, u.referred_by FROM users u JOIN tree t ON u.referred_by = t.id
                ) SELECT referred_by AS source, id AS target FROM tree
            """, (uid,))
            return jsonify(cur.fetchall())
        cur.execute("""
            WITH RECURSIVE tree AS (
              SELECT id, referred_by, 1 AS level FROM users WHERE referred_by = %s
              UNION ALL
              SELECT u.id, u.referred_by, t.level+1 FROM users u
              JOIN tree t ON u.referred_by = t.id
            ) SELECT * FROM tree ORDER BY level
        """, (uid,))
        return jsonify(cur.fetchall())

# --- Notifiche ---
@user_bp.get("/notifications")
def notifications():
    uid = session.get("user_id")
    priority = request.args.get('priority')
    is_read = request.args.get('is_read')
    q = ["user_id=%s"]; params = [uid]
    if priority: q.append("priority=%s"); params.append(priority)
    if is_read is not None:
        q.append("is_read=%s"); params.append(is_read.lower() in ('1','true','yes'))
    where = " AND ".join(q)
    sql = f"SELECT * FROM notifications WHERE {where} ORDER BY created_at DESC"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify(rows)

@user_bp.post("/notifications/bulk")
def notifications_bulk():
    uid = session.get("user_id")
    data = request.json or request.form
    ids = data.get('ids')
    action = data.get('action')  # mark_read | mark_unread
    if not ids or action not in ('mark_read','mark_unread'):
        return ("bad request", 400)
    is_read = True if action == 'mark_read' else False
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("UPDATE notifications SET is_read=%s WHERE user_id=%s AND id = ANY(%s)", (is_read, uid, ids))
    return jsonify({"updated": len(ids)})

# --- Preferenze ---
@user_bp.route("/preferences", methods=["GET","POST"])
def preferences():
    uid = session.get("user_id")
    if request.method == 'POST':
        data = request.form or request.json or {}
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET full_name=COALESCE(%s,full_name), email=COALESCE(%s,email), phone=COALESCE(%s,phone), address=COALESCE(%s,address), currency_code=COALESCE(%s,currency_code) WHERE id=%s",
                        (data.get('full_name'), data.get('email'), data.get('phone'), data.get('address'), data.get('currency_code'), uid))
        return jsonify({"updated": True})
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT full_name,email,phone,address,currency_code FROM users WHERE id=%s", (uid,))
        row = cur.fetchone()
    return jsonify(row)
```

## auth.py
```python
import os
from flask import Blueprint, request, session, redirect, url_for, jsonify
import psycopg
from psycopg.rows import dict_row
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

load_dotenv()
auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

def get_conn():
    dsn = os.environ.get("DATABASE_URL")
    return psycopg.connect(dsn, row_factory=dict_row)

@auth_bp.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email") or (request.json and request.json.get('email'))
        password = request.form.get("password") or (request.json and request.json.get('password'))
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT id, password_hash, role FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            return jsonify({"ok": True})
        return ("invalid", 401)
    return ("login", 200)

@auth_bp.get("/me")
def me():
    if 'user_id' not in session:
        return ("unauthenticated", 401)
    return jsonify({"user_id": session['user_id'], "role": session.get('role')})

@auth_bp.get("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["POST"])
def register():
    email = request.form.get("email") or (request.json and request.json.get('email'))
    password = request.form.get("password") or (request.json and request.json.get('password'))
    full_name = request.form.get("full_name") or (request.json and request.json.get('full_name'))
    if not email or not password:
        return ("bad request", 400)
    hashed = generate_password_hash(password)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users(email,password_hash,full_name,role) VALUES (%s,%s,%s,'investor') RETURNING id",
                    (email, hashed, full_name))
        uid = cur.fetchone()['id']
    return jsonify({"id": uid})
```

