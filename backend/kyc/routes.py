"""
KYC API routes
API per gestione KYC: Upload, verifica, stati
"""

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, session, jsonify, current_app, render_template
from werkzeug.utils import secure_filename
from backend.shared.database import get_connection
from backend.auth.decorators import login_required, admin_required

kyc_bp = Blueprint("kyc", __name__)

def get_conn():
    return get_connection()

def get_upload_folder():
    """Ottiene la cartella upload dalla configurazione Flask"""
    return current_app.config.get('UPLOAD_FOLDER', 'uploads')

def allowed_file(filename):
    """Verifica se il file è di tipo consentito"""
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# =====================================================
# 1. KYC API - Upload, verifica, stati
# =====================================================

@kyc_bp.route('/api/status', methods=['GET'])
@login_required
def get_kyc_status():
    """Ottiene lo stato KYC dell'utente corrente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT kyc_status, created_at 
            FROM users 
            WHERE id = %s
        """, (uid,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404
        
        # Ottieni documenti KYC dell'utente
        cur.execute("""
            SELECT d.id, d.title, d.file_path, d.verified_by_admin, d.uploaded_at,
                   dc.name as category_name, dc.slug as category_slug
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
            ORDER BY d.uploaded_at DESC
        """, (uid,))
        documents = cur.fetchall()
        
        # Calcola stato complessivo
        kyc_status = user['kyc_status']
        has_documents = len(documents) > 0
        all_verified = all(doc['verified_by_admin'] for doc in documents) if documents else False
        
        # Aggiorna stato se necessario
        if kyc_status == 'unverified' and has_documents:
            new_status = 'pending'
            cur.execute("UPDATE users SET kyc_status = %s WHERE id = %s", (new_status, uid))
            kyc_status = new_status
        elif kyc_status == 'pending' and all_verified and has_documents:
            new_status = 'verified'
            cur.execute("UPDATE users SET kyc_status = %s WHERE id = %s", (new_status, uid))
            kyc_status = new_status
        
        conn.commit()
    
    return jsonify({
        'kyc_status': kyc_status,
        'has_documents': has_documents,
        'all_verified': all_verified,
        'documents': documents,
        'can_invest': kyc_status == 'verified'
    })

@kyc_bp.route('/api/documents', methods=['GET'])
@login_required
def get_kyc_documents():
    """Ottiene tutti i documenti KYC dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT d.id, d.title, d.file_path, d.verified_by_admin, d.uploaded_at,
                   dc.name as category_name, dc.slug as category_slug
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
            ORDER BY d.uploaded_at DESC
        """, (uid,))
        documents = cur.fetchall()
    
    return jsonify({'documents': documents})

@kyc_bp.route('/api/documents/upload', methods=['POST'])
@login_required
def upload_kyc_document():
    """Upload di un documento KYC"""
    uid = session.get("user_id")
    
    # Verifica se è già verificato
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT kyc_status FROM users WHERE id = %s", (uid,))
        user = cur.fetchone()
        if user and user['kyc_status'] == 'verified':
            return jsonify({'error': 'Utente già verificato'}), 400
    
    # Validazione file - supporta file multipli (fronte obbligatorio, retro opzionale)
    front_file = request.files.get('file')  # File principale (fronte)
    back_file = request.files.get('file_back')  # File retro (opzionale)
    
    if not front_file or front_file.filename == '':
        return jsonify({'error': 'File fronte del documento è obbligatorio'}), 400
    
    files_to_upload = [('front', front_file)]
    if back_file and back_file.filename != '':
        files_to_upload.append(('back', back_file))
    
    # Validazione per tutti i file
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    for file_type, file in files_to_upload:
        if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
            return jsonify({'error': f'Tipo file non supportato per {file_type}. Usa PDF o immagini'}), 400
        
        # Validazione dimensione (max 16MB)
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 16 * 1024 * 1024:  # 16MB
            return jsonify({'error': f'File {file_type} troppo grande. Massimo 16MB'}), 400
    
    # Ottieni categoria documento
    category_slug = request.form.get('category', 'id_card')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni categoria
        cur.execute("SELECT id, name FROM doc_categories WHERE slug = %s AND is_kyc = TRUE", (category_slug,))
        category = cur.fetchone()
        
        if not category:
            return jsonify({'error': 'Categoria documento non valida'}), 400
        
        uploaded_files = []
        
        # Salva tutti i file
        for file_type, file in files_to_upload:
            # Genera nome file sicuro
            filename = secure_filename(file.filename)
            unique_filename = f"{uid}_{uuid.uuid4().hex}_{file_type}_{filename}"
            
            # Salva file
            upload_folder = get_upload_folder()
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, unique_filename)
            file.save(file_path)
            
            # Salva nel database
            cur.execute("""
                INSERT INTO documents (user_id, category_id, title, file_path, mime_type, size_bytes, uploaded_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                uid, 
                category['id'], 
                f"Documento {category['name']} - {file_type}", 
                unique_filename,
                file.content_type,
                file_size,
                datetime.now()
            ))
            
            uploaded_files.append(unique_filename)
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': f'Documento caricato con successo ({len(uploaded_files)} file)',
        'files': uploaded_files
    })

@kyc_bp.route('/api/categories', methods=['GET'])
@login_required
def get_kyc_categories():
    """Ottiene le categorie di documenti KYC disponibili"""
    with get_conn() as conn, conn.cursor() as cur:
        # Prima verifica se esistono categorie KYC
        cur.execute("SELECT COUNT(*) as count FROM doc_categories WHERE is_kyc = TRUE")
        count = cur.fetchone()['count']
        
        # Se non esistono, le crea
        if count == 0:
            cur.execute("""
                INSERT INTO doc_categories (name, slug, description, is_kyc, is_required) VALUES
                ('Carta d''Identità', 'id_card', 'Documento di identità italiano (fronte e retro)', TRUE, TRUE),
                ('Patente di Guida', 'drivers_license', 'Patente di guida italiana (fronte e retro)', TRUE, FALSE),
                ('Passaporto', 'passport', 'Passaporto italiano (pagina principale)', TRUE, FALSE)
                ON CONFLICT (slug) DO NOTHING
            """)
            conn.commit()
        
        # Ora ottieni tutte le categorie KYC
        cur.execute("""
            SELECT id, name, slug, description, is_required
            FROM doc_categories 
            WHERE is_kyc = TRUE
            ORDER BY name
        """)
        categories = cur.fetchall()
    
    return jsonify({'categories': categories})

# =====================================================
# 2. ADMIN ENDPOINTS
# =====================================================

@kyc_bp.route('/admin/dashboard')
@admin_required
def admin_kyc_dashboard():
    """Dashboard KYC admin"""
    return render_template("admin/kyc/dashboard.html")

@kyc_bp.route('/admin/api/kyc-requests', methods=['GET'])
@admin_required 
def admin_get_kyc_requests():
    """Ottiene tutte le richieste KYC per il dashboard admin"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT u.id, u.full_name, u.email, u.telefono, u.created_at, u.kyc_status,
                   COUNT(d.id) as documents_count,
                   CASE WHEN p.id IS NOT NULL THEN true ELSE false END as has_portfolio
            FROM users u
            LEFT JOIN documents d ON u.id = d.user_id 
            LEFT JOIN doc_categories dc ON d.category_id = dc.id AND dc.is_kyc = TRUE
            LEFT JOIN user_portfolios p ON u.id = p.user_id
            WHERE u.role = 'investor'
            GROUP BY u.id, u.full_name, u.email, u.telefono, u.created_at, u.kyc_status, p.id
            ORDER BY u.created_at DESC
        """)
        requests = cur.fetchall()
    
    return jsonify(requests)

@kyc_bp.route('/admin/api/kyc-requests/<int:user_id>', methods=['GET'])
@admin_required
def admin_get_kyc_request_detail(user_id):
    """Ottiene dettagli di una richiesta KYC specifica"""
    with get_conn() as conn, conn.cursor() as cur:
        # Ottieni informazioni utente
        cur.execute("""
            SELECT id, full_name, email, telefono, address, created_at, kyc_status
            FROM users WHERE id = %s
        """, (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'error': 'Utente non trovato'}), 404
        
        # Ottieni documenti KYC
        cur.execute("""
            SELECT d.id, d.title, d.file_path, d.uploaded_at, d.admin_notes,
                   d.verified_by_admin, d.mime_type, d.size_bytes,
                   dc.name as category_name, dc.slug as category_slug
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
            ORDER BY d.uploaded_at DESC
        """, (user_id,))
        documents = cur.fetchall()
        
        user['documents'] = documents
        return jsonify(user)

@kyc_bp.route('/admin/api/kyc-requests/<int:user_id>/approve', methods=['POST'])
@admin_required
def admin_approve_kyc(user_id):
    """Approva la verifica KYC di un utente"""
    admin_id = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica che l'utente abbia documenti
        cur.execute("""
            SELECT COUNT(*) as doc_count
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
        """, (user_id,))
        doc_count = cur.fetchone()['doc_count']
        
        if doc_count == 0:
            return jsonify({'error': 'Utente senza documenti KYC'}), 400
        
        # Aggiorna stato utente
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'verified', kyc_verified_at = %s, kyc_verified_by = %s
            WHERE id = %s
        """, (datetime.now(), admin_id, user_id))
        
        # Marca documenti come verificati
        cur.execute("""
            UPDATE documents 
            SET verified_by_admin = TRUE, verified_at = %s, verified_by = %s
            WHERE user_id = %s AND category_id IN (
                SELECT id FROM doc_categories WHERE is_kyc = TRUE
            )
        """, (datetime.now(), admin_id, user_id))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'KYC approvato con successo'})

@kyc_bp.route('/admin/api/kyc-requests/<int:user_id>/reject', methods=['POST'])
@admin_required
def admin_reject_kyc(user_id):
    """Rifiuta la verifica KYC di un utente"""
    admin_id = session.get("user_id")
    reason = request.json.get('reason', 'Documenti non conformi')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Aggiorna stato utente
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'rejected', kyc_notes = %s, kyc_rejected_at = %s, kyc_rejected_by = %s
            WHERE id = %s
        """, (reason, datetime.now(), admin_id, user_id))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'KYC rifiutato'})

@kyc_bp.route('/admin/api/kyc-stats', methods=['GET'])
@admin_required
def admin_get_kyc_stats():
    """Ottiene statistiche KYC per il dashboard"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN kyc_status = 'verified' THEN 1 ELSE 0 END) as verified,
                SUM(CASE WHEN kyc_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN kyc_status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                SUM(CASE WHEN kyc_status = 'unverified' THEN 1 ELSE 0 END) as unverified
            FROM users WHERE role = 'investor'
        """)
        stats = cur.fetchone()
        
        return jsonify(stats)
