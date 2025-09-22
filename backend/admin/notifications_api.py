"""
API per gestione notifiche admin
"""
from flask import Blueprint, jsonify, request, session
from backend.auth.decorators import admin_required
from backend.shared.notifications import (
    get_admin_notifications,
    get_unread_notifications_count,
    mark_notification_as_read,
    get_notifications_by_type
)

notifications_api = Blueprint("notifications_api", __name__, url_prefix="/admin/api/notifications")


@notifications_api.route("/", methods=["GET"])
@admin_required
def get_notifications():
    """Ottiene tutte le notifiche per l'admin"""
    try:
        limit = request.args.get('limit', 50, type=int)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        
        notifications = get_admin_notifications(limit=limit, unread_only=unread_only)
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "total": len(notifications)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore recupero notifiche: {str(e)}"
        }), 500


@notifications_api.route("/unread-count", methods=["GET"])
@admin_required
def get_unread_count():
    """Ottiene il numero di notifiche non lette"""
    try:
        count = get_unread_notifications_count()
        
        return jsonify({
            "success": True,
            "unread_count": count
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore conteggio notifiche: {str(e)}"
        }), 500


@notifications_api.route("/<int:notification_id>/read", methods=["POST"])
@admin_required
def mark_as_read(notification_id):
    """Marca una notifica come letta"""
    try:
        admin_user_id = session.get('user_id')
        success = mark_notification_as_read(notification_id, admin_user_id)
        
        if success:
            return jsonify({
                "success": True,
                "message": "Notifica marcata come letta"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Notifica non trovata o già letta"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore marcatura notifica: {str(e)}"
        }), 500


@notifications_api.route("/by-type/<notification_type>", methods=["GET"])
@admin_required
def get_by_type(notification_type):
    """Ottiene notifiche per tipo specifico"""
    try:
        if notification_type not in ['kyc', 'deposit', 'withdrawal']:
            return jsonify({
                "success": False,
                "error": "Tipo notifica non valido"
            }), 400
            
        limit = request.args.get('limit', 20, type=int)
        notifications = get_notifications_by_type(notification_type, limit=limit)
        
        return jsonify({
            "success": True,
            "notifications": notifications,
            "type": notification_type,
            "total": len(notifications)
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore recupero notifiche per tipo: {str(e)}"
        }), 500


@notifications_api.route("/mark-all-read", methods=["POST"])
@admin_required
def mark_all_as_read():
    """Marca tutte le notifiche come lette"""
    try:
        from backend.shared.database import get_connection
        
        admin_user_id = session.get('user_id')
        
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE admin_notifications 
                SET is_read = TRUE, read_at = NOW(), read_by = %s
                WHERE is_read = FALSE
            """, (admin_user_id,))
            
            updated_count = cur.rowcount
            conn.commit()
            
        return jsonify({
            "success": True,
            "message": f"Marcate {updated_count} notifiche come lette"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore marcatura notifiche: {str(e)}"
        }), 500


@notifications_api.route("/<int:notification_id>", methods=["DELETE"])
@admin_required
def delete_notification(notification_id):
    """Elimina una singola notifica"""
    try:
        from backend.shared.database import get_connection
        
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM admin_notifications WHERE id = %s", (notification_id,))
            deleted_count = cur.rowcount
            conn.commit()
            
        if deleted_count > 0:
            return jsonify({
                "success": True,
                "message": "Notifica eliminata"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Notifica non trovata"
            }), 404
            
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore eliminazione notifica: {str(e)}"
        }), 500


@notifications_api.route("/clear-all", methods=["POST"])
@admin_required
def clear_all_notifications():
    """Elimina tutte le notifiche"""
    try:
        from backend.shared.database import get_connection
        
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM admin_notifications")
            deleted_count = cur.rowcount
            conn.commit()
            
        return jsonify({
            "success": True,
            "message": f"Eliminate {deleted_count} notifiche"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Errore eliminazione notifiche: {str(e)}"
        }), 500
