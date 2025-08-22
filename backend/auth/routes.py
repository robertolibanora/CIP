from flask import Blueprint, request, session, redirect, url_for, jsonify, render_template, current_app
from werkzeug.security import check_password_hash
import os

auth_bp = Blueprint("auth", __name__)

def get_db_connection():
    """Ottiene connessione al database"""
    from backend.shared.database import get_connection
    return get_connection()

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Verifica credenziali nel database
            cur.execute("""
                SELECT id, email, password_hash, full_name, role, kyc_status
                FROM users 
                WHERE email = %s
            """, (email,))
            
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            # Verifica password usando hash
            if user and check_password_hash(user['password_hash'], password):
                # Login riuscito
                session['user_id'] = user['id']
                session['email'] = user['email']
                session['role'] = user['role']
                session['full_name'] = user['full_name']
                
                current_app.logger.info(f"Login riuscito per utente: {email} (ID: {user['id']})")
                
                # Redirect in base al ruolo
                if user['role'] == 'admin':
                    return redirect(url_for('admin.admin_dashboard'))
                else:
                    return redirect(url_for('user.dashboard'))
            else:
                current_app.logger.warning(f"Tentativo di login fallito per: {email}")
                return render_template("auth/login.html", error="Credenziali non valide")
                
        except Exception as e:
            current_app.logger.error(f"Errore durante il login: {str(e)}")
            return render_template("auth/login.html", error="Errore interno del server")
    
    return render_template("auth/login.html")

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        full_name = request.form.get("full_name")
        
        # Simuliamo registrazione
        if email and password and full_name:
            session['user_id'] = 2  # Nuovo utente
            session['email'] = email
            session['role'] = 'investor'
            return redirect(url_for('user.dashboard'))
        
        return render_template("auth/register.html", error="Dati mancanti")
    
    return render_template("auth/register.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))

@auth_bp.route("/profile")
def profile():
    # Verifica sessione utente
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template("auth/profile.html")
