from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from backend.shared.database import get_connection
import os
from backend.shared.validators import validate_email, validate_password, ValidationError
from backend.auth.middleware import create_secure_session, destroy_session
from backend.utils.http import is_api_request
import hashlib

auth_bp = Blueprint("auth", __name__)


def get_conn():
    return get_connection()


def hash_password(password: str) -> str:
    """Hash della password per sicurezza (SHA-256)."""
    return hashlib.sha256(password.encode()).hexdigest()


from backend.auth.decorators import guest_only

@auth_bp.route("/login", methods=["GET", "POST"])
@guest_only
def login():
    """Login utente - supporta form HTML e JSON"""
    print(f"LOGIN: Method={request.method}, Form data={dict(request.form)}")
    
    if request.method == "GET":
        return render_template("auth/login.html")
    
    # POST - gestisce sia form che JSON
    if request.is_json:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
    else:
        email = request.form.get("email")
        password = request.form.get("password")
    
    print(f"LOGIN: Email={email}, Password={'*' * len(password) if password else 'None'}")

    if not email or not password:
        if is_api_request():
            return jsonify({"error": "Email e password sono richiesti"}), 400
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
            # Crea sessione sicura
            print(f"LOGIN: Creazione sessione per {user['email']}")
            create_secure_session(user)

            # Se è richiesta API, restituisce JSON
            if is_api_request():
                return jsonify({
                    "ok": True,
                    "user": {
                        "id": user["id"],
                        "email": user["email"],
                        "nome": user["nome"],
                        "cognome": user["cognome"],
                        "role": user["role"]
                    }
                }), 200

            # Altrimenti, redirect HTML
            flash(f"Benvenuto, {user['nome']} {user['cognome']}!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin.admin_dashboard"))
            else:
                return redirect(url_for("user.dashboard"))
        else:
            if is_api_request():
                return jsonify({"error": "Credenziali non valide"}), 401
            flash("Credenziali non valide", "error")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@guest_only
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

        try:
            validate_email(email)
        except ValidationError as e:
            flash(str(e), "error")
            return render_template("auth/register.html")

        try:
            validate_password(password)
        except ValidationError as e:
            flash(str(e), "error")
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
    """Logout utente con pulizia completa sessione"""
    if 'user_id' in session:
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'Utente')
        
        # Distrugge sessione in modo sicuro
        destroy_session()
        
        flash(f"Logout completato per {user_name}", "success")
        # logger.info(f"Logout utente {user_id}") # This line was commented out in the original file, so it's commented out here.
    else:
        flash("Nessuna sessione attiva", "info")
    
    return redirect(url_for("auth.login"))


# Route di supporto solo in testing per creare una sessione senza DB
if os.environ.get("TESTING") == "1":
    @auth_bp.get("/test-login")
    def test_login():
        role = (request.args.get("role") or "investor").strip()
        user = {
            "id": 9999,
            "email": f"test_{role}@example.com",
            "nome": "Test",
            "cognome": "User",
            "role": role,
        }
        create_secure_session(user)
        # Allinea anche la chiave 'role' usata dal middleware
        from flask import session as flask_session
        flask_session["role"] = role
        return redirect(url_for("user.dashboard"))

    @auth_bp.get("/test-logout")
    def test_logout():
        destroy_session()
        return redirect(url_for("auth.login"))
