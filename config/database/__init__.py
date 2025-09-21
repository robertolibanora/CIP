# Database Configuration Module

import os
import psycopg
from pathlib import Path

def get_connection():
    """Ottieni connessione al database PostgreSQL"""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL non configurata")
    
    return psycopg.connect(database_url)

def create_tables():
    """Crea le tabelle del database se non esistono"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Esegui script di creazione tabelle
                schema_path = Path(__file__).parent / "schema_complete.sql"
                if schema_path.exists():
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        cur.execute(f.read())
                
                # Esegui script per vista admin metrics
                metrics_view_path = Path(__file__).parent / "create_admin_metrics_view.sql"
                if metrics_view_path.exists():
                    with open(metrics_view_path, 'r', encoding='utf-8') as f:
                        cur.execute(f.read())
                
                conn.commit()
                print("✅ Tabelle e viste create con successo")
                
    except Exception as e:
        print(f"❌ Errore durante la creazione tabelle: {e}")
        raise
