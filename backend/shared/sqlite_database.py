"""
Modulo per connessioni database SQLite
Sostituisce il sistema PostgreSQL per compatibilità
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Optional, Dict, Any, List

def get_database_url():
    """Ottiene l'URL del database dalle variabili d'ambiente"""
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL non impostata nelle variabili d'ambiente")
    
    # Converte URL SQLite in percorso file
    if dsn.startswith("sqlite:///"):
        return dsn.replace("sqlite:///", "")
    return dsn

def get_connection():
    """Crea una nuova connessione al database SQLite"""
    db_path = get_database_url()
    
    # Se il percorso è relativo, crea la directory se necessario
    if not os.path.isabs(db_path):
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # Per ottenere risultati come dict
    return conn

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
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 as test")
        result = cur.fetchone()
        conn.close()
        return result['test'] == 1
    except Exception as e:
        print(f"Errore connessione database: {e}")
        return False

def init_database():
    """Inizializza il database SQLite con le tabelle necessarie"""
    try:
        conn = get_connection()
        cur = conn.cursor()
        
        # Crea tabella users se non esiste
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                nome_telegram TEXT UNIQUE NOT NULL,
                telefono TEXT NOT NULL,
                address TEXT,
                role TEXT NOT NULL CHECK (role IN ('admin','investor')) DEFAULT 'investor',
                kyc_status TEXT NOT NULL CHECK (kyc_status IN ('unverified','pending','verified','rejected')) DEFAULT 'unverified',
                currency_code TEXT NOT NULL DEFAULT 'EUR',
                referral_code TEXT UNIQUE,
                referral_link TEXT,
                referred_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Crea indici
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_users_kyc_status ON users(kyc_status)")
        
        conn.commit()
        conn.close()
        print("✅ Database SQLite inizializzato con successo")
        return True
    except Exception as e:
        print(f"❌ Errore inizializzazione database: {e}")
        return False

if __name__ == "__main__":
    # Test standalone
    if test_connection():
        print("✅ Connessione database SQLite OK")
    else:
        print("❌ Errore connessione database SQLite")
