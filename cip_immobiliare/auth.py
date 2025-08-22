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
