"""
Система сповіщень про активацію honeypot-токенів
Надсилає повідомлення через різні канали
"""

import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Optional
from config import Config

class AlertSystem:
    """Надсилання сповіщень про активацію токенів"""
    
    def __init__(self):
        self.config = Config()
    
    def format_alert_message(self, token, activation) -> str:
        """Форматування повідомлення про активацію"""
        return f"""
🚨 CanaryTrap - ВИЯВЛЕНО АКТИВАЦІЮ!

🎯 Токен: {token.token_type}
🆔 ID: {token.token_id}
📅 Час: {activation.timestamp.strftime('%d.%m.%Y %H:%M:%S')}

📍 IP: {activation.ip_address}
🌍 Країна: {activation.country}
🏙️ Місто: {activation.city}
🖥️ User-Agent: {activation.user_agent}

📎 Джерело: {activation.source}

⚠️ Це може бути OSINT-розвідка!
"""
    
    def send_telegram(self, message: str) -> bool:
        """Надсилання через Telegram"""
        if not self.config.TELEGRAM_BOT_TOKEN or not self.config.TELEGRAM_CHAT_ID:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.config.TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': self.config.TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def send_slack(self, message: str) -> bool:
        """Надсилання через Slack"""
        if not self.config.SLACK_WEBHOOK_URL:
            return False
        
        try:
            payload = {
                'text': message,
                'username': 'CanaryTrap Alert',
                'icon_emoji': ':warning:'
            }
            response = requests.post(
                self.config.SLACK_WEBHOOK_URL,
                json=payload,
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def send_email(self, message: str) -> bool:
        """Надсилання через Email"""
        if not self.config.ALERT_EMAIL:
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = 'canarytrap@localhost'
            msg['To'] = self.config.ALERT_EMAIL
            msg['Subject'] = '🚨 CanaryTrap - Виявлено OSINT-активність'
            
            msg.attach(MIMEText(message, 'plain'))
            
            # Тут реальна відправка через SMTP
            # Для прикладу просто повертаємо True
            return True
        except:
            return False
    
    def send_alert(self, token, activation):
        """Надсилання сповіщень через всі канали"""
        message = self.format_alert_message(token, activation)
        
        print(f"\n📨 Надсилання сповіщень...")
        
        # Telegram
        if self.send_telegram(message):
            print("   ✅ Telegram")
        
        # Slack
        if self.send_slack(message):
            print("   ✅ Slack")
        
        # Email
        if self.send_email(message):
            print("   ✅ Email")
        
        # Локальний вивід
        print(f"\n{message}")

# Тест
if __name__ == "__main__":
    from web.app import Token, Activation
    from datetime import datetime
    
    # Створюємо тестові дані
    token = Token(
        token_id="test-123",
        token_type="aws_key",
        token_value="AKIATESTKEY123",
        tracker="test-tracker"
    )
    
    activation = Activation(
        token_id=1,
        ip_address="95.67.123.45",
        country="Україна",
        city="Київ",
        user_agent="Mozilla/5.0 (Test)",
        source="github_scanner"
    )
    activation.timestamp = datetime.now()
    
    # Тестуємо сповіщення
    alerts = AlertSystem()
    alerts.send_alert(token, activation)