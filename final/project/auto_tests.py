#!/usr/bin/env python3
"""
Автоматичне тестування CanaryTrap
Генерація та активація ВСІХ типів токенів
"""

import os
import sys
import time
from typing import Dict, Optional
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8080"
TEST_USER = {"username": "admin", "password": "admin123"}

class TestReport:
    def __init__(self):
        self.tests = []
        self.start_time = datetime.now()
        self.generated_tokens = {}
        self.triggered_tokens = {}
    
    def add(self, name: str, passed: bool, details: str = ""):
        self.tests.append({
            "name": name,
            "passed": passed,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def generate(self) -> str:
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        passed = sum(1 for t in self.tests if t["passed"])
        
        report = f"""
{'='*70}
ЗВІТ ТЕСТУВАННЯ - CanaryTrap
{'='*70}
Дата: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Тривалість: {duration:.2f} секунд
Результат: {passed}/{len(self.tests)} тестів пройдено ({passed*100//len(self.tests)}%)

{'='*70}
ДЕТАЛЬНІ РЕЗУЛЬТАТИ
{'='*70}
"""
        for i, test in enumerate(self.tests, 1):
            status = "ПРОЙДЕНО" if test["passed"] else "НЕ ПРОЙДЕНО"
            report += f"\n[{i}] {status}\n"
            report += f"    Тест: {test['name']}\n"
            if test["details"]:
                report += f"    Деталі: {test['details']}\n"
        
        report += f"\n{'='*70}\n"
        if self.generated_tokens:
            report += "\nСТВОРЕНІ ТОКЕНИ:\n"
            for token_type, token_id in self.generated_tokens.items():
                status = "АКТИВОВАНО" if token_id in self.triggered_tokens.values() else "АКТИВНИЙ"
                report += f"  - {token_type}: {token_id} [{status}]\n"
        
        report += f"\n{'='*70}\n"
        report += f"ПІДСУМОК: {'УСПІШНО' if passed == len(self.tests) else 'НЕВДАЛО'}\n"
        report += f"{'='*70}\n"
        
        return report

class CanaryTrapTester:
    def __init__(self):
        self.session = requests.Session()
        self.report = TestReport()
    
    def log(self, msg: str):
        print(f"  {msg}")
    
    def get_token_id_from_db(self, token_type: str) -> Optional[str]:
        """Отримує токен ID з БД за типом"""
        try:
            from web.app import app, db, Token
            
            with app.app_context():
                token = Token.query.filter_by(token_type=token_type, status='active').first()
                if token:
                    return token.token_id
                return None
        except Exception as e:
            self.log(f"Помилка БД: {e}")
            return None
    
    def get_all_active_tokens(self) -> Dict[str, str]:
        """Отримує всі активні токени з БД"""
        try:
            from web.app import app, db, Token
            
            tokens = {}
            with app.app_context():
                for token in Token.query.filter_by(status='active').all():
                    tokens[token.token_type] = token.token_id
            return tokens
        except Exception as e:
            self.log(f"Помилка БД: {e}")
            return {}
    
    def test_connection(self) -> bool:
        print("\n[ТЕСТ 1] Перевірка підключення")
        
        try:
            response = self.session.get(f"{BASE_URL}/api/ping", timeout=3)
            success = response.status_code == 200 and response.json().get("ok")
            self.report.add("Підключення до сервера", success, f"URL: {BASE_URL}")
            return success
        except Exception as e:
            self.report.add("Підключення до сервера", False, str(e))
            return False
    
    def test_login(self) -> bool:
        print("\n[ТЕСТ 2] Авторизація")
        
        try:
            response = self.session.post(f"{BASE_URL}/login", data=TEST_USER)
            success = "dashboard" in response.text.lower() or response.status_code == 302
            self.report.add("Вхід адміністратора", success, f"Користувач: {TEST_USER['username']}")
            return success
        except Exception as e:
            self.report.add("Вхід адміністратора", False, str(e))
            return False
    
    def generate_tokens(self, token_type: str, count: int = 2) -> bool:
        """Генерація токенів певного типу"""
        print(f"\n[ТЕСТ] Генерація токенів типу {token_type}")
        
        try:
            response = self.session.post(f"{BASE_URL}/tokens/generate", data={
                'token_type': token_type,
                'count': count,
                'platforms': []
            }, allow_redirects=True)
            
            success = response.status_code == 200
            self.report.add(f"Генерація {token_type}", success, f"Створено {count} токенів")
            
            if success:
                self.log(f"Створено {count} токенів типу {token_type}")
                time.sleep(1)
            return success
        except Exception as e:
            self.report.add(f"Генерація {token_type}", False, str(e))
            return False
    
    def trigger_token(self, token_type: str, token_id: str) -> bool:
        """Активація конкретного токена"""
        print(f"\n[ТЕСТ] Активація токена типу {token_type}")
        
        try:
            response = self.session.get(f"{BASE_URL}/api/trigger/{token_id}")
            success = response.status_code == 200 and response.json().get('status') == 'triggered'
            
            self.report.add(f"Активація {token_type}", success, f"ID токена: {token_id[:16]}...")
            
            if success:
                self.log(f"Токен {token_type} успішно активовано")
                self.report.triggered_tokens[token_type] = token_id
            return success
        except Exception as e:
            self.report.add(f"Активація {token_type}", False, str(e))
            return False
    
    def trigger_all_token_types(self) -> bool:
        """Активує по одному токену КОЖНОГО типу"""
        print("\n[ТЕСТ] Активація всіх типів токенів")
        
        tokens = self.get_all_active_tokens()
        
        if not tokens:
            self.log("Не знайдено активних токенів у базі даних")
            self.report.add("Активація всіх типів токенів", False, "Не знайдено активних токенів")
            return False
        
        self.log(f"Знайдено {len(tokens)} типів токенів: {', '.join(tokens.keys())}")
        
        success_count = 0
        for token_type, token_id in tokens.items():
            if self.trigger_token(token_type, token_id):
                success_count += 1
            time.sleep(0.5)
        
        all_success = success_count == len(tokens)
        self.report.add("Активація всіх типів токенів", all_success, 
                       f"Активовано {success_count}/{len(tokens)} типів")
        
        return all_success
    
    def test_get_tokens_list(self) -> bool:
        print("\n[ТЕСТ] Сторінка токенів")
        
        try:
            response = self.session.get(f"{BASE_URL}/tokens")
            success = response.status_code == 200
            self.report.add("Доступ до сторінки токенів", success, "Сторінка токенів доступна")
            return success
        except Exception as e:
            self.report.add("Доступ до сторінки токенів", False, str(e))
            return False
    
    def test_get_activations_list(self) -> bool:
        print("\n[ТЕСТ] Сторінка активацій")
        
        try:
            response = self.session.get(f"{BASE_URL}/activations")
            success = response.status_code == 200
            self.report.add("Доступ до сторінки активацій", success, "Сторінка активацій доступна")
            return success
        except Exception as e:
            self.report.add("Доступ до сторінки активацій", False, str(e))
            return False
    
    def test_api_stats(self) -> bool:
        print("\n[ТЕСТ] API статистика")
        
        try:
            response = self.session.get(f"{BASE_URL}/api/stats")
            data = response.json()
            
            success = response.status_code == 200 and 'tokens' in data
            
            self.report.add("API статистика", success, 
                          f"Токенів: {data.get('tokens', 0)}, "
                          f"Активацій: {data.get('activations', 0)}, "
                          f"Активовано: {data.get('triggered', 0)}")
            return success
        except Exception as e:
            self.report.add("API статистика", False, str(e))
            return False
    
    def run_all_tests(self):
        print("""
===============================================================================
     CanaryTrap - АВТОМАТИЧНЕ ТЕСТУВАННЯ
     Перевірка всієї функціональності з активацією всіх типів токенів
===============================================================================
        """)
        
        # Базові тести
        if not self.test_connection():
            print("\nПОМИЛКА: Не вдалося підключитися до сервера")
            print("Запустіть: python run.py")
            return self.report.generate()
        
        if not self.test_login():
            print("\nПОМИЛКА: Не вдалося увійти")
            return self.report.generate()
        
        # Генерація всіх типів токенів
        print("\n--- Генерація токенів ---")
        
        self.generate_tokens('aws_key', 1)
        time.sleep(0.5)
        
        self.generate_tokens('github_token', 1)
        time.sleep(0.5)
        
        self.generate_tokens('url', 1)
        time.sleep(0.5)
        
        self.generate_tokens('document', 1)
        time.sleep(0.5)
        
        self.generate_tokens('mixed', 2)
        time.sleep(0.5)
        
        # Перевірка сторінок
        print("\n--- Доступ до сторінок ---")
        self.test_get_tokens_list()
        self.test_get_activations_list()
        self.test_api_stats()
        
        # Активація КОЖНОГО типу токенів
        print("\n--- Активація токенів ---")
        self.trigger_all_token_types()
        
        # Фінальна статистика
        print("\n--- Фінальна статистика ---")
        self.test_api_stats()
        
        return self.report.generate()

def save_report(report_text: str, filename: str = None):
    if filename is None:
        filename = f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    print(f"\nЗвіт збережено: {filename}")
    return filename

def main():
    tester = CanaryTrapTester()
    report = tester.run_all_tests()
    
    print(report)
    filename = save_report(report)
    
    print(f"\nПовний звіт: {filename}")
    print("\nДля ручної перевірки:")
    print("  - Панель керування: http://localhost:8080/dashboard")
    print("  - Список токенів: http://localhost:8080/tokens")
    print("  - Список активацій: http://localhost:8080/activations")

if __name__ == "__main__":
    main()