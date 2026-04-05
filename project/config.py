import os
from datetime import timedelta

class Config:
    # База даних
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'trap.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Безпека
    SECRET_KEY = os.environ.get('SECRET_KEY', 'trap-secret-key-change-in-production')
    
    # Публічна URL програми (краще домен, не IP — інакше IP видно в посиланні)
    PUBLIC_BASE_URL = os.environ.get('PUBLIC_BASE_URL', 'http://127.0.0.1:5000').rstrip('/')
    # Короткий шлях для URL-canary: {PUBLIC_BASE_URL}/{CANARY_LINK_PREFIX}/{slug} (не /api/trigger/uuid)
    _lp = (os.environ.get('CANARY_LINK_PREFIX') or 'i').strip().strip('/')
    CANARY_LINK_PREFIX = _lp if _lp and _lp.replace('_', '').replace('-', '').isalnum() else 'i'
    
    # Налаштування токенів
    TOKEN_TYPES = ['aws_key', 'github_token', 'url', 'document', 'dns']
    DEPLOY_PLATFORMS = ['github', 'local']
    
    # Інтервали (в секундах)
    MONITOR_INTERVAL = 60  # Перевіряти кожну хвилину
    DEPLOY_INTERVAL = 21600  # Розміщувати кожні 6 годин
    
    # Сповіщення
    TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '')
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')
    ALERT_EMAIL = os.environ.get('ALERT_EMAIL', '')
    
    # GitHub для розміщення
    GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
    GITHUB_REPO = os.environ.get('GITHUB_REPO', 'canarytrap-deployed')