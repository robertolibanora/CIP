"""
API KYC per admin - Gestione richieste (VERSIONE CORRETTA)
Unifica i due sistemi KYC: documents + kyc_requests
"""
from flask import Blueprint, jsonify, request, current_app, session
import os
from backend.auth.decorators import admin_required
from backend.shared.database import get_connection

kyc_admin_api = Blueprint("kyc_admin_api", __name__, url_prefix="/kyc/admin/api")


@kyc_admin_api.route("/kyc-requests", methods=["GET"])
@admin_required
def admin_get_kyc_requests():
    """Lista per dashboard admin: una riga per utente con documenti KYC."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            # Query unificata che usa la tabella documents (sistema principale)
            cur.execute("""
                SELECT DISTINCT u.id AS user_id,
                       u.nome, u.cognome, u.email, u.telefono, u.kyc_status,
                       u.created_at,
                       COUNT(d.id) AS documents_count,
                       MAX(d.uploaded_at) AS last_upload
                FROM users u
                LEFT JOIN documents d ON u.id = d.user_id 
                LEFT JOIN doc_categories dc ON d.category_id = dc.id AND dc.is_kyc = TRUE
                WHERE u.ruolo = 'investor'
                GROUP BY u.id, u.nome, u.cognome, u.email, u.telefono, u.kyc_status, u.created_at
                ORDER BY u.created_at DESC
            """)
            rows = cur.fetchall()

        result = []
        for r in rows:
            result.append({
                "id": r["user_id"],
                "nome": f"{r['nome']} {r['cognome']}",
                "email": r["email"],
                "telefono": r.get("telefono"),
                "kyc_status": r["kyc_status"],
                "documents_count": r.get("documents_count") or 0,
                "created_at": r["created_at"].isoformat() if r.get("created_at") else None,
                "last_upload": r["last_upload"].isoformat() if r.get("last_upload") else None
            })

        return jsonify({"requests": result})

    except Exception as e:
        current_app.logger.error(f"Errore recupero richieste KYC: {e}")
        return jsonify({"error": "Errore recupero dati"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>", methods=["GET"])
@admin_required
def admin_get_kyc_request_detail(user_id: int):
    """Dettaglio per utente: mostra documenti KYC caricati."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            # Utente
            cur.execute("SELECT nome, cognome, email, telefono, kyc_status FROM users WHERE id=%s", (user_id,))
            user = cur.fetchone()
            if not user:
                return jsonify({"error": "Utente non trovato"}), 404

            # Documenti KYC
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

        return jsonify({
            "id": user_id,
            "nome": f"{user['nome']} {user['cognome']}",
            "email": user["email"],
            "telefono": user.get("telefono"),
            "kyc_status": user["kyc_status"],
            "documents": documents
        })

    except Exception as e:
        current_app.logger.error(f"Errore dettaglio KYC user {user_id}: {e}")
        return jsonify({"error": "Errore recupero dati"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>/approve", methods=["POST"])
@admin_required
def admin_approve_kyc(user_id: int):
    """Approva la verifica KYC di un utente."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            # Verifica che l'utente esista
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Utente non trovato'}), 404
            
            # Verifica che l'utente abbia documenti KYC
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
                SET kyc_status = 'verified'
                WHERE id = %s
            """, (user_id,))
            
            # Marca documenti come verificati
            cur.execute("""
                UPDATE documents 
                SET verified_by_admin = TRUE, verified_at = NOW(), verified_by = %s
                WHERE user_id = %s AND category_id IN (
                    SELECT id FROM doc_categories WHERE is_kyc = TRUE
                )
            """, (session.get('user_id'), user_id))
            
            conn.commit()
        
        current_app.logger.info(f"KYC user {user_id} approved by admin {session.get('user_id')}")
        return jsonify({"ok": True, "message": "KYC approvato con successo"})

    except Exception as e:
        current_app.logger.error(f"Errore approvazione KYC user {user_id}: {e}")
        return jsonify({"error": "Errore durante l'approvazione"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>/reject", methods=["POST"])
@admin_required  
def admin_reject_kyc(user_id: int):
    """Rifiuta la verifica KYC di un utente."""
    try:
        data = request.get_json() or {}
        reason = data.get("reason", "Documenti non conformi")

        with get_connection() as conn, conn.cursor() as cur:
            # Verifica che l'utente esista
            cur.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cur.fetchone():
                return jsonify({'error': 'Utente non trovato'}), 404
                
            # Aggiorna stato utente
            cur.execute("""
                UPDATE users 
                SET kyc_status = 'rejected'
                WHERE id = %s
            """, (user_id,))
            
            # Aggiungi note ai documenti
            cur.execute("""
                UPDATE documents 
                SET admin_notes = %s
                WHERE user_id = %s AND category_id IN (
                    SELECT id FROM doc_categories WHERE is_kyc = TRUE
                )
            """, (reason, user_id))
            
            conn.commit()
        
        current_app.logger.info(f"KYC user {user_id} rejected: {reason}")
        return jsonify({"ok": True, "message": "KYC rifiutato"})

    except Exception as e:
        current_app.logger.error(f"Errore rifiuto KYC user {user_id}: {e}")
        return jsonify({"error": "Errore durante il rifiuto"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>/revoke", methods=["POST"])
@admin_required
def admin_revoke_kyc(user_id: int):
    """Revoca lo stato KYC di un utente."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            # Verifica che l'utente esista
            cur.execute("SELECT id, kyc_status FROM users WHERE id = %s", (user_id,))
            user = cur.fetchone()
            if not user:
                return jsonify({'error': 'Utente non trovato'}), 404
            
            # Verifica che l'utente sia verificato
            if user['kyc_status'] != 'verified':
                return jsonify({'error': 'Utente non è verificato'}), 400
            
            # Aggiorna stato utente -> passa a "rejected" per comparire tra rifiutati
            cur.execute("UPDATE users SET kyc_status='rejected' WHERE id=%s", (user_id,))
            
            # Rimuovi verifiche dai documenti
            cur.execute("""
                UPDATE documents 
                SET verified_by_admin = FALSE, verified_at = NULL, verified_by = NULL, admin_notes = NULL
                WHERE user_id = %s AND category_id IN (
                    SELECT id FROM doc_categories WHERE is_kyc = TRUE
                )
            """, (user_id,))
            
            conn.commit()
            
        current_app.logger.info(f"KYC user {user_id} revoked (set to rejected) by admin {session.get('user_id')}")
        return jsonify({"ok": True, "message": "Verifica KYC revocata: utente spostato tra rifiutati"})
    except Exception as e:
        current_app.logger.error(f"Errore revoca KYC user {user_id}: {e}")
        return jsonify({"error": "Errore durante la revoca"}), 500


@kyc_admin_api.route("/kyc-stats", methods=["GET"])
@admin_required
def admin_get_kyc_stats():
    """Statistiche KYC basate sulla tabella users."""
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN kyc_status = 'verified' THEN 1 ELSE 0 END) as verified,
                    SUM(CASE WHEN kyc_status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN kyc_status = 'rejected' THEN 1 ELSE 0 END) as rejected,
                    SUM(CASE WHEN kyc_status = 'unverified' THEN 1 ELSE 0 END) as unverified
                FROM users WHERE ruolo = 'investor'
            """)
            stats = cur.fetchone()
            
        return jsonify(stats)
        
    except Exception as e:
        current_app.logger.error(f"Errore statistiche KYC: {e}")
        return jsonify({
            "total": 0,
            "verified": 0, 
            "pending": 0,
            "rejected": 0,
            "unverified": 0
        })


# -----------------------------------------------------
# Delete single KYC document (admin only)
# -----------------------------------------------------
@kyc_admin_api.route("/kyc-requests/<int:user_id>/documents/<int:doc_id>", methods=["DELETE"])
@admin_required
def admin_delete_kyc_document(user_id: int, doc_id: int):
    """Elimina un documento KYC (record DB + file su disco).

    Sicurezza:
    - Verifica che il documento appartenga all'utente indicato
    - Consente la cancellazione solo per documenti di categorie KYC
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            # Recupera documento e verifica appartenenza e che sia KYC
            cur.execute(
                """
                SELECT d.file_path
                FROM documents d
                JOIN doc_categories dc ON dc.id = d.category_id
                WHERE d.id = %s AND d.user_id = %s AND dc.is_kyc = TRUE
                """,
                (doc_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Documento non trovato"}), 404

            file_rel_path = row.get("file_path")

            # Elimina record DB
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))

            # Se l'utente non ha più documenti KYC e non è verified, rimane pending/unverified
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM documents d
                JOIN doc_categories dc ON dc.id = d.category_id
                WHERE d.user_id = %s AND dc.is_kyc = TRUE
                """,
                (user_id,)
            )
            remaining = (cur.fetchone() or {}).get("cnt", 0)

            # Se nessun documento rimasto e utente non verified => metti in unverified
            if remaining == 0:
                cur.execute("UPDATE users SET kyc_status = CASE WHEN kyc_status = 'verified' THEN kyc_status ELSE 'unverified' END WHERE id=%s", (user_id,))

            conn.commit()

        # Elimina file su disco (best effort)
        try:
            if file_rel_path:
                upload_dir = current_app.config.get('UPLOAD_FOLDER')
                if upload_dir:
                    abs_path = os.path.join(upload_dir, file_rel_path)
                    if os.path.isfile(abs_path):
                        os.remove(abs_path)
        except Exception as fe:
            current_app.logger.warning(f"Impossibile eliminare file documento {file_rel_path}: {fe}")

        return jsonify({"ok": True})
    except Exception as e:
        current_app.logger.error(f"Errore eliminazione documento KYC {doc_id} per user {user_id}: {e}")
        return jsonify({"error": "Errore durante l'eliminazione"}), 500
