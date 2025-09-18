"""
Sistema notifiche admin per KYC, depositi e prelievi
"""
from typing import Dict, Any, Optional
from datetime import datetime
import json
from backend.shared.database import get_connection


def create_admin_notification(
    notification_type: str,
    user_id: int,
    title: str,
    message: str,
    metadata: Optional[Dict[str, Any]] = None
) -> int:
    """
    Crea una notifica per l'admin
    
    Args:
        notification_type: 'kyc', 'deposit', 'withdrawal'
        user_id: ID dell'utente che ha generato la notifica
        title: Titolo della notifica
        message: Messaggio dettagliato
        metadata: Dati aggiuntivi (es. amount per depositi)
    
    Returns:
        ID della notifica creata
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO admin_notifications (type, user_id, title, message, metadata)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (notification_type, user_id, title, message, json.dumps(metadata) if metadata else None))
            
            notification_id = cur.fetchone()['id']
            conn.commit()
            return notification_id
            
    except Exception as e:
        print(f"Errore creazione notifica admin: {e}")
        return None


def get_admin_notifications(limit: int = 50, unread_only: bool = False) -> list:
    """
    Ottiene le notifiche per l'admin
    
    Args:
        limit: Numero massimo di notifiche da restituire
        unread_only: Se True, restituisce solo notifiche non lette
    
    Returns:
        Lista delle notifiche
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            where_clause = "WHERE is_read = FALSE" if unread_only else ""
            
            cur.execute(f"""
                SELECT n.id, n.type, n.user_id, n.title, n.message, n.is_read, 
                       n.created_at, n.read_at, n.metadata,
                       u.nome, u.cognome, u.email
                FROM admin_notifications n
                LEFT JOIN users u ON n.user_id = u.id
                {where_clause}
                ORDER BY n.created_at DESC
                LIMIT %s
            """, (limit,))
            
            return cur.fetchall()
            
    except Exception as e:
        print(f"Errore recupero notifiche admin: {e}")
        return []


def mark_notification_as_read(notification_id: int, admin_user_id: int) -> bool:
    """
    Marca una notifica come letta
    
    Args:
        notification_id: ID della notifica
        admin_user_id: ID dell'admin che ha letto la notifica
    
    Returns:
        True se successo, False altrimenti
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                UPDATE admin_notifications 
                SET is_read = TRUE, read_at = NOW(), read_by = %s
                WHERE id = %s
            """, (admin_user_id, notification_id))
            
            conn.commit()
            return cur.rowcount > 0
            
    except Exception as e:
        print(f"Errore marcatura notifica come letta: {e}")
        return False


def get_unread_notifications_count() -> int:
    """
    Ottiene il numero di notifiche non lette
    
    Returns:
        Numero di notifiche non lette
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as count FROM admin_notifications WHERE is_read = FALSE")
            result = cur.fetchone()
            return result['count'] if result else 0
            
    except Exception as e:
        print(f"Errore conteggio notifiche non lette: {e}")
        return 0


def get_notifications_by_type(notification_type: str, limit: int = 20) -> list:
    """
    Ottiene notifiche per tipo specifico
    
    Args:
        notification_type: 'kyc', 'deposit', 'withdrawal'
        limit: Numero massimo di notifiche
    
    Returns:
        Lista delle notifiche del tipo specificato
    """
    try:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT n.id, n.type, n.user_id, n.title, n.message, n.is_read, 
                       n.created_at, n.read_at, n.metadata,
                       u.nome, u.cognome, u.email
                FROM admin_notifications n
                JOIN users u ON n.user_id = u.id
                WHERE n.type = %s
                ORDER BY n.created_at DESC
                LIMIT %s
            """, (notification_type, limit))
            
            return cur.fetchall()
            
    except Exception as e:
        print(f"Errore recupero notifiche per tipo {notification_type}: {e}")
        return []


# Funzioni helper per creare notifiche specifiche

def create_kyc_notification(user_id: int, user_name: str) -> int:
    """Crea notifica per richiesta KYC"""
    return create_admin_notification(
        notification_type='kyc',
        user_id=user_id,
        title='Nuova Richiesta KYC',
        message=f'{user_name} ha caricato documenti per la verifica KYC',
        metadata={'action': 'kyc_upload'}
    )


def create_deposit_notification(user_id: int, user_name: str, amount: float = None) -> int:
    """Crea notifica per richiesta deposito"""
    return create_admin_notification(
        notification_type='deposit',
        user_id=user_id,
        title='Nuova Richiesta Deposito',
        message=f'{user_name} ha effettuato una richiesta di deposito',
        metadata={'action': 'deposit_request'}
    )


def create_withdrawal_notification(user_id: int, user_name: str, amount: float) -> int:
    """Crea notifica per richiesta prelievo"""
    return create_admin_notification(
        notification_type='withdrawal',
        user_id=user_id,
        title='Nuova Richiesta Prelievo',
        message=f'{user_name} ha richiesto un prelievo di €{amount:,.2f}',
        metadata={'action': 'withdrawal_request', 'amount': amount}
    )
