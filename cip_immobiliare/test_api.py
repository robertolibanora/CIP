#!/usr/bin/env python3
"""
Test rapido delle API CIP Immobiliare
Esegui con: python test_api.py
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_register():
    """Test registrazione utente"""
    print("🧪 Test registrazione...")
    data = {
        "email": "test@example.com",
        "password": "password123",
        "full_name": "Test User"
    }
    response = requests.post(f"{BASE_URL}/auth/register", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_login():
    """Test login"""
    print("\n🧪 Test login...")
    data = {
        "email": "test@example.com",
        "password": "password123"
    }
    response = requests.post(f"{BASE_URL}/auth/login", json=data)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 200:
        # Salva i cookie per i test successivi
        global cookies
        cookies = response.cookies
        return True
    return False

def test_dashboard():
    """Test dashboard utente"""
    print("\n🧪 Test dashboard...")
    response = requests.get(f"{BASE_URL}/", cookies=cookies)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    return response.status_code == 200

def test_admin_metrics():
    """Test metriche admin (dovrebbe fallire per utente normale)"""
    print("\n🧪 Test metriche admin (utente normale)...")
    response = requests.get(f"{BASE_URL}/admin/metrics", cookies=cookies)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    return response.status_code == 403  # Dovrebbe essere forbidden

def main():
    """Esegui tutti i test"""
    print("🚀 Test API CIP Immobiliare")
    print("=" * 40)
    
    # Assicurati che l'app sia in esecuzione
    try:
        requests.get(f"{BASE_URL}/auth/login", timeout=5)
    except requests.exceptions.ConnectionError:
        print("❌ Errore: L'applicazione non è in esecuzione")
        print("Avvia con: export FLASK_APP=admin.py && flask run --debug")
        return
    
    print("✅ Applicazione raggiungibile")
    
    # Esegui test
    tests = [
        test_register,
        test_login,
        test_dashboard,
        test_admin_metrics
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
                print("✅ Test passato")
            else:
                print("❌ Test fallito")
        except Exception as e:
            print(f"❌ Errore nel test: {e}")
    
    print(f"\n📊 Risultati: {passed}/{len(tests)} test passati")
    
    if passed == len(tests):
        print("🎉 Tutti i test sono passati!")
    else:
        print("⚠️  Alcuni test sono falliti")

if __name__ == "__main__":
    main()
