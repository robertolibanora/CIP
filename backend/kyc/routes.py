"""
KYC API routes
API per gestione KYC: Upload, verifica, stati
"""

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, session, jsonify, current_app
from werkzeug.utils import secure_filename
from backend.shared.database import get_connection
from backend.shared.models import KYCStatus, DocumentVisibility

kyc_bp = Blueprint("kyc", __name__)

def get_conn():
    return get_connection()

def get_upload_folder():
    """Ottiene la cartella upload dalla configurazione Flask"""
    return current_app.config.get('UPLOAD_FOLDER', 'uploads')

# Importa decoratori di autorizzazione
from backend.auth.decorators import login_required

# Rimuove il before_request globale e usa decoratori specifici
# per ogni route che richiede autorizzazione

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
                   d.admin_notes, dc.name as category_name, dc.slug as category_slug
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
    
    # Validazione file
    if 'file' not in request.files:
        return jsonify({'error': 'Nessun file caricato'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nessun file selezionato'}), 400
    
    # Validazione tipo file
    allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}
    if not file.filename.lower().endswith(tuple('.' + ext for ext in allowed_extensions)):
        return jsonify({'error': 'Tipo file non supportato. Usa PDF o immagini'}), 400
    
    # Validazione dimensione (max 16MB)
    file.seek(0, 2)  # Vai alla fine del file
    file_size = file.tell()
    file.seek(0)  # Torna all'inizio
    
    if file_size > 16 * 1024 * 1024:  # 16MB
        return jsonify({'error': 'File troppo grande. Massimo 16MB'}), 400
    
    # Ottieni categoria documento
    category_slug = request.form.get('category', 'id_card')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica categoria esiste
        cur.execute("SELECT id, name FROM doc_categories WHERE slug = %s AND is_kyc = TRUE", (category_slug,))
        category = cur.fetchone()
        if not category:
            return jsonify({'error': 'Categoria documento non valida'}), 400
        
        # Salva file
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}-{filename}"
        file_path = os.path.join(get_upload_folder(), unique_filename)
        
        # Crea directory se non esiste
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        file.save(file_path)
        
        # Inserisci nel database
        cur.execute("""
            INSERT INTO documents (user_id, category_id, title, file_path, mime_type, 
                                 size_bytes, visibility, verified_by_admin)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            uid, category['id'], filename, file_path, 
            file.content_type, file_size, 'admin', False
        ))
        
        doc_id = cur.fetchone()['id']
        
        # Aggiorna stato utente se era unverified
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'pending' 
            WHERE id = %s AND kyc_status = 'unverified'
        """, (uid,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'document_id': doc_id,
        'filename': filename,
        'message': 'Documento caricato con successo'
    })

@kyc_bp.route('/api/documents/<int:doc_id>', methods=['DELETE'])
@login_required
def delete_kyc_document(doc_id):
    """Elimina un documento KYC dell'utente"""
    uid = session.get("user_id")
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica proprietà documento
        cur.execute("""
            SELECT d.id, d.file_path, d.verified_by_admin
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.id = %s AND d.user_id = %s AND dc.is_kyc = TRUE
        """, (doc_id, uid))
        document = cur.fetchone()
        
        if not document:
            return jsonify({'error': 'Documento non trovato'}), 404
        
        if document['verified_by_admin']:
            return jsonify({'error': 'Non puoi eliminare un documento verificato'}), 400
        
        # Elimina file fisico
        try:
            if os.path.exists(document['file_path']):
                os.remove(document['file_path'])
        except OSError:
            pass  # Ignora errori eliminazione file
        
        # Elimina record database
        cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
        
        # Verifica se rimangono documenti KYC
        cur.execute("""
            SELECT COUNT(*) as doc_count
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
        """, (uid,))
        
        doc_count = cur.fetchone()['doc_count']
        
        # Se non ci sono più documenti, torna a unverified
        if doc_count == 0:
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'unverified' 
                WHERE id = %s
            """, (uid,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'message': 'Documento eliminato con successo'
    })

@kyc_bp.route('/api/categories', methods=['GET'])
@login_required
def get_kyc_categories():
    """Ottiene le categorie di documenti KYC disponibili"""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT id, slug, name, is_kyc
            FROM doc_categories
            WHERE is_kyc = TRUE
            ORDER BY id
        """)
        categories = cur.fetchall()
    
    return jsonify({'categories': categories})

# =====================================================
# ENDPOINT ADMIN (richiedono ruolo admin)
# =====================================================

from backend.auth.decorators import admin_required

@kyc_bp.route('/api/admin/verify/<int:doc_id>', methods=['POST'])
@admin_required
def admin_verify_document(doc_id):
    """Admin verifica un documento KYC"""
    # Verifica ruolo admin
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data = request.get_json() or {}
    verified = data.get('verified', True)
    admin_notes = data.get('admin_notes', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Verifica documento esiste
        cur.execute("""
            SELECT d.id, d.user_id, d.verified_by_admin
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.id = %s AND dc.is_kyc = TRUE
        """, (doc_id,))
        document = cur.fetchone()
        
        if not document:
            return jsonify({'error': 'Documento non trovato'}), 404
        
        if document['verified_by_admin'] == verified:
            return jsonify({'error': 'Documento già in questo stato'}), 400
        
        # Aggiorna stato documento
        cur.execute("""
            UPDATE documents 
            SET verified_by_admin = %s, admin_notes = %s, verified_at = NOW(), verified_by = %s
            WHERE id = %s
        """, (verified, admin_notes, session.get('user_id'), doc_id))
        
        # Verifica se tutti i documenti KYC dell'utente sono verificati
        cur.execute("""
            SELECT COUNT(*) as total_docs,
                   COUNT(CASE WHEN verified_by_admin = TRUE THEN 1 END) as verified_docs
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE d.user_id = %s AND dc.is_kyc = TRUE
        """, (document['user_id'],))
        
        doc_stats = cur.fetchone()
        
        # Se tutti i documenti sono verificati, approva KYC
        if doc_stats['total_docs'] > 0 and doc_stats['total_docs'] == doc_stats['verified_docs']:
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'verified' 
                WHERE id = %s
            """, (document['user_id'],))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'verified': verified,
        'message': 'Documento verificato con successo' if verified else 'Documento rifiutato'
    })

@kyc_bp.route('/api/admin/pending', methods=['GET'])
@admin_required
def admin_get_pending_kyc():
    """Admin ottiene tutti i documenti KYC in attesa di verifica"""
    # Verifica ruolo admin
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT d.id, d.title, d.file_path, d.uploaded_at, d.admin_notes,
                   u.id as user_id, u.full_name, u.email, u.kyc_status,
                   dc.name as category_name
            FROM documents d
            JOIN users u ON d.user_id = u.id
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE dc.is_kyc = TRUE AND d.verified_by_admin = FALSE
            ORDER BY d.uploaded_at ASC
        """)
        pending_documents = cur.fetchall()
    
    return jsonify({'pending_documents': pending_documents})
