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
@kyc_bp.route('/api/upload', methods=['POST'])  # Endpoint aggiuntivo come richiesto
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
    front_file = request.files.get('file_front') or request.files.get('file')  # Retrocompatibilità
    back_file = request.files.get('file_back')
    
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
        # Verifica categoria esiste
        cur.execute("SELECT id, name FROM doc_categories WHERE slug = %s AND is_kyc = TRUE", (category_slug,))
        category = cur.fetchone()
        if not category:
            return jsonify({'error': 'Categoria documento non valida'}), 400
        
        # Salva i file
        upload_folder = get_upload_folder()
        os.makedirs(upload_folder, exist_ok=True)
        
        uploaded_documents = []
        
        for file_type, file in files_to_upload:
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}-{file_type}-{filename}"
            file_path = os.path.join(upload_folder, unique_filename)
            
            # Salva il file fisico
            file.save(file_path)
            
            # Calcola dimensione file
            file_size = os.path.getsize(file_path)
            
            # Titolo del documento include il tipo (fronte/retro)
            doc_title = f"{filename} ({file_type.title()})"
            
            # Inserisci nel database
            cur.execute("""
                INSERT INTO documents (user_id, category_id, title, file_path, mime_type, 
                                     size_bytes, visibility, verified_by_admin)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                uid, category['id'], doc_title, unique_filename, 
                file.content_type, file_size, 'admin', False
            ))
            
            doc_id = cur.fetchone()['id']
            uploaded_documents.append({
                'id': doc_id,
                'filename': filename,
                'file_type': file_type,
                'size': file_size
            })
        
        # Aggiorna stato utente se era unverified
        cur.execute("""
            UPDATE users 
            SET kyc_status = 'pending' 
            WHERE id = %s AND kyc_status = 'unverified'
        """, (uid,))
        
        conn.commit()
    
    return jsonify({
        'success': True,
        'documents': uploaded_documents,
        'total_files': len(uploaded_documents),
        'message': f'Documento caricato con successo ({len(uploaded_documents)} file)'
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

# =====================================================
# ADMIN ENDPOINTS per Dashboard
# =====================================================

@kyc_bp.route('/admin/api/kyc-requests', methods=['GET'])
@admin_required 
def admin_get_kyc_requests():
    """Ottiene tutte le richieste KYC per il dashboard admin"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
        
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT u.id, u.full_name, u.email, u.telefono, u.created_at, u.kyc_status,
                   COUNT(d.id) as documents_count,
                   CASE WHEN p.id IS NOT NULL THEN true ELSE false END as has_portfolio
            FROM users u
            LEFT JOIN documents d ON u.id = d.user_id 
            LEFT JOIN doc_categories dc ON d.category_id = dc.id AND dc.is_kyc = TRUE
            LEFT JOIN portfolio p ON u.id = p.user_id
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
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
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

@kyc_bp.route('/admin/api/kyc-stats', methods=['GET'])
@admin_required
def admin_get_kyc_stats():
    """Ottiene statistiche KYC per il dashboard"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT 
                COUNT(CASE WHEN kyc_status = 'pending' THEN 1 END) as pending,
                COUNT(CASE WHEN kyc_status = 'verified' THEN 1 END) as verified,
                COUNT(CASE WHEN kyc_status = 'rejected' THEN 1 END) as rejected,
                COUNT(*) as total
            FROM users WHERE role = 'investor'
        """)
        stats = cur.fetchone()
        
        # Calcola trend (mock data per ora)
        stats['trend'] = 5.2  # Placeholder
        
        return jsonify(stats)

@kyc_bp.route('/admin/kyc/<int:user_id>/approve', methods=['POST'])
@admin_required
def admin_approve_kyc_user(user_id):
    """Approva rapidamente tutti i documenti di un utente"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
        
    data = request.get_json() or {}
    notes = data.get('notes', 'Approvazione rapida')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Approva tutti i documenti KYC dell'utente
        cur.execute("""
            UPDATE documents 
            SET verified_by_admin = TRUE, 
                admin_notes = %s, 
                verified_at = NOW(),
                verified_by = %s
            FROM doc_categories dc 
            WHERE documents.category_id = dc.id 
            AND dc.is_kyc = TRUE 
            AND documents.user_id = %s
        """, (notes, session.get('user_id'), user_id))
        
        # Aggiorna stato utente
        cur.execute("UPDATE users SET kyc_status = 'verified' WHERE id = %s", (user_id,))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'KYC approvato con successo'})

@kyc_bp.route('/admin/kyc/<int:user_id>/reject', methods=['POST'])
@admin_required 
def admin_reject_kyc_user(user_id):
    """Rifiuta KYC di un utente"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data = request.get_json() or {}
    notes = data.get('notes', '')
    
    if not notes.strip():
        return jsonify({'error': 'Le note sono obbligatorie per il rifiuto'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        # Aggiorna documenti con note di rifiuto
        cur.execute("""
            UPDATE documents 
            SET verified_by_admin = FALSE, 
                admin_notes = %s, 
                verified_at = NOW(),
                verified_by = %s
            FROM doc_categories dc 
            WHERE documents.category_id = dc.id 
            AND dc.is_kyc = TRUE 
            AND documents.user_id = %s
        """, (notes, session.get('user_id'), user_id))
        
        # Aggiorna stato utente
        cur.execute("UPDATE users SET kyc_status = 'rejected' WHERE id = %s", (user_id,))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': 'KYC rifiutato'})

@kyc_bp.route('/admin/kyc/bulk-action', methods=['POST'])
@admin_required
def admin_bulk_kyc_action():
    """Esegue azioni bulk sui KYC"""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data = request.get_json() or {}
    action = data.get('action')
    request_ids = data.get('request_ids', [])
    
    if not action or not request_ids:
        return jsonify({'error': 'Azione e IDs richiesti'}), 400
    
    with get_conn() as conn, conn.cursor() as cur:
        if action == 'approve':
            # Approva tutti i documenti degli utenti selezionati
            for user_id in request_ids:
                cur.execute("""
                    UPDATE documents 
                    SET verified_by_admin = TRUE, 
                        admin_notes = 'Approvazione bulk', 
                        verified_at = NOW(),
                        verified_by = %s
                    FROM doc_categories dc 
                    WHERE documents.category_id = dc.id 
                    AND dc.is_kyc = TRUE 
                    AND documents.user_id = %s
                """, (session.get('user_id'), user_id))
                
                cur.execute("UPDATE users SET kyc_status = 'verified' WHERE id = %s", (user_id,))
        
        elif action == 'reject':
            # Rifiuta KYC degli utenti selezionati
            for user_id in request_ids:
                cur.execute("""
                    UPDATE documents 
                    SET verified_by_admin = FALSE, 
                        admin_notes = 'Rifiuto bulk', 
                        verified_at = NOW(),
                        verified_by = %s
                    FROM doc_categories dc 
                    WHERE documents.category_id = dc.id 
                    AND dc.is_kyc = TRUE 
                    AND documents.user_id = %s
                """, (session.get('user_id'), user_id))
                
                cur.execute("UPDATE users SET kyc_status = 'rejected' WHERE id = %s", (user_id,))
        
        elif action == 'pending':
            # Rimetti in attesa
            for user_id in request_ids:
                cur.execute("UPDATE users SET kyc_status = 'pending' WHERE id = %s", (user_id,))
        
        conn.commit()
    
    return jsonify({'success': True, 'message': f'Azione {action} completata per {len(request_ids)} utenti'})

@kyc_bp.route('/api/kyc/<int:doc_id>', methods=['PATCH'])  # Endpoint richiesto dall'utente
@kyc_bp.route('/api/admin/verify/<int:doc_id>', methods=['POST'])  # Endpoint esistente
@admin_required
def admin_update_document_status(doc_id):
    """Admin verifica/aggiorna stato di un documento KYC"""
    # Verifica ruolo admin
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    data = request.get_json() or {}
    
    # Supporta sia 'verified' (endpoint POST) che 'status' (endpoint PATCH)
    if 'status' in data:
        # Nuovo formato PATCH: status può essere 'verified', 'rejected', 'pending'
        status = data.get('status', 'pending')
        if status == 'verified':
            verified = True
        elif status == 'rejected':
            verified = False
        else:  # pending o altro
            verified = False
    else:
        # Formato originale POST: verified boolean
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
    
    # Determina messaggio e status basato sul risultato
    if verified:
        status_text = 'verified'
        message = 'Documento verificato con successo'
    elif admin_notes:
        status_text = 'rejected'
        message = 'Documento rifiutato'
    else:
        status_text = 'pending'
        message = 'Documento rimesso in attesa'
    
    return jsonify({
        'success': True,
        'verified': verified,
        'status': status_text,
        'admin_notes': admin_notes,
        'message': message
    })

@kyc_bp.route('/api/kyc/documents', methods=['GET'])  # Endpoint richiesto dall'utente
@kyc_bp.route('/api/admin/pending', methods=['GET'])  # Endpoint esistente
@admin_required
def admin_get_kyc_documents():
    """Admin ottiene tutti i documenti KYC per gestione"""
    # Verifica ruolo admin
    if session.get('role') != 'admin':
        return jsonify({'error': 'Accesso negato'}), 403
    
    # Ottieni filtri dalla query string
    status_filter = request.args.get('status', '')
    search = request.args.get('search', '')
    
    with get_conn() as conn, conn.cursor() as cur:
        # Query base
        query = """
            SELECT d.id, d.title, d.file_path, d.uploaded_at, d.admin_notes,
                   d.verified_by_admin, d.verified_at, d.mime_type, d.size_bytes,
                   u.id as user_id, u.full_name, u.email, u.kyc_status,
                   dc.name as category_name, dc.slug as category_slug
            FROM documents d
            JOIN users u ON d.user_id = u.id
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE dc.is_kyc = TRUE
        """
        params = []
        
        # Applica filtri
        if status_filter == 'pending':
            query += " AND d.verified_by_admin = FALSE"
        elif status_filter == 'verified':
            query += " AND d.verified_by_admin = TRUE"
        elif status_filter == 'rejected':
            query += " AND d.verified_by_admin = FALSE AND d.admin_notes IS NOT NULL AND d.admin_notes != ''"
        
        if search:
            query += " AND (u.full_name ILIKE %s OR u.email ILIKE %s OR d.title ILIKE %s)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        query += " ORDER BY d.uploaded_at DESC"
        
        cur.execute(query, params)
        documents = cur.fetchall()
        
        # Aggiungi statistiche
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN d.verified_by_admin = FALSE THEN 1 END) as pending,
                COUNT(CASE WHEN d.verified_by_admin = TRUE THEN 1 END) as verified,
                COUNT(CASE WHEN d.verified_by_admin = FALSE AND d.admin_notes IS NOT NULL AND d.admin_notes != '' THEN 1 END) as rejected
            FROM documents d
            JOIN doc_categories dc ON d.category_id = dc.id
            WHERE dc.is_kyc = TRUE
        """)
        stats = cur.fetchone()
    
    return jsonify({
        'documents': documents,
        'stats': stats,
        'filters': {'status': status_filter, 'search': search}
    })
