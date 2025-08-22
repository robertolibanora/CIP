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
