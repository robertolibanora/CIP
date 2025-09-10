#!/usr/bin/env python3
"""
Script per correggere i problemi di indentazione nei file Python
"""

import re
import os

def fix_indentation_in_file(file_path):
    """Corregge i problemi di indentazione in un file"""
    print(f"Correggendo {file_path}...")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern per trovare le linee con problemi di indentazione
    # Cerca linee che iniziano con "cur = conn.cursor()" senza indentazione corretta
    lines = content.split('\n')
    fixed_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Se troviamo una linea con "with get_db_connection() as conn:" seguita da "cur = conn.cursor()" senza indentazione
        if line.strip() == "with get_db_connection() as conn:":
            fixed_lines.append(line)
            i += 1
            
            # Controlla le prossime linee per problemi di indentazione
            while i < len(lines) and lines[i].strip().startswith("cur = conn.cursor()"):
                if not lines[i].startswith("        "):  # Dovrebbe essere indentato con 8 spazi
                    fixed_lines.append("        " + lines[i].strip())
                else:
                    fixed_lines.append(lines[i])
                i += 1
                
            # Continua con le altre linee che dovrebbero essere indentate
            while i < len(lines) and lines[i].strip() and not lines[i].startswith("    ") and not lines[i].startswith("def ") and not lines[i].startswith("class ") and not lines[i].startswith("@") and not lines[i].strip().startswith("return ") and not lines[i].strip().startswith("except ") and not lines[i].strip().startswith("finally "):
                if lines[i].strip() and not lines[i].startswith("        "):
                    fixed_lines.append("        " + lines[i].strip())
                else:
                    fixed_lines.append(lines[i])
                i += 1
        else:
            fixed_lines.append(line)
            i += 1
    
    # Scrivi il file corretto
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"✅ Corretto {file_path}")

def main():
    """Funzione principale"""
    files_to_fix = [
        "backend/admin/routes.py",
        "backend/user/routes.py",
        "backend/auth/middleware.py"
    ]
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_indentation_in_file(file_path)
        else:
            print(f"❌ File non trovato: {file_path}")

if __name__ == "__main__":
    main()
