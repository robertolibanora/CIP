from flask import Blueprint, request, session, redirect, url_for, render_template, flash
from backend.shared.database import get_connection
from backend.shared.validators import validate_email, validate_password

auth_bp = Blueprint("auth", __name__)

def get_conn():
    return get_connection()

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
            cur.execute("""
                SELECT id, email, full_name, password_hash, role
                FROM users WHERE email = %s
            """, (email,))
            user = cur.fetchone()
            
            if user and user['password_hash'] == password:  # TODO: hash reale
                session['user_id'] = user['id']
                session['user_role'] = user['role']
                flash(f"Benvenuto, {user['full_name']}!", "success")
                return redirect(url_for("user.dashboard"))
            else:
                flash("Credenziali non valide", "error")
    
    return render_template("auth/login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registrazione nuovo utente"""
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        password = request.form.get("password")
        referral_code = request.args.get("ref")  # Codice referral dall'URL
        
        # Validazione
        if not all([full_name, email, password]):
            flash("Tutti i campi sono richiesti", "error")
            return render_template("auth/register.html")
        
        if not validate_email(email):
            flash("Email non valida", "error")
            return render_template("auth/register.html")
        
        if not validate_password(password):
            flash("Password deve essere di almeno 8 caratteri", "error")
            return render_template("auth/register.html")
        
        with get_conn() as conn, conn.cursor() as cur:
            # Verifica email duplicata
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("Email già registrata", "error")
                return render_template("auth/register.html")
            
            # Trova utente referral se codice fornito
            referred_by = None
            if referral_code:
                cur.execute("SELECT id FROM users WHERE referral_code = %s", (referral_code,))
                referred_by = cur.fetchone()
                if referred_by:
                    referred_by = referred_by['id']
            
            # Genera codice referral unico
            import uuid
            new_referral_code = str(uuid.uuid4())[:8].upper()
            
            # Inserisci nuovo utente
            cur.execute("""
                INSERT INTO users (full_name, email, password_hash, referral_code, referred_by, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                RETURNING id
            """, (full_name, email, password, new_referral_code, referred_by))
            
            new_user_id = cur.fetchone()['id']
            
            # Se c'è referral, crea bonus
            if referred_by:
                cur.execute("""
                    INSERT INTO referral_bonuses (referrer_user_id, receiver_user_id, amount, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (referred_by, new_user_id, 50))  # Bonus fisso di €50
            
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
