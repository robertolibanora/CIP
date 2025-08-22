"""
Modulo condiviso per connessioni database
Centralizza la gestione delle connessioni PostgreSQL
"""

import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager

def get_database_url():
    """Ottiene l'URL del database dalle variabili d'ambiente"""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL non impostata nelle variabili d'ambiente")
    return dsn

def get_connection():
    """Crea una nuova connessione al database"""
    dsn = get_database_url()
    return psycopg.connect(dsn, row_factory=dict_row)

@contextmanager
def get_db_connection():
    """Context manager per connessioni database con autocommit/rollback"""
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

def test_connection():
    """Testa la connessione al database"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 as test")
                result = cur.fetchone()
                return result['test'] == 1
    except Exception as e:
        print(f"Errore connessione database: {e}")
        return False

if __name__ == "__main__":
    # Test standalone
    if test_connection():
        print("✅ Connessione database OK")
    else:
        print("❌ Errore connessione database")
