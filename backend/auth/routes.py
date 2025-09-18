from flask import Blueprint, request, session, redirect, url_for, render_template, flash, jsonify
from backend.shared.database import get_connection
import os
from backend.shared.validators import validate_email, validate_password, ValidationError
from backend.auth.middleware import create_secure_session, destroy_session
from backend.utils.http import is_api_request
import hashlib

auth_bp = Blueprint("auth", __name__)


def get_conn():
    from backend.shared.database import get_connection
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

    conn = get_conn()
    cur = conn.cursor()
    
    try:
        # Cerca utente per email
        cur.execute(
            """
            SELECT id, email, nome, cognome, password_hash, role
            FROM users WHERE email = %s
            """,
            (email,),
        )
        user = cur.fetchone()
        # PostgreSQL restituisce già dict con row_factory

        # Verifica password con hash SHA-256
        if user and user["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
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
    
    finally:
        conn.close()

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@guest_only
def register():
    """Registrazione nuovo utente"""
    # Gestisci parametro referral dall'URL
    referral_code_from_url = request.args.get('ref', '').strip()
    
    if request.method == "POST":
        nome = request.form.get("nome")
        cognome = request.form.get("cognome")
        nome_telegram = request.form.get("nome_telegram")
        telefono = request.form.get("telefono")
        email = request.form.get("email")
        referral_link = request.form.get("referral_link") or referral_code_from_url
        password = request.form.get("password")

        # Validazione
        if not all([nome, cognome, nome_telegram, telefono, email, password]):
            flash("Tutti i campi obbligatori sono richiesti", "error")
            return render_template("auth/register.html", 
                                 referral_code_from_url=referral_code_from_url,
                                 form_data={
                                     'nome': nome,
                                     'cognome': cognome,
                                     'nome_telegram': nome_telegram,
                                     'telefono': telefono,
                                     'email': email,
                                     'referral_link': referral_link
                                 })

        try:
            validate_email(email)
        except ValidationError as e:
            flash(str(e), "error")
            return render_template("auth/register.html", 
                                 referral_code_from_url=referral_code_from_url,
                                 form_data={
                                     'nome': nome,
                                     'cognome': cognome,
                                     'nome_telegram': nome_telegram,
                                     'telefono': telefono,
                                     'email': '',  # Svuota solo l'email
                                     'referral_link': referral_link
                                 })

        try:
            validate_password(password)
        except ValidationError as e:
            flash(str(e), "error")
            return render_template("auth/register.html", 
                                 referral_code_from_url=referral_code_from_url,
                                 form_data={
                                     'nome': nome,
                                     'cognome': cognome,
                                     'nome_telegram': nome_telegram,
                                     'telefono': telefono,
                                     'email': '',  # Svuota solo l'email
                                     'referral_link': referral_link
                                 })

        with get_conn() as conn, conn.cursor() as cur:
            # Verifica email duplicata
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("Email già registrata", "error")
                return render_template("auth/register.html", 
                                     referral_code_from_url=referral_code_from_url,
                                     form_data={
                                         'nome': nome,
                                         'cognome': cognome,
                                         'nome_telegram': nome_telegram,
                                         'telefono': telefono,
                                         'email': '',  # Svuota solo l'email
                                         'referral_link': referral_link
                                     })

            # Verifica nome telegram duplicato
            cur.execute("SELECT id FROM users WHERE nome_telegram = %s", (nome_telegram,))
            if cur.fetchone():
                flash("Nome Telegram già registrato", "error")
                return render_template("auth/register.html", 
                                     referral_code_from_url=referral_code_from_url,
                                     form_data={
                                         'nome': nome,
                                         'cognome': cognome,
                                         'nome_telegram': '',  # Svuota solo il telegram
                                         'telefono': telefono,
                                         'email': email,
                                         'referral_link': referral_link
                                     })

            # Trova utente referral
            referred_by = None
            if referral_link:
                # Se l'utente ha inserito un codice, validalo
                cur.execute("SELECT id FROM users WHERE referral_code = %s", (referral_link,))
                row = cur.fetchone()
                if row:
                    referred_by = row["id"]
                else:
                    flash("Codice referral non valido", "error")
                    return render_template("auth/register.html", 
                                         referral_code_from_url=referral_code_from_url,
                                         form_data={
                                             'nome': nome,
                                             'cognome': cognome,
                                             'nome_telegram': nome_telegram,
                                             'telefono': telefono,
                                             'email': email,
                                             'referral_link': ''  # Svuota solo il referral
                                         })
            else:
                # Nessun referral inserito: assegna al primo utente 'investor' (non admin)
                cur.execute(
                    """
                    SELECT id FROM users 
                    WHERE role = 'investor' 
                    AND referral_code IS NOT NULL 
                    ORDER BY created_at ASC 
                    LIMIT 1
                    """
                )
                first_investor_row = cur.fetchone()
                if first_investor_row:
                    referred_by = first_investor_row["id"]
                else:
                    # Fallback: se non ci sono utenti investor, usa il primo utente disponibile (escluso admin)
                    cur.execute(
                        """
                        SELECT id FROM users 
                        WHERE role != 'admin' 
                        AND referral_code IS NOT NULL 
                        ORDER BY created_at ASC 
                        LIMIT 1
                        """
                    )
                    fallback_row = cur.fetchone()
                    if fallback_row:
                        referred_by = fallback_row["id"]

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

            # Se c'è referral, crea bonus (se la tabella esiste)
            if referred_by:
                cur.execute("SELECT to_regclass('public.referral_bonuses') AS tbl_exists")
                tbl = cur.fetchone()
                tbl_exists = tbl and (tbl.get('tbl_exists') is not None if isinstance(tbl, dict) else tbl[0] is not None)
                if tbl_exists:
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

    return render_template("auth/register.html", referral_code_from_url=referral_code_from_url)


@auth_bp.route("/logout")
def logout():
    """Logout utente con pulizia completa sessione"""
    if 'user_id' in session:
        user_id = session.get('user_id')
        user_name = session.get('user_name', 'Utente')
        user_role = session.get('user_role', 'investor')
        
        # Se è un admin, elimina tutte le notifiche prima del logout
        if user_role == 'admin':
            try:
                from backend.shared.database import get_connection
                with get_connection() as conn, conn.cursor() as cur:
                    cur.execute("DELETE FROM admin_notifications")
                    conn.commit()
                    print(f"Notifiche eliminate per logout admin {user_id}")
            except Exception as e:
                print(f"Errore eliminazione notifiche al logout: {e}")
        
        # Distrugge sessione in modo sicuro
        destroy_session()
        
        flash(f"Logout completato per {user_name}", "success")
        # logger.info(f"Logout utente {user_id}") # This line was commented out in the original file, so it's commented out here.
    else:
        flash("Nessuna sessione attiva", "info")
    
    return redirect(url_for("auth.login"))


@auth_bp.route("/check", methods=["GET"])
def check_auth():
    """Verifica stato autenticazione e permessi utente"""
    if 'user_id' not in session:
        return jsonify({
            "authenticated": False,
            "is_admin": False,
            "user": None
        }), 401
    
    user_id = session.get('user_id')
    user_role = session.get('role', 'investor')
    
    return jsonify({
        "authenticated": True,
        "is_admin": user_role == 'admin',
        "user": {
            "id": user_id,
            "email": session.get('user_email'),
            "nome": session.get('user_name'),
            "cognome": session.get('user_surname'),
            "role": user_role
        }
    }), 200


@auth_bp.get("/referral/validate")
def validate_referral_code():
    """Valida un codice referral e restituisce nome/cognome associati."""
    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"valid": False, "error": "missing_code"}), 400

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT id, nome, cognome FROM users WHERE referral_code = %s", (code,))
        row = cur.fetchone()
        if not row:
            return jsonify({"valid": False}), 200
        return jsonify({
            "valid": True,
            "user": {
                "id": row["id"],
                "nome": row["nome"],
                "cognome": row["cognome"]
            }
        }), 200


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


@auth_bp.route("/terms")
def terms():
    """Pagina Termini e Condizioni"""
    return render_template("auth/terms.html")


@auth_bp.route("/privacy")
def privacy():
    """Pagina Privacy Policy"""
    return render_template("auth/privacy.html")
