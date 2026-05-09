"""
Система моніторингу активації honeypot-токенів
Відстежує спроби використання приманок
"""

import requests
import socket
import json
from datetime import datetime
from typing import Dict, Any, Optional
from web.app import db, Token, Activation
from core.alert_system import AlertSystem

class Monitor:
    """Моніторинг активації токенів"""
    
    def __init__(self):
        self.alert_system = AlertSystem()
        self.monitoring_points = {
            'aws_key': self.check_aws_key,
            'github_token': self.check_github_token,
            'url': self.check_url,
            'document': self.check_document,
            'dns': self.check_dns
        }
    
    def get_ip_info(self, ip: str) -> Dict:
        """Отримання інформації про IP (геолокація)"""
        try:
            response = requests.get(f"http://ip-api.com/json/{ip}", timeout=2)
            if response.status_code == 200:
                data = response.json()
                return {
                    'country': data.get('country', 'Unknown'),
                    'city': data.get('city', 'Unknown'),
                    'isp': data.get('isp', 'Unknown'),
                    'lat': data.get('lat'),
                    'lon': data.get('lon')
                }
        except:
            pass
        return {'country': 'Unknown', 'city': 'Unknown'}
    
    def check_aws_key(self, token: Token) -> Optional[Activation]:
        """Перевірка чи використовувався AWS ключ"""
        # Симуляція перевірки AWS API
        # В реальній системі тут був би запит до AWS
        return None
    
    def check_github_token(self, token: Token) -> Optional[Activation]:
        """Перевірка чи використовувався GitHub токен"""
        # Симуляція перевірки GitHub API
        return None
    
    def check_url(self, token: Token) -> Optional[Activation]:
        """Перевірка чи переходили за URL"""
        # В реальній системі URL веде на наш сервер
        # який логує всі запити
        return None
    
    def check_document(self, token: Token) -> Optional[Activation]:
        """Перевірка чи відкривали документ"""
        # В реальній системі документи містять
        # веб-баги або макроси
        return None
    
    def check_dns(self, token: Token) -> Optional[Activation]:
        """Перевірка DNS-запитів"""
        try:
            # Спробуємо резолвити домен
            socket.gethostbyname(token.token_value)
            # Якщо успішно - значить хтось робив DNS-запит
            return self.create_activation(
                token=token,
                source='dns_query',
                ip='0.0.0.0',  # DNS не дає IP клієнта
                user_agent='DNS Resolver'
            )
        except:
            return None
    
    # В функції create_activation:
    def create_activation(self, token: Token, source: str, 
                        ip: str, user_agent: str) -> Activation:
        """Створення запису про активацію токена"""
        ip_info = self.get_ip_info(ip)
        
        activation = Activation(
            token_id=token.id,
            ip_address=ip,
            country=ip_info.get('country', 'Unknown'),
            city=ip_info.get('city', 'Unknown'),
            user_agent=user_agent,
            source=source,
            activation_metadata=json.dumps({  # ← ЗМІНА
                'ip_info': ip_info,
                'timestamp': datetime.now().isoformat()
            })
        )
        
        # Оновлюємо статус токена
        token.status = 'triggered'
        token.triggered_at = datetime.now()
        
        return activation

        
    def check_token(self, token: Token) -> Optional[Activation]:
        """Перевірка конкретного токена"""
        if token.status != 'active':
            return None
        
        check_func = self.monitoring_points.get(token.token_type)
        if check_func:
            return check_func(token)
        return None
    
    def check_all(self):
        """Перевірка всіх активних токенів"""
        from web.app import app
        
        with app.app_context():
            active_tokens = Token.query.filter_by(status='active').all()
            print(f"\n🔍 [{datetime.now().strftime('%H:%M:%S')}] Моніторинг {len(active_tokens)} токенів...")
            
            for token in active_tokens:
                activation = self.check_token(token)
                
                if activation:
                    # Зберігаємо активацію
                    db.session.add(activation)
                    db.session.commit()
                    
                    # Надсилаємо сповіщення
                    self.alert_system.send_alert(token, activation)
                    
                    print(f"   🚨 Активація! {token.token_type} - {activation.ip_address} ({activation.country})")
    
    def manual_trigger(self, token_id: str, ip: str, user_agent: str) -> bool:
        """Ручне спрацювання токена (для тестування)"""
        from web.app import app
        
        with app.app_context():
            token = Token.query.filter_by(token_id=token_id).first()
            if token and token.status == 'active':
                activation = self.create_activation(
                    token=token,
                    source='manual',
                    ip=ip,
                    user_agent=user_agent
                )
                db.session.add(activation)
                db.session.commit()
                
                self.alert_system.send_alert(token, activation)
                return True
        return False

# Тест
if __name__ == "__main__":
    monitor = Monitor()
    monitor.check_all()