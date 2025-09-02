"""
API KYC per utenti - Upload documenti
"""
from flask import Blueprint, request, jsonify, current_app, session
from backend.auth.decorators import login_required
from backend.models.kyc import KYCRequest, KYCStatus
from backend.kyc.utils import save_kyc_file

kyc_user_api = Blueprint("kyc_user_api", __name__, url_prefix="/kyc/api")


@kyc_user_api.route("/upload", methods=["POST"])
@login_required
def kyc_upload():
    """
    Upload documenti KYC
    
    Accetta:
    - doc_type: passport|id_card|driver_license
    - file_front: file fronte (opzionale)
    - file_back: file retro (opzionale)
    """
    user_id = session.get("user_id")
    doc_type = (request.form.get("doc_type") or "").strip().lower()
    
    # Log per debug
    current_app.logger.info(f"KYC UPLOAD REQUEST by user={user_id} doc_type={doc_type}")
    
    # Validazione doc_type
    if doc_type not in {"passport", "id_card", "driver_license"}:
        return jsonify({
            "ok": False, 
            "error": "Tipo documento non valido. Usa: passport, id_card o driver_license"
        }), 400
    
    # File upload
    file_front = request.files.get("file_front")
    file_back = request.files.get("file_back")
    
    # Almeno un file richiesto
    if not file_front and not file_back:
        return jsonify({
            "ok": False, 
            "error": "Carica almeno un file (fronte o retro)"
        }), 400
    
    try:
        # Salva i file
        rel_front = save_kyc_file(file_front, user_id) if file_front else None
        rel_back = save_kyc_file(file_back, user_id) if file_back else None
        
        current_app.logger.info(
            f"KYC UPLOAD by user={user_id} doc_type={doc_type} "
            f"front={bool(file_front)} back={bool(file_back)}"
        )
        
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Errore salvataggio file KYC: {e}")
        return jsonify({
            "ok": False, 
            "error": "Errore durante il salvataggio del file"
        }), 500
    
    # Crea richiesta KYC
    try:
        req = KYCRequest(
            user_id=user_id,
            doc_type=doc_type,
            file_front=rel_front,
            file_back=rel_back,
            status=KYCStatus.PENDING
        )
        req.save()
        
        current_app.logger.info(f"KYC request created: ID={req.id}")
        
        return jsonify({
            "ok": True,
            "success": True,  # Per compatibilità frontend
            "request_id": req.id,
            "message": "Documento caricato con successo!"
        })
        
    except Exception as e:
        current_app.logger.error(f"Errore creazione richiesta KYC: {e}")
        return jsonify({
            "ok": False,
            "error": "Errore durante la creazione della richiesta"
        }), 500


@kyc_user_api.route("/status", methods=["GET"])
def get_user_kyc_status():
    """Ottiene lo stato KYC dell'utente corrente"""
    user_id = session.get("user_id")
    
    from backend.shared.database import get_connection
    
    with get_connection() as conn, conn.cursor() as cur:
        # Ultima richiesta KYC
        cur.execute("""
            SELECT id, doc_type, status, created_at, 
                   file_front, file_back
            FROM kyc_requests
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        
        request = cur.fetchone()
        
        if not request:
            return jsonify({
                "has_request": False,
                "kyc_status": "unverified",
                "can_invest": False
            })
        
        return jsonify({
            "has_request": True,
            "kyc_status": request['status'],
            "request_id": request['id'],
            "doc_type": request['doc_type'],
            "created_at": request['created_at'].isoformat(),
            "has_documents": bool(request['file_front'] or request['file_back']),
            "can_invest": request['status'] == 'approved'
        })


@kyc_user_api.route("/test", methods=["GET"])
def test_endpoint():
    """Test endpoint semplice"""
    return jsonify({"test": "ok", "message": "Endpoint funziona!"})

@kyc_user_api.route("/doc-types", methods=["GET"])
def get_kyc_doc_types():
    """Ritorna i tipi di documenti disponibili"""
    doc_types = [
        {
            "slug": "id_card",
            "name": "Carta d'Identità",
            "description": "Documento di identità italiano (fronte e retro)"
        },
        {
            "slug": "passport", 
            "name": "Passaporto",
            "description": "Passaporto italiano (pagina principale)"
        },
        {
            "slug": "driver_license",
            "name": "Patente di Guida", 
            "description": "Patente di guida italiana (fronte e retro)"
        }
    ]
    
    return jsonify({"doc_types": doc_types})
