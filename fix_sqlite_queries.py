#!/usr/bin/env python3
"""
Script per convertire le query PostgreSQL in SQLite
"""

import re

def fix_sqlite_queries():
    """Converte le query PostgreSQL in SQLite"""
    
    # Leggi il file
    with open('backend/admin/routes.py', 'r') as f:
        content = f.read()
    
    # Sostituzioni per SQLite
    replacements = [
        # Context manager
        (r'with get_conn\(\) as conn, conn\.cursor\(\) as cur:', 'conn = get_conn()\n        cur = conn.cursor()'),
        
        # Parametri PostgreSQL -> SQLite
        (r'%s', '?'),
        
        # Boolean values
        (r'is_active = true', 'is_active = 1'),
        (r'is_active = false', 'is_active = 0'),
        
        # RETURNING -> lastrowid
        (r'RETURNING id\n\s*""", \(', '""", ('),
        (r'config_id = cur\.fetchone\(\)\[\'id\'\]', 'config_id = cur.lastrowid'),
        
        # ON CONFLICT -> INSERT OR REPLACE
        (r'ON CONFLICT \(config_key\)\s*DO UPDATE SET\s*config_value = EXCLUDED\.config_value,\s*config_type = EXCLUDED\.config_type,\s*description = EXCLUDED\.description,\s*updated_at = CURRENT_TIMESTAMP,\s*updated_by = EXCLUDED\.updated_by', ''),
        (r'INSERT INTO system_configurations', 'INSERT OR REPLACE INTO system_configurations'),
    ]
    
    # Applica le sostituzioni
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Aggiungi conn.close() prima di ogni return
    content = re.sub(r'(\s+)return jsonify\(', r'\1conn.close()\n\1return jsonify(', content)
    
    # Scrivi il file
    with open('backend/admin/routes.py', 'w') as f:
        f.write(content)
    
    print("✅ Query convertite per SQLite!")

if __name__ == "__main__":
    fix_sqlite_queries()
