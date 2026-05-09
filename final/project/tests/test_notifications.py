#!/usr/bin/env python3
"""
Автоматичне тестування сповіщень CanaryTrap
Перевіряє Telegram, Slack та Email сповіщення
"""

import os
import sys
import time
import requests
import json
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_URL = "http://localhost:8080"
TEST_USER = {"username": "admin", "password": "admin123"}

class NotificationTester:
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
    
    def test_telegram_settings(self, bot_token: str, chat_id: str) -> bool:
        print("\n[3] Налаштування Telegram")
        try:
            response = self.session.post(f"{BASE_URL}/api/save-notification-settings", json={
                'telegram_bot': bot_token,
                'telegram_chat': chat_id
            })
            success = response.status_code == 200 and response.json().get('status') == 'success'
            if success:
                self.log("Telegram налаштовано")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_slack_settings(self, webhook_url: str) -> bool:
        print("\n[4] Налаштування Slack")
        try:
            response = self.session.post(f"{BASE_URL}/api/save-notification-settings", json={
                'slack_webhook': webhook_url
            })
            success = response.status_code == 200 and response.json().get('status') == 'success'
            if success:
                self.log("Slack налаштовано")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_email_settings(self, email: str) -> bool:
        print("\n[5] Налаштування Email")
        try:
            response = self.session.post(f"{BASE_URL}/api/save-notification-settings", json={
                'alert_email': email
            })
            success = response.status_code == 200 and response.json().get('status') == 'success'
            if success:
                self.log(f"Email налаштовано: {email}")
            return success
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_telegram_webhook(self, bot_token: str, chat_id: str) -> bool:
        print("\n[6] Перевірка Telegram бота")
        try:
            # Перевіряємо чи бот існує та чи правильний токен
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info.get('ok'):
                    self.log(f"Бот знайдено: {bot_info['result']['username']}")
                    
                    # Надсилаємо тестове повідомлення
                    test_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
                    test_response = requests.post(test_url, json={
                        'chat_id': chat_id,
                        'text': "[TEST] CanaryTrap: Тестове сповіщення"
                    }, timeout=10)
                    
                    if test_response.status_code == 200:
                        self.log("Тестове повідомлення надіслано")
                        return True
                    else:
                        self.log(f"Помилка надсилання: {test_response.text}")
                        return False
            else:
                self.log("Невірний токен бота")
                return False
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_slack_webhook(self, webhook_url: str) -> bool:
        print("\n[7] Перевірка Slack webhook")
        try:
            payload = {
                'text': '[TEST] CanaryTrap: Тестове сповіщення з системи моніторингу'
            }
            response = requests.post(webhook_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.log("Тестове повідомлення надіслано в Slack")
                return True
            else:
                self.log(f"Помилка: {response.status_code}")
                return False
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_smtp_email(self, smtp_server: str, smtp_port: int, username: str, password: str, to_email: str, use_auth: bool = None) -> bool:
        print("\n[8] Перевірка Email (SMTP)")
        
        # Якщо use_auth не вказано явно, визначаємо за наявністю логіна
        if use_auth is None:
            use_auth = bool(username and password)
        
        try:
            # Підключаємося до сервера
            if smtp_port == 25:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                self.log(f"Підключено до {smtp_server}:{smtp_port} (без TLS)")
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                server.starttls()
                self.log(f"Підключено до {smtp_server}:{smtp_port} (з TLS)")
            
            # Авторизація (тільки якщо є логін та пароль)
            if use_auth and username and password:
                server.login(username, password)
                self.log("Авторизацію виконано")
                from_email = username
            else:
                self.log("Підключення без авторизації")
                from_email = "canarytrap@test.local"
            
            # Надсилаємо тестовий лист
            msg = MIMEText(
                f"Тестове сповіщення від CanaryTrap\n"
                f"Час: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                "Якщо ви бачите це повідомлення, то сповіщення працюють коректно."
            )
            msg['Subject'] = '[TEST] CanaryTrap - Тест сповіщень'
            msg['From'] = from_email
            msg['To'] = to_email
            
            server.send_message(msg)
            server.quit()
            
            self.log(f"Листа надіслано на {to_email}")
            
            # Підказка для локального тестування
            if smtp_server == "localhost":
                self.log("")
                self.log("Перевірте лист у вашому локальному SMTP-сервері:")
                self.log("  - smtp4dev: відкрийте http://localhost:3000")
                self.log("  - FakeSMTP: лист з'явиться у вікні програми")
            
            return True
            
        except ConnectionRefusedError:
            self.log(f"ПОМИЛКА: Не вдалося підключитися до {smtp_server}:{smtp_port}")
            if smtp_server == "localhost":
                self.log("  Запустіть спочатку локальний SMTP-сервер (smtp4dev або FakeSMTP)")
            return False
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def test_generate_and_trigger(self) -> bool:
        print("\n[9] Генерація та активація токена для перевірки сповіщень")
        try:
            # Генеруємо токен
            gen_response = self.session.post(f"{BASE_URL}/tokens/generate", data={
                'token_type': 'aws_key',
                'count': 1,
                'platforms': []
            }, allow_redirects=True)
            
            if gen_response.status_code != 200:
                self.log("Помилка генерації токена")
                return False
            
            self.log("Токен створено")
            time.sleep(1)
            
            # Отримуємо ID токена з БД
            from web.app import app, db, Token
            with app.app_context():
                token = Token.query.filter_by(token_type='aws_key', status='active').first()
                if not token:
                    self.log("Токен не знайдено в БД")
                    return False
                token_id = token.token_id
            
            # Активуємо токен (має надіслати сповіщення)
            trigger_response = self.session.get(f"{BASE_URL}/api/trigger/{token_id}")
            
            if trigger_response.status_code == 200:
                self.log("Токен активовано, сповіщення надіслано")
                return True
            else:
                self.log("Помилка активації")
                return False
                
        except Exception as e:
            self.log(f"Помилка: {e}")
            return False
    
    def save_report(self, results: list):
        filename = f"notifications_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write("ЗВІТ ТЕСТУВАННЯ СПОВІЩЕНЬ\n")
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
     ТЕСТУВАННЯ СПОВІЩЕНЬ
     Перевірка Telegram, Slack та Email сповіщень
===========================================================================
        """)
        
        results = []
        
        # Базові тести
        results.append({'name': 'Підключення до сервера', 'passed': self.test_connection()})
        results.append({'name': 'Авторизація', 'passed': self.test_login()})
        
        print("\nОберіть тип сповіщень для тестування:")
        print("  1. Telegram")
        print("  2. Slack")
        print("  3. Email")
        print("  4. Всі")
        choice = input("Ваш вибір (1-4): ").strip()
        
        # Telegram тест
        if choice in ['1', '4']:
            print("\n--- Telegram ---")
            bot_token = input("  Токен бота: ").strip()
            chat_id = input("  ID чату: ").strip()
            
            if bot_token and chat_id:
                results.append({'name': 'Telegram налаштування', 
                               'passed': self.test_telegram_settings(bot_token, chat_id)})
                results.append({'name': 'Telegram перевірка', 
                               'passed': self.test_telegram_webhook(bot_token, chat_id)})
            else:
                print("  Пропускаємо Telegram (немає даних)")
        
        # Slack тест
        if choice in ['2', '4']:
            print("\n--- Slack ---")
            webhook_url = input("  Webhook URL: ").strip()
            
            if webhook_url:
                results.append({'name': 'Slack налаштування', 
                               'passed': self.test_slack_settings(webhook_url)})
                results.append({'name': 'Slack перевірка', 
                               'passed': self.test_slack_webhook(webhook_url)})
            else:
                print("  Пропускаємо Slack (немає даних)")
        
        # Email тест
        # Email тест
        if choice in ['3', '4']:
            print("\n--- Email ---")
            print("Для локального тестування (smtp4dev/FakeSMTP) введіть: localhost, порт 25")
            print("Для реальної пошти введіть дані вашого провайдера")
            print()
            
            smtp_server = input("  SMTP сервер (localhost для тестування): ").strip() or "localhost"
            smtp_port = input("  Порт (25 для localhost, 587 для Gmail): ").strip() or "25"
            
            # Перетворюємо порт на число
            try:
                smtp_port = int(smtp_port)
            except:
                smtp_port = 25
            
            # Якщо localhost - дозволяємо пусті логін/пароль
            if smtp_server == "localhost":
                email_user = "test@localhost"
                email_pass = ""
                to_email = input("  Email отримувача (test@localhost): ").strip() or "test@localhost"
                use_auth = False
                print("  (Підключення без авторизації для локального SMTP)")
            else:
                email_user = input("  Email користувач: ").strip()
                email_pass = input("  Пароль: ").strip()
                to_email = input("  Email отримувача: ").strip()
                use_auth = bool(email_user and email_pass)
            
            if smtp_server and to_email:
                results.append({'name': 'Email налаштування', 
                            'passed': self.test_email_settings(to_email)})
                results.append({'name': 'SMTP перевірка', 
                            'passed': self.test_smtp_email(smtp_server, smtp_port, email_user, email_pass, to_email, use_auth)})
            else:
                print("  Пропускаємо Email (немає даних)")
        
        # Фінальний тест з генерацією та активацією
        if any(r['passed'] for r in results[-3:]):
            results.append({'name': 'Активація зі сповіщенням', 
                           'passed': self.test_generate_and_trigger()})
        
        # Підсумок
        passed = sum(1 for r in results if r['passed'])
        total = len(results)
        
        print("\n" + "="*60)
        print(f"РЕЗУЛЬТАТ: {passed}/{total} тестів пройдено")
        if passed == total:
            print("Сповіщення працюють коректно")
        else:
            print("Є проблеми зі сповіщеннями")
        print("="*60)
        
        self.save_report(results)

if __name__ == "__main__":
    tester = NotificationTester()
    tester.run()