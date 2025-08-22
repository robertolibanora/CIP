import os
import psycopg
from psycopg.rows import dict_row
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

def get_database_url():
    """Ottiene l'URL del database dalle variabili d'ambiente"""
    return os.environ.get("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/cip"

def get_connection():
    """Crea una connessione al database"""
    dsn = get_database_url()
    if not dsn:
        raise RuntimeError("DATABASE_URL non impostata")
    return psycopg.connect(dsn, row_factory=dict_row)

@contextmanager
def get_db_cursor():
    """Context manager per gestire connessioni e cursori del database"""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_database():
    """Inizializza il database creando le tabelle se non esistono"""
    with get_db_cursor() as cur:
        # Leggi e esegui lo schema
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
        
        # Esegui le query una per volta per evitare errori
        queries = schema_sql.split(';')
        for query in queries:
            query = query.strip()
            if query and not query.startswith('--'):
                try:
                    cur.execute(query)
                except Exception as e:
                    print(f"Errore nell'esecuzione della query: {e}")
                    print(f"Query: {query[:100]}...")

def health_check():
    """Verifica la salute del database"""
    try:
        with get_db_cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"Errore connessione database: {e}")
        return False

if __name__ == "__main__":
    print("Verifica connessione database...")
    if health_check():
        print("✅ Database raggiungibile")
    else:
        print("❌ Database non raggiungibile")
