#!/usr/bin/env python3
"""
CanaryTrap - система проактивного виявлення OSINT-розвідки
Головний файл запуску
"""

import os
import sys
import threading
import time
import schedule
from datetime import datetime

# Додаємо шлях до проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app, db
from core.token_generator import TokenGenerator
from core.deploy import DeployEngine
from core.monitor import Monitor
from core.alert_system import AlertSystem
from config import Config

class CanaryTrap:
    """Головний клас системи"""
    
    def __init__(self):
        self.token_generator = TokenGenerator()
        self.deploy_engine = DeployEngine()
        self.monitor = Monitor()
        self.alert_system = AlertSystem()
        self.running = False
        
    def initialize_database(self):
        """Ініціалізація бази даних"""
        with app.app_context():
            db.create_all()
            from web.app import _migrate_sqlite_schema
            _migrate_sqlite_schema()
            print("✅ Базу даних ініціалізовано")
    
    def start_background_tasks(self):
        """Запуск фонових задач"""
        def run_schedule():
            while self.running:
                schedule.run_pending()
                time.sleep(1)
        
        # Планування задач
        schedule.every(Config.DEPLOY_INTERVAL).seconds.do(self.deploy_engine.deploy_all)
        schedule.every(Config.MONITOR_INTERVAL).seconds.do(self.monitor.check_all)
        
        # Запуск в окремому потоці
        thread = threading.Thread(target=run_schedule)
        thread.daemon = True
        thread.start()
        print("✅ Фонові задачі запущено")
    
    def run(self):
#         """Запуск системи"""
#         print("""
# ╔══════════════════════════════════════════════╗
# ║     🚀 CanaryTrap v1.0                       ║
# ║     Система проактивного виявлення OSINT     ║
# ╚══════════════════════════════════════════════╝
#         """)
        
        self.initialize_database()
        self.running = True
        self.start_background_tasks()
        
        print(f"\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
        print(f"📊 Веб-інтерфейс: http://localhost:{Config.APP_PORT}")
        print(f"🌐 PUBLIC_BASE_URL: {Config.PUBLIC_BASE_URL}")
        print(f"   URL-токени: {Config.PUBLIC_BASE_URL}/{Config.CANARY_LINK_PREFIX}/<slug> (коротке посилання; префікс: CANARY_LINK_PREFIX)")
        print(f"   Тест з телефону: {Config.PUBLIC_BASE_URL}/api/ping  → має бути {{\"ok\": true}}")
        # print("🔍 Моніторинг активовано. Чекаю на активації...\n")
        
        # Запуск веб-сервера
        app.run(debug=True, host='0.0.0.0', port=Config.APP_PORT)

if __name__ == "__main__":
    system = CanaryTrap()
    system.run()