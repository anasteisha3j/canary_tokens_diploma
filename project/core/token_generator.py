"""
Генератор honeypot-токенів (canary tokens)
Створює різні типи цифрових приманок
"""

import os
import uuid
import random
import string
import json
import hashlib
import secrets
from datetime import datetime
from typing import Dict, List, Any, Optional

class TokenGenerator:
    """Генерація різних типів honeypot-токенів"""
    
    def __init__(
        self,
        public_base_url: Optional[str] = None,
        link_prefix: Optional[str] = None,
    ):
        base = public_base_url or os.environ.get('PUBLIC_BASE_URL') or 'http://127.0.0.1:5000'
        self.public_base_url = base.rstrip('/')
        lp = (link_prefix if link_prefix is not None else os.environ.get('CANARY_LINK_PREFIX') or 'i')
        lp = (lp or 'i').strip().strip('/')
        self.link_prefix = lp if lp and lp.replace('_', '').replace('-', '').isalnum() else 'i'
        self.token_types = {
            'aws_key': self.generate_aws_key,
            'github_token': self.generate_github_token,
            'url': self.generate_url_token,
            'document': self.generate_document_token,
            'dns': self.generate_dns_token
        }
    
    def generate_id(self) -> str:
        """Генерація унікального ID для токена"""
        return str(uuid.uuid4())
    
    def generate_hash(self, data: str) -> str:
        """Генерація хешу для відстеження"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def generate_aws_key(self) -> Dict[str, Any]:
        """
        Генерація фейкового AWS ключа
        Формат: AKIA[A-Z0-9]{16}
        """
        token_id = self.generate_id()
        prefix = "AKIA"
        chars = string.ascii_uppercase + string.digits
        suffix = ''.join(random.choices(chars, k=16))
        key = f"{prefix}{suffix}"
        
        return {
            'id': token_id,
            'type': 'aws_key',
            'value': key,
            'tracker': self.generate_hash(key),
            'metadata': {
                'service': 'AWS',
                'format': 'AKIA...',
                'created': datetime.now().isoformat()
            }
        }
    
    def generate_github_token(self) -> Dict[str, Any]:
        """
        Генерація фейкового GitHub токена
        Формат: github_pat_[A-Za-z0-9]{62}
        """
        token_id = self.generate_id()
        chars = string.ascii_letters + string.digits
        token = f"github_pat_{''.join(random.choices(chars, k=62))}"
        
        return {
            'id': token_id,
            'type': 'github_token',
            'value': token,
            'tracker': self.generate_hash(token),
            'metadata': {
                'service': 'GitHub',
                'created': datetime.now().isoformat()
            }
        }
    
    def generate_url_token(self) -> Dict[str, Any]:
        """
        URL-canary: коротке «нейтральне» посилання /{link_prefix}/{slug} (без UUID у URL).
        Внутрішній token_id лишається UUID; старий варіант /api/trigger/<uuid> ще підтримується сервером.
        """
        token_id = self.generate_id()
        alphabet = string.ascii_letters + string.digits
        url_slug = ''.join(secrets.choice(alphabet) for _ in range(16))
        path = f"/{self.link_prefix}/{url_slug}"
        url = f"{self.public_base_url}{path}"
        
        return {
            'id': token_id,
            'type': 'url',
            'value': url,
            'url_slug': url_slug,
            'tracker': self.generate_hash(url),
            'metadata': {
                'kind': 'canary_http',
                'trigger_path': path,
                'url_slug': url_slug,
                'created': datetime.now().isoformat()
            }
        }
    
    def generate_document_token(self) -> Dict[str, Any]:
        """
        Генерація документа-приманки
        Імітує PDF/Word/Excel файл з трекером
        """
        token_id = self.generate_id()
        doc_types = ['pdf', 'docx', 'xlsx', 'pptx']
        topics = ['Financial_Report_Q4', 'Employee_Salaries', 
                 'Merger_Plan', 'API_Documentation', 'Network_Diagram']
        
        doc_type = random.choice(doc_types)
        topic = random.choice(topics)
        filename = f"{topic}_{datetime.now().strftime('%Y%m%d')}.{doc_type}"
        
        return {
            'id': token_id,
            'type': 'document',
            'value': filename,
            'tracker': self.generate_hash(filename),
            'metadata': {
                'filename': filename,
                'doc_type': doc_type,
                'topic': topic,
                'created': datetime.now().isoformat()
            }
        }
    
    def generate_dns_token(self) -> Dict[str, Any]:
        """
        Генерація DNS-токена
        Унікальне доменне ім'я для відстеження
        """
        token_id = self.generate_id()
        subdomain = ''.join(random.choices(string.ascii_lowercase, k=12))
        dns_name = f"{subdomain}.canarytrap.local"
        
        return {
            'id': token_id,
            'type': 'dns',
            'value': dns_name,
            'tracker': self.generate_hash(dns_name),
            'metadata': {
                'record_type': 'A',
                'created': datetime.now().isoformat()
            }
        }
    
    def generate_batch(self, token_type: str, count: int = 5) -> List[Dict]:
        """Генерація партії токенів одного типу"""
        if token_type not in self.token_types:
            raise ValueError(f"Невідомий тип токена: {token_type}")
        
        tokens = []
        generator = self.token_types[token_type]
        
        for _ in range(count):
            tokens.append(generator())
        
        return tokens
    
    def generate_mixed(self, counts: Dict[str, int]) -> List[Dict]:
        """Генерація різних типів токенів"""
        tokens = []
        
        for token_type, count in counts.items():
            if token_type in self.token_types:
                tokens.extend(self.generate_batch(token_type, count))
        
        return tokens

# Тест
if __name__ == "__main__":
    gen = TokenGenerator()
    
    # Тестуємо різні типи
    print("🎯 Генерація токенів:\n")
    
    aws = gen.generate_aws_key()
    print(f"AWS ключ: {aws['value']}")
    print(f"Tracker: {aws['tracker']}\n")
    
    github = gen.generate_github_token()
    print(f"github_token: {github['value'][:20]}...")
    print(f"Tracker: {github['tracker']}\n")
    
    url = gen.generate_url_token()
    print(f"URL: {url['value']}")
    print(f"Tracker: {url['tracker']}\n")
    
    # Партія токенів
    batch = gen.generate_batch('aws_key', 3)
    print(f"Партія з {len(batch)} AWS ключів")