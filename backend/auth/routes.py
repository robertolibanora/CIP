from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from backend.shared.database import get_connection
from backend.shared.validators import validate_email, validate_password
import hashlib

auth_bp = Blueprint("auth", __name__)


def get_conn():
    return get_connection()


def hash_password(password: str) -> str:
    """Hash della password per sicurezza (SHA-256)."""
    return hashlib.sha256(password.encode()).hexdigest()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Login utente"""
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if not email or not password:
            flash("Email e password sono richiesti", "error")
            return render_template("auth/login.html")

        with get_conn() as conn, conn.cursor() as cur:
            # Cerca utente per email
            cur.execute(
                """
                SELECT id, email, nome, cognome, password_hash, role
                FROM users WHERE email = %s
                """,
                (email,),
            )
            user = cur.fetchone()

            # Verifica password con hash
            if user and user["password_hash"] == hash_password(password):
                session["user_id"] = user["id"]
                session["user_role"] = user["role"]
                session["user_name"] = (
                    f"{user['nome']} {user['cognome']}" if user["nome"] and user["cognome"] else user["email"]
                )

                flash(f"Benvenuto, {session['user_name']}!", "success")

                # Reindirizza admin alla dashboard admin, utenti normali alla dashboard utente
                if user["role"] == "admin":
                    return redirect(url_for("admin.dashboard"))
                else:
                    return redirect(url_for("user.dashboard"))
            else:
                flash("Credenziali non valide", "error")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registrazione nuovo utente"""
    if request.method == "POST":
        nome = request.form.get("nome")
        cognome = request.form.get("cognome")
        nome_telegram = request.form.get("nome_telegram")
        telefono = request.form.get("telefono")
        email = request.form.get("email")
        referral_link = request.form.get("referral_link")
        password = request.form.get("password")

        # Validazione
        if not all([nome, cognome, nome_telegram, telefono, email, password]):
            flash("Tutti i campi obbligatori sono richiesti", "error")
            return render_template("auth/register.html")

        if not validate_email(email):
            flash("Email non valida", "error")
            return render_template("auth/register.html")

        if not validate_password(password):
            flash("Password deve essere di almeno 6 caratteri", "error")
            return render_template("auth/register.html")

        with get_conn() as conn, conn.cursor() as cur:
            # Verifica email duplicata
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("Email già registrata", "error")
                return render_template("auth/register.html")

            # Verifica nome telegram duplicato
            cur.execute("SELECT id FROM users WHERE nome_telegram = %s", (nome_telegram,))
            if cur.fetchone():
                flash("Nome Telegram già registrato", "error")
                return render_template("auth/register.html")

            # Trova utente referral se link fornito
            referred_by = None
            if referral_link:
                cur.execute("SELECT id FROM users WHERE referral_code = %s", (referral_link,))
                row = cur.fetchone()
                if row:
                    referred_by = row["id"]

            # Genera codice referral unico
            import uuid

            new_referral_code = str(uuid.uuid4())[:8].upper()

            # Inserisci nuovo utente con hash password
            cur.execute(
                """
                INSERT INTO users (nome, cognome, nome_telegram, telefono, email, password_hash, referral_code, referral_link, referred_by, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (
                    nome,
                    cognome,
                    nome_telegram,
                    telefono,
                    email,
                    hash_password(password),
                    new_referral_code,
                    referral_link,
                    referred_by,
                ),
            )

            new_user_id = cur.fetchone()["id"]

            # Se c'è referral, crea bonus
            if referred_by:
                cur.execute(
                    """
                    INSERT INTO referral_bonuses (receiver_user_id, source_user_id, amount, month_ref, level, status, created_at)
                    VALUES (%s, %s, %s, DATE_TRUNC('month', NOW())::date, %s, 'accrued', NOW())
                    """,
                    (referred_by, new_user_id, 50, 1),
                )

            conn.commit()

            flash("Registrazione completata! Ora puoi fare login.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/logout")
def logout():
    """Logout utente"""
    session.clear()
    flash("Logout completato", "success")
    return redirect(url_for("auth.login"))
