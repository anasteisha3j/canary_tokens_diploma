#!/usr/bin/env python3
"""
Автоматичне тестування GitHub деплою CanaryTrap
Перевіряє розміщення токенів у репозиторії
"""

import os
import sys
import time
import requests
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8080"
TEST_USER = {"username": "admin", "password": "admin123"}

class GitHubDeployTester:
    def __init__(self):
        self.session = requests.Session()
        self.results = []
    
    def log(self, msg: str):
        print(f"  {msg}")
    
    def test_connection(self) -> bool:
        print("\n[1] Перевірка підключення")
        try:
            response = self.session.get(f"{BASE_URL}/api/ping", timeout=3)
            if response.status_code == 200:
                self.log("Сервер доступний")
                return True
            return False
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_login(self) -> bool:
        print("\n[2] Вхід адміністратора")
        try:
            response = self.session.post(f"{BASE_URL}/login", data=TEST_USER)
            success = "dashboard" in response.text.lower() or response.status_code == 302
            if success:
                self.log("Вхід виконано")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_github_settings(self, repo: str, token: str, branch: str = "main") -> bool:
        print("\n[3] Налаштування GitHub")
        try:
            response = self.session.post(f"{BASE_URL}/api/save-deploy-settings", json={
                'github_repo': repo,
                'github_branch': branch,
                'github_token': token
            })
            success = response.status_code == 200 and response.json().get('status') == 'success'
            if success:
                self.log(f"Репозиторій: {repo}, Гілка: {branch}")
            else:
                self.log("Помилка збереження налаштувань")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_generate_document_token(self) -> bool:
        print("\n[4] Генерація документа-приманки")
        try:
            response = self.session.post(f"{BASE_URL}/tokens/generate", data={
                'token_type': 'document',
                'count': 1,
                'platforms': []
            }, allow_redirects=True)
            success = response.status_code == 200
            if success:
                self.log("Документ створено")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_deploy_to_github(self) -> bool:
        print("\n[5] Деплой на GitHub")
        try:
            response = self.session.post(f"{BASE_URL}/api/deploy/github")
            success = response.status_code == 200
            result = response.json()
            
            if success:
                self.log(f"Результат: {result.get('message', 'Успішно')}")
            else:
                self.log(f"Помилка: {result.get('message', 'Невідома')}")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_deploy_single_token(self, token_id: int) -> bool:
        print(f"\n[6] Деплой конкретного токена {token_id}")
        try:
            response = self.session.post(f"{BASE_URL}/tokens/{token_id}/deploy-github")
            success = response.status_code == 200
            result = response.json()
            
            if success:
                self.log(f"URL: {result.get('url', 'Успішно')}")
            else:
                self.log(f"Помилка: {result.get('message', 'Невідома')}")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def verify_github_file(self, repo: str, filename: str, github_token: str) -> bool:
        print("\n[7] Перевірка файлу на GitHub")
        try:
            # Перевіряємо чи файл з'явився в репозиторії
            url = f"https://api.github.com/repos/{repo}/contents/canary-docs"
            headers = {
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github+json'
            }
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                files = response.json()
                doc_files = [f for f in files if f['name'].endswith('.html') or f['name'].endswith('.pdf')]
                if doc_files:
                    self.log(f"Знайдено файли: {[f['name'] for f in doc_files]}")
                    return True
                else:
                    self.log("Документи не знайдено")
                    return False
            elif response.status_code == 404:
                self.log("Папка canary-docs не існує")
                return False
            else:
                self.log(f"Помилка GitHub API: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def save_report(self, results: list):
        filename = f"github_deploy_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("ЗВІТ ТЕСТУВАННЯ GITHUB ДЕПЛОЮ\n")
            f.write("="*60 + "\n\n")
            for r in results:
                status = "ПРОЙДЕНО" if r['passed'] else "НЕ ПРОЙДЕНО"
                f.write(f"[{r['name']}] {status}\n")
                if r.get('details'):
                    f.write(f"  {r['details']}\n")
            f.write("\n" + "="*60 + "\n")
        print(f"\nЗвіт збережено: {filename}")
    
    def run(self):
        print("""
===========================================================================
     ТЕСТУВАННЯ GITHUB ДЕПЛОЮ
     Перевірка розміщення токенів у репозиторії
===========================================================================
        """)
        
        results = []
        
        # Отримуємо налаштування від користувача
        print("\nВведіть дані для GitHub деплою:")
        repo = input("  Репозиторій (формат: username/repo): ").strip()
        github_token = input("  GitHub токен: ").strip()
        branch = input("  Гілка (Enter для main): ").strip() or "main"
        
        if not repo or not github_token:
            print("\nПОМИЛКА: Репозиторій та токен обов'язкові")
            return
        
        # Виконання тестів
        results.append({'name': 'Підключення до сервера', 'passed': self.test_connection()})
        results.append({'name': 'Авторизація', 'passed': self.test_login()})
        results.append({'name': 'Налаштування GitHub', 'passed': self.test_github_settings(repo, github_token, branch)})
        results.append({'name': 'Генерація документа', 'passed': self.test_generate_document_token()})
        results.append({'name': 'Деплой на GitHub', 'passed': self.test_deploy_to_github()})
        
        # Перевірка наявності файлу на GitHub
        time.sleep(3)  # Чекаємо поки GitHub обробить
        results.append({'name': 'Перевірка файлу на GitHub', 
                       'passed': self.verify_github_file(repo, "", github_token)})
        
        # Підсумок
        passed = sum(1 for r in results if r['passed'])
        total = len(results)
        
        print("\n" + "="*60)
        print(f"РЕЗУЛЬТАТ: {passed}/{total} тестів пройдено")
        if passed == total:
            print("GitHub деплой працює коректно")
        else:
            print("Є проблеми з GitHub деплоєм")
        print("="*60)
        
        self.save_report(results)

if __name__ == "__main__":
    tester = GitHubDeployTester()
    tester.run()