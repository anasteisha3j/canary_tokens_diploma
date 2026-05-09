#!/usr/bin/env python3
"""Швидкий тест всієї системи CanaryTrap"""

import os
import sys
import requests
import json
from datetime import datetime

# Налаштування
BASE_URL = "http://localhost:8080"
TEST_USER = {"username": "admin", "password": "admin123"}

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def print_test(name, status, details=""):
    symbol = "✅" if status else "❌"
    color = Colors.GREEN if status else Colors.RED
    print(f"{color}{symbol} {name}{Colors.RESET}")
    if details:
        print(f"   {details}")

def run_quick_test():
    # print(f"\n{Colors.BLUE}╔══════════════════════════════════════════════════════════╗{Colors.RESET}")
    # print(f"{Colors.BLUE}║     CanaryTrap - Швидкий тест системи                     ║{Colors.RESET}")
    # print(f"{Colors.BLUE}╚══════════════════════════════════════════════════════════╝{Colors.RESET}")
    
    session = requests.Session()
    results = []
    
    # 1. Тест API ping
    try:
        r = session.get(f"{BASE_URL}/api/ping", timeout=2)
        print_test("API доступний", r.status_code == 200, f"статус: {r.status_code}")
        results.append(r.status_code == 200)
    except Exception as e:
        print_test("API доступний", False, f"помилка: {e}")
        results.append(False)
        print(f"\n{Colors.RED}❌ Сервер не відповідає! Запустіть python run.py{Colors.RESET}")
        return
    
    # 2. Тест логіну
    try:
        r = session.post(f"{BASE_URL}/login", data=TEST_USER)
        login_ok = "dashboard" in r.text.lower() or "tokens" in r.text.lower()
        print_test("Логін адміністратора", login_ok)
        results.append(login_ok)
    except Exception as e:
        print_test("Логін адміністратора", False, f"помилка: {e}")
        results.append(False)
    
    # 3. Тест дашборду
    try:
        r = session.get(f"{BASE_URL}/dashboard")
        dashboard_ok = r.status_code == 200
        print_test("Дашборд доступний", dashboard_ok)
        results.append(dashboard_ok)
    except:
        print_test("Дашборд доступний", False)
        results.append(False)
    
    # 4. Тест API статистики
    try:
        r = session.get(f"{BASE_URL}/api/stats")
        stats_ok = r.status_code == 200 and 'tokens' in r.json()
        print_test("API статистики", stats_ok)
        if stats_ok:
            data = r.json()
            print(f"   📊 Токенів: {data.get('tokens', 0)}, Активацій: {data.get('activations', 0)}")
        results.append(stats_ok)
    except:
        print_test("API статистики", False)
        results.append(False)
    
    # 5. Тест генерації токена
    try:
        r = session.post(f"{BASE_URL}/tokens/generate", data={
            'token_type': 'aws_key',
            'count': 1,
            'platforms': []
        }, allow_redirects=True)
        
        gen_ok = r.status_code == 200
        print_test("Генерація токена", gen_ok)
        if gen_ok:
            print(f"   ✅ Токен створено")
        results.append(gen_ok)
    except Exception as e:
        print_test("Генерація токена", False, f"помилка: {e}")
        results.append(False)
    
    # 6. Тест списку токенів
    try:
        r = session.get(f"{BASE_URL}/tokens")
        tokens_ok = r.status_code == 200
        print_test("Сторінка токенів", tokens_ok)
        results.append(tokens_ok)
    except:
        print_test("Сторінка токенів", False)
        results.append(False)
    
    # 7. Тест активацій
    try:
        r = session.get(f"{BASE_URL}/activations")
        activations_ok = r.status_code == 200
        print_test("Сторінка активацій", activations_ok)
        results.append(activations_ok)
    except:
        print_test("Сторінка активацій", False)
        results.append(False)
    
    # 8. Тест налаштувань
    try:
        r = session.get(f"{BASE_URL}/settings")
        settings_ok = r.status_code == 200
        print_test("Сторінка налаштувань", settings_ok)
        results.append(settings_ok)
    except:
        print_test("Сторінка налаштувань", False)
        results.append(False)
    
    # Підсумок
    print(f"\n{Colors.BLUE}{'='*54}{Colors.RESET}")
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"{Colors.GREEN}ВСІ ТЕСТИ ПРОЙДЕНО! ({passed}/{total}){Colors.RESET}")
        print(f"{Colors.GREEN}✅ Система працює коректно{Colors.RESET}")
    elif passed >= total - 2:
        print(f"{Colors.YELLOW}⚠️ БІЛЬШІСТЬ ТЕСТІВ ПРОЙДЕНО ({passed}/{total}){Colors.RESET}")
        print(f"{Colors.YELLOW}⚠️ Є невеликі проблеми, але система функціонує{Colors.RESET}")
    else:
        print(f"{Colors.RED}❌ ПРОБЛЕМИ В СИСТЕМІ ({passed}/{total}){Colors.RESET}")
        print(f"{Colors.RED}❌ Перевірте логи та налаштування{Colors.RESET}")
    
    return passed == total

if __name__ == "__main__":
    success = run_quick_test()
    sys.exit(0 if success else 1)