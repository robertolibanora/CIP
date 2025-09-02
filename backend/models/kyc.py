"""
Modello KYCRequest per gestione richieste KYC
"""
from datetime import datetime
from backend.shared.database import get_connection


class KYCStatus:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class KYCRequest:
    """Modello per richieste KYC senza ORM"""
    
    def __init__(self, user_id, doc_type, file_front=None, file_back=None, 
                 status=KYCStatus.PENDING, id=None, created_at=None, updated_at=None):
        self.id = id
        self.user_id = user_id
        self.doc_type = doc_type
        self.file_front = file_front
        self.file_back = file_back
        self.status = status
        self.created_at = created_at or datetime.utcnow()
        self.updated_at = updated_at or datetime.utcnow()
    
    def save(self):
        """Salva o aggiorna la richiesta nel database"""
        with get_connection() as conn, conn.cursor() as cur:
            if self.id:
                # Update esistente
                cur.execute("""
                    UPDATE kyc_requests 
                    SET doc_type = %s, file_front = %s, file_back = %s, 
                        status = %s, updated_at = NOW()
                    WHERE id = %s
                    RETURNING id
                """, (self.doc_type, self.file_front, self.file_back, 
                      self.status, self.id))
            else:
                # Insert nuovo
                cur.execute("""
                    INSERT INTO kyc_requests 
                    (user_id, doc_type, file_front, file_back, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                    RETURNING id
                """, (self.user_id, self.doc_type, self.file_front, 
                      self.file_back, self.status))
            
            result = cur.fetchone()
            if result:
                self.id = result['id']
            conn.commit()
        return self
    
    @classmethod
    def get_by_id(cls, request_id):
        """Recupera richiesta per ID"""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM kyc_requests WHERE id = %s
            """, (request_id,))
            row = cur.fetchone()
            if row:
                return cls(
                    id=row['id'],
                    user_id=row['user_id'],
                    doc_type=row['doc_type'],
                    file_front=row['file_front'],
                    file_back=row['file_back'],
                    status=row['status'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
        return None
    
    @classmethod
    def get_all(cls, order_by='created_at DESC'):
        """Recupera tutte le richieste"""
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(f"""
                SELECT k.*, u.nome, u.cognome, u.email 
                FROM kyc_requests k
                JOIN users u ON k.user_id = u.id
                ORDER BY k.{order_by}
            """)
            rows = cur.fetchall()
            return rows  # Ritorna dict per semplicità
    
    def approve(self):
        """Approva la richiesta"""
        self.status = KYCStatus.APPROVED
        self.save()
    
    def reject(self):
        """Rifiuta la richiesta"""
        self.status = KYCStatus.REJECTED
        self.save()
