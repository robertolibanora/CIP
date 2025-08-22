#!/usr/bin/env python3
"""
Monitoraggio e metriche per CIP Immobiliare
"""

import psutil
import time
import json
from datetime import datetime, timedelta
from database import get_connection

class CIPMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        
    def get_system_metrics(self):
        """Ottiene metriche del sistema"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available_gb': round(memory.available / (1024**3), 2),
                'disk_percent': disk.percent,
                'disk_free_gb': round(disk.free / (1024**3), 2)
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_database_metrics(self):
        """Ottiene metriche del database"""
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Conteggio tabelle
                    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
                    table_count = cur.fetchone()['count']
                    
                    # Conteggio utenti
                    cur.execute("SELECT COUNT(*) FROM users")
                    user_count = cur.fetchone()['count']
                    
                    # Conteggio progetti
                    cur.execute("SELECT COUNT(*) FROM projects")
                    project_count = cur.fetchone()['count']
                    
                    # Conteggio investimenti
                    cur.execute("SELECT COUNT(*) FROM investments")
                    investment_count = cur.fetchone()['count']
                    
                    # Conteggio richieste in attesa
                    cur.execute("SELECT COUNT(*) FROM investment_requests WHERE state = 'in_review'")
                    pending_requests = cur.fetchone()['count']
                    
                    # Dimensione database
                    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                    db_size = cur.fetchone()['pg_size_pretty']
                    
                    return {
                        'timestamp': datetime.now().isoformat(),
                        'table_count': table_count,
                        'user_count': user_count,
                        'project_count': project_count,
                        'investment_count': investment_count,
                        'pending_requests': pending_requests,
                        'database_size': db_size
                    }
        except Exception as e:
            return {'error': str(e)}
    
    def get_application_metrics(self):
        """Ottiene metriche dell'applicazione"""
        uptime = time.time() - self.start_time
        
        return {
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': int(uptime),
            'uptime_human': str(timedelta(seconds=int(uptime))),
            'request_count': self.request_count,
            'error_count': self.error_count,
            'success_rate': round(((self.request_count - self.error_count) / max(self.request_count, 1)) * 100, 2)
        }
    
    def get_all_metrics(self):
        """Ottiene tutte le metriche"""
        return {
            'system': self.get_system_metrics(),
            'database': self.get_database_metrics(),
            'application': self.get_application_metrics()
        }
    
    def increment_request(self):
        """Incrementa il contatore delle richieste"""
        self.request_count += 1
    
    def increment_error(self):
        """Incrementa il contatore degli errori"""
        self.error_count += 1
    
    def save_metrics(self, filename='metrics.json'):
        """Salva le metriche in un file JSON"""
        try:
            metrics = self.get_all_metrics()
            with open(filename, 'w') as f:
                json.dump(metrics, f, indent=2, default=str)
            return True
        except Exception as e:
            print(f"Errore nel salvataggio metriche: {e}")
            return False

def create_monitoring_endpoint(app):
    """Crea endpoint di monitoraggio per Flask"""
    monitor = CIPMonitor()
    
    @app.route('/health')
    def health_check():
        """Health check endpoint"""
        try:
            # Verifica database
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
            
            return {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'disconnected',
                'error': str(e)
            }, 500
    
    @app.route('/metrics')
    def metrics():
        """Endpoint metriche"""
        monitor.increment_request()
        try:
            return monitor.get_all_metrics()
        except Exception as e:
            monitor.increment_error()
            return {'error': str(e)}, 500
    
    @app.route('/metrics/system')
    def system_metrics():
        """Metriche sistema"""
        monitor.increment_request()
        try:
            return monitor.get_system_metrics()
        except Exception as e:
            monitor.increment_error()
            return {'error': str(e)}, 500
    
    @app.route('/metrics/database')
    def database_metrics():
        """Metriche database"""
        monitor.increment_request()
        try:
            return monitor.get_database_metrics()
        except Exception as e:
            monitor.increment_error()
            return {'error': str(e)}, 500
    
    return monitor

if __name__ == "__main__":
    # Test standalone
    monitor = CIPMonitor()
    
    print("📊 Metriche Sistema:")
    print(json.dumps(monitor.get_system_metrics(), indent=2))
    
    print("\n📊 Metriche Database:")
    print(json.dumps(monitor.get_database_metrics(), indent=2))
    
    print("\n📊 Metriche Applicazione:")
    print(json.dumps(monitor.get_application_metrics(), indent=2))
