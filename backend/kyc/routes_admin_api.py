"""
API KYC per admin - Gestione richieste
"""
from flask import Blueprint, jsonify, request, current_app
from backend.auth.decorators import admin_required
from backend.models.kyc import KYCRequest, KYCStatus

kyc_admin_api = Blueprint("kyc_admin_api", __name__, url_prefix="/kyc/admin/api")


@kyc_admin_api.route("/kyc-requests", methods=["GET"])
@admin_required
def admin_get_kyc_requests():
    """Lista per dashboard admin: una riga per utente con ultima richiesta."""
    try:
        from backend.shared.database import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            # Ultima richiesta per utente con info utente
            cur.execute(
                """
                SELECT u.id AS user_id,
                       u.nome, u.cognome, u.email, u.telefono, u.kyc_status,
                       kr.id AS request_id,
                       kr.created_at,
                       kr.status AS request_status,
                       (CASE WHEN kr.file_front IS NOT NULL THEN 1 ELSE 0 END
                        + CASE WHEN kr.file_back IS NOT NULL THEN 1 ELSE 0 END) AS documents_count
                FROM users u
                LEFT JOIN LATERAL (
                    SELECT * FROM kyc_requests r
                    WHERE r.user_id = u.id
                    ORDER BY r.created_at DESC
                    LIMIT 1
                ) kr ON true
                ORDER BY COALESCE(kr.created_at, u.created_at) DESC
                """
            )
            rows = cur.fetchall()

        result = []
        for r in rows:
            result.append({
                "id": r["user_id"],
                "full_name": f"{r['nome']} {r['cognome']}",
                "email": r["email"],
                "telefono": r.get("telefono"),
                "kyc_status": r["kyc_status"],
                "latest_request_status": r.get("request_status"),
                "documents_count": r.get("documents_count") or 0,
                "created_at": (r.get("created_at") or r.get("created_at")).isoformat() if r.get("created_at") else None,
                "latest_request_id": r.get("request_id")
            })

        # Il frontend si aspetta un array, non un oggetto {items:[]}
        return jsonify(result)

    except Exception as e:
        current_app.logger.error(f"Errore recupero richieste KYC: {e}")
        return jsonify({"error": "Errore recupero dati"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>", methods=["GET"])
@admin_required
def admin_get_kyc_request_detail(user_id: int):
    """Dettaglio per utente: mostra l'ultima richiesta e info contatto."""
    try:
        from backend.shared.database import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            # Utente
            cur.execute("SELECT nome, cognome, email, telefono, kyc_status FROM users WHERE id=%s", (user_id,))
            user = cur.fetchone()
            if not user:
                return jsonify({"error": "Utente non trovato"}), 404

            # Ultima richiesta
            cur.execute(
                """
                SELECT id, doc_type, file_front, file_back, status, created_at
                FROM kyc_requests
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            )
            req = cur.fetchone()

        documents = []
        if req:
            if req["file_front"]:
                documents.append({"title": "Documento Fronte", "file_path": req["file_front"], "category_name": req["doc_type"]})
            if req["file_back"]:
                documents.append({"title": "Documento Retro", "file_path": req["file_back"], "category_name": req["doc_type"]})

        return jsonify({
            "id": user_id,
            "full_name": f"{user['nome']} {user['cognome']}",
            "email": user["email"],
            "telefono": user.get("telefono"),
            "kyc_status": user["kyc_status"],
            "request": {
                "id": req["id"] if req else None,
                "status": req["status"] if req else "unverified",
                "doc_type": req["doc_type"] if req else None,
                "created_at": req["created_at"].isoformat() if req else None,
            },
            "documents": documents
        })

    except Exception as e:
        current_app.logger.error(f"Errore dettaglio KYC user {user_id}: {e}")
        return jsonify({"error": "Errore recupero dati"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>/approve", methods=["POST"])
@admin_required
def admin_approve_kyc(user_id: int):
    """Approva l'ultima richiesta pending dell'utente e aggiorna lo stato."""
    try:
        from backend.shared.database import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            # Trova ultima richiesta pending
            cur.execute(
                """
                SELECT id FROM kyc_requests
                WHERE user_id=%s AND status='pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Nessuna richiesta pending"}), 404

            rid = row["id"]
        
        req = KYCRequest.get_by_id(rid)
        req.approve()

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET kyc_status='verified' WHERE id=%s", (user_id,))
            conn.commit()

        current_app.logger.info(f"KYC user {user_id} approved (req {rid})")
        return jsonify({"ok": True, "message": "KYC approvato con successo"})

    except Exception as e:
        current_app.logger.error(f"Errore approvazione KYC user {user_id}: {e}")
        return jsonify({"error": "Errore durante l'approvazione"}), 500


@kyc_admin_api.route("/kyc-requests/<int:user_id>/reject", methods=["POST"])
@admin_required  
def admin_reject_kyc(user_id: int):
    """Rifiuta l'ultima richiesta pending dell'utente e aggiorna lo stato."""
    try:
        data = request.get_json() or {}
        reason = data.get("reason", "Documenti non conformi")

        from backend.shared.database import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM kyc_requests
                WHERE user_id=%s AND status='pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Nessuna richiesta pending"}), 404

            rid = row["id"]

        req = KYCRequest.get_by_id(rid)
        req.reject()

        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("UPDATE users SET kyc_status='rejected' WHERE id=%s", (user_id,))
            conn.commit()

        current_app.logger.info(f"KYC user {user_id} rejected (req {rid}): {reason}")
        return jsonify({"ok": True, "message": "KYC rifiutato"})

    except Exception as e:
        current_app.logger.error(f"Errore rifiuto KYC user {user_id}: {e}")
        return jsonify({"error": "Errore durante il rifiuto"}), 500


@kyc_admin_api.route("/kyc-stats", methods=["GET"])
@admin_required
def admin_get_kyc_stats():
    """Statistiche KYC"""
    try:
        from backend.shared.database import get_connection
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as verified,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM kyc_requests
            """)
            stats = cur.fetchone()
            
        return jsonify(stats)
        
    except Exception as e:
        current_app.logger.error(f"Errore statistiche KYC: {e}")
        return jsonify({
            "total": 0,
            "verified": 0, 
            "pending": 0,
            "rejected": 0
        })
