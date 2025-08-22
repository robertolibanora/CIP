#!/usr/bin/env python3
"""
Test completo delle API CIP Immobiliare
Esegui con: python test_complete.py
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "http://localhost:5000"

class CIPAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.test_results = []
        self.admin_user_id = None
        self.test_user_id = None
        
    def log_test(self, test_name, success, details=""):
        """Logga il risultato di un test"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_health_check(self):
        """Test base di connessione"""
        try:
            response = self.session.get(f"{BASE_URL}/auth/login")
            if response.status_code == 200:
                self.log_test("Health Check", True, "Applicazione raggiungibile")
                return True
            else:
                self.log_test("Health Check", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Health Check", False, f"Errore: {e}")
            return False
    
    def test_register_user(self):
        """Test registrazione utente"""
        try:
            data = {
                "email": "test@example.com",
                "password": "password123",
                "full_name": "Test User"
            }
            response = self.session.post(f"{BASE_URL}/auth/register", json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.test_user_id = result.get('id')
                self.log_test("Registrazione Utente", True, f"ID: {self.test_user_id}")
                return True
            else:
                self.log_test("Registrazione Utente", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Registrazione Utente", False, f"Errore: {e}")
            return False
    
    def test_login_user(self):
        """Test login utente"""
        try:
            data = {
                "email": "test@example.com",
                "password": "password123"
            }
            response = self.session.post(f"{BASE_URL}/auth/login", json=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    self.log_test("Login Utente", True, "Sessione creata")
                    return True
                else:
                    self.log_test("Login Utente", False, "Login fallito")
                    return False
            else:
                self.log_test("Login Utente", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Login Utente", False, f"Errore: {e}")
            return False
    
    def test_user_dashboard(self):
        """Test dashboard utente"""
        try:
            response = self.session.get(f"{BASE_URL}/")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Dashboard Utente", True, f"Dati: {list(result.keys())}")
                return True
            else:
                self.log_test("Dashboard Utente", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Dashboard Utente", False, f"Errore: {e}")
            return False
    
    def test_user_portfolio(self):
        """Test portafoglio utente"""
        try:
            response = self.session.get(f"{BASE_URL}/portfolio")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Portafoglio Utente", True, f"Tab: {result.get('tab')}")
                return True
            else:
                self.log_test("Portafoglio Utente", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Portafoglio Utente", False, f"Errore: {e}")
            return False
    
    def test_user_documents(self):
        """Test documenti utente"""
        try:
            response = self.session.get(f"{BASE_URL}/documents")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Documenti Utente", True, f"Count: {len(result)}")
                return True
            else:
                self.log_test("Documenti Utente", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Documenti Utente", False, f"Errore: {e}")
            return False
    
    def test_admin_access_denied(self):
        """Test che utente normale non possa accedere ad admin"""
        try:
            response = self.session.get(f"{BASE_URL}/admin/")
            
            if response.status_code == 403:
                self.log_test("Accesso Admin Negato", True, "Autorizzazione corretta")
                return True
            else:
                self.log_test("Accesso Admin Negato", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Accesso Admin Negato", False, f"Errore: {e}")
            return False
    
    def test_logout(self):
        """Test logout"""
        try:
            response = self.session.get(f"{BASE_URL}/auth/logout")
            
            if response.status_code == 302:  # Redirect
                self.log_test("Logout", True, "Sessione terminata")
                return True
            else:
                self.log_test("Logout", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Logout", False, f"Errore: {e}")
            return False
    
    def test_register_admin(self):
        """Test registrazione admin"""
        try:
            data = {
                "email": "admin@cip.com",
                "password": "admin123",
                "full_name": "Administrator"
            }
            response = self.session.post(f"{BASE_URL}/auth/register", json=data)
            
            if response.status_code == 200:
                result = response.json()
                self.admin_user_id = result.get('id')
                self.log_test("Registrazione Admin", True, f"ID: {self.admin_user_id}")
                return True
            else:
                self.log_test("Registrazione Admin", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Registrazione Admin", False, f"Errore: {e}")
            return False
    
    def test_login_admin(self):
        """Test login admin"""
        try:
            data = {
                "email": "admin@cip.com",
                "password": "admin123"
            }
            response = self.session.post(f"{BASE_URL}/auth/login", json=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    self.log_test("Login Admin", True, "Sessione admin creata")
                    return True
                else:
                    self.log_test("Login Admin", False, "Login admin fallito")
                    return False
            else:
                self.log_test("Login Admin", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Login Admin", False, f"Errore: {e}")
            return False
    
    def test_admin_dashboard(self):
        """Test dashboard admin"""
        try:
            response = self.session.get(f"{BASE_URL}/admin/")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Dashboard Admin", True, f"Dati: {list(result.keys())}")
                return True
            else:
                self.log_test("Dashboard Admin", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Dashboard Admin", False, f"Errore: {e}")
            return False
    
    def test_admin_users(self):
        """Test lista utenti admin"""
        try:
            response = self.session.get(f"{BASE_URL}/admin/users")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Lista Utenti Admin", True, f"Count: {len(result)}")
                return True
            else:
                self.log_test("Lista Utenti Admin", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Lista Utenti Admin", False, f"Errore: {e}")
            return False
    
    def test_admin_projects(self):
        """Test lista progetti admin"""
        try:
            response = self.session.get(f"{BASE_URL}/admin/projects")
            
            if response.status_code == 200:
                result = response.json()
                self.log_test("Lista Progetti Admin", True, f"Count: {len(result)}")
                return True
            else:
                self.log_test("Lista Progetti Admin", False, f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.log_test("Lista Progetti Admin", False, f"Errore: {e}")
            return False
    
    def run_all_tests(self):
        """Esegue tutti i test in sequenza"""
        print("🚀 Test Completo API CIP Immobiliare")
        print("=" * 50)
        
        # Verifica che l'app sia in esecuzione
        if not self.test_health_check():
            print("❌ Applicazione non raggiungibile. Avvia con: flask run --debug")
            return
        
        # Test utente
        print("\n👤 Test Utente:")
        self.test_register_user()
        self.test_login_user()
        self.test_user_dashboard()
        self.test_user_portfolio()
        self.test_user_documents()
        self.test_admin_access_denied()
        self.test_logout()
        
        # Test admin
        print("\n👑 Test Admin:")
        self.test_register_admin()
        self.test_login_admin()
        self.test_admin_dashboard()
        self.test_admin_users()
        self.test_admin_projects()
        
        # Riepilogo
        print("\n" + "=" * 50)
        print("📊 RIEPILOGO TEST")
        print("=" * 50)
        
        passed = sum(1 for result in self.test_results if result['success'])
        total = len(self.test_results)
        
        print(f"Test Passati: {passed}/{total}")
        print(f"Percentuale Successo: {(passed/total)*100:.1f}%")
        
        if passed == total:
            print("🎉 TUTTI I TEST SONO PASSATI!")
        else:
            print("⚠️  Alcuni test sono falliti")
            print("\nTest falliti:")
            for result in self.test_results:
                if not result['success']:
                    print(f"  ❌ {result['test']}: {result['details']}")
        
        # Salva risultati
        with open('test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2)
        print(f"\n📝 Risultati salvati in: test_results.json")

def main():
    """Funzione principale"""
    tester = CIPAPITester()
    tester.run_all_tests()

if __name__ == "__main__":
    main()
