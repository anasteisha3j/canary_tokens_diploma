#!/usr/bin/env python3
"""
Тестування CanaryTrap - імітація OSINT-атак
Запускає фейкові активації для перевірки системи
"""

import sys
import os
import requests
import random
import time
from datetime import datetime

# Додаємо шлях до проекту
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.token_generator import TokenGenerator

class FakeAttacker:
    """Імітація атакувальника"""
    
    def __init__(self, target_url="http://localhost:8080"):
        self.target_url = target_url
        self.gen = TokenGenerator()
        
        # Список фейкових IP (різні країни)
        self.ips = [
            ("95.67.123.45", "Україна", "Київ"),
            ("185.23.45.67", "Росія", "Москва"),
            ("45.33.22.11", "США", "Нью-Йорк"),
            ("89.12.34.56", "Польща", "Варшава"),
            ("103.45.67.89", "Китай", "Пекін"),
        ]
        
        # User-Agents
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "python-requests/2.31.0",
            "curl/7.68.0",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15",
        ]
    
    def generate_test_tokens(self, count=10):
        """Генерація тестових токенів"""
        print(f"\n🎯 Генеруємо {count} тестових токенів...")
        
        tokens = self.gen.generate_mixed({
            'aws_key': count//2,
            'github_token': count//2,
            'url': 2,
            'document': 2
        })
        
        print(f"✅ Згенеровано {len(tokens)} токенів")
        return tokens
    
    def simulate_activation(self, token_id):
        """Симуляція активації токена"""
        ip, country, city = random.choice(self.ips)
        user_agent = random.choice(self.user_agents)
        
        print(f"\n🕵️ Імітація активації:")
        print(f"   Токен: {token_id}")
        print(f"   IP: {ip} ({country}, {city})")
        print(f"   User-Agent: {user_agent[:30]}...")
        
        # Відправляємо запит до API
        try:
            response = requests.get(
                f"{self.target_url}/api/trigger/{token_id}",
                headers={'User-Agent': user_agent},
                timeout=2
            )
            
            if response.status_code == 200:
                print("   ✅ Система отримала активацію!")
                return True
            else:
                print(f"   ❌ Помилка: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"   ❌ Помилка: {e}")
            return False
    
    def run_test_sequence(self, num_activations=5):
        """Запуск послідовності тестів"""
        print("""
╔══════════════════════════════════════════╗
║  🔬 CanaryTrap - ТЕСТУВАННЯ СИСТЕМИ     ║
║  Імітація OSINT-атак                     ║
╚══════════════════════════════════════════╝
        """)
        
        # Генеруємо тестові токени
        tokens = self.generate_test_tokens(10)
        
        print(f"\n⏳ Запускаємо {num_activations} тестових активацій...")
        time.sleep(2)
        
        success = 0
        for i in range(num_activations):
            token = random.choice(tokens)
            print(f"\n--- Тест {i+1} ---")
            
            if self.simulate_activation(token['id']):
                success += 1
            
            # Пауза між активаціями
            time.sleep(random.uniform(1, 3))
        
        # Результати
        print(f"\n📊 РЕЗУЛЬТАТИ ТЕСТУВАННЯ:")
        print(f"   ✅ Успішних активацій: {success}/{num_activations}")
        print(f"   ❌ Помилок: {num_activations - success}")
        
        if success == num_activations:
            print("\n🎉 СИСТЕМА ПРАЦЮЄ КОРЕКТНО!")
        else:
            print("\n⚠️ Є проблеми - перевірте систему")

if __name__ == "__main__":
    attacker = FakeAttacker()
    
    # Питаємо URL
    url = input("Введіть URL CanaryTrap (Enter для http://localhost:8080): ").strip()
    if url:
        attacker.target_url = url
    
    # Питаємо кількість тестів
    num = input("Кількість тестових активацій (Enter для 5): ").strip()
    num = int(num) if num else 5
    
    # Запуск
    attacker.run_test_sequence(num)