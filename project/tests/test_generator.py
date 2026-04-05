#!/usr/bin/env python3
"""
Тести для генератора токенів
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.token_generator import TokenGenerator

def test_aws_key():
    """Тест генерації AWS ключа"""
    gen = TokenGenerator()
    token = gen.generate_aws_key()
    
    assert token['type'] == 'aws_key'
    assert token['value'].startswith('AKIA')
    assert len(token['value']) == 20  # AKIA + 16 символів
    assert len(token['tracker']) == 16
    
    print("✅ AWS ключ: OK")

def test_github_token():
    """Тест генерації GitHub токена"""
    gen = TokenGenerator()
    token = gen.generate_github_token()
    
    assert token['type'] == 'github_token'
    assert token['value'].startswith('github_pat_')
    assert len(token['tracker']) == 16
    
    print("✅ GitHub токен: OK")

def test_url_token():
    """Тест генерації URL-токена (короткий шлях /{prefix}/{slug})"""
    gen = TokenGenerator(public_base_url='https://canary.example.test', link_prefix='i')
    token = gen.generate_url_token()
    
    assert token['type'] == 'url'
    assert token['value'].startswith('https://canary.example.test/i/')
    assert '/api/trigger/' not in token['value']
    assert token['id'] not in token['value']
    assert token.get('url_slug') and len(token['url_slug']) == 16
    assert len(token['tracker']) == 16
    
    print("✅ URL-токен: OK")

def test_document_token():
    """Тест генерації документа"""
    gen = TokenGenerator()
    token = gen.generate_document_token()
    
    assert token['type'] == 'document'
    assert '.' in token['value']
    assert len(token['tracker']) == 16
    
    print("✅ Документ: OK")

def test_batch_generation():
    """Тест масової генерації"""
    gen = TokenGenerator()
    
    # Один тип
    aws_tokens = gen.generate_batch('aws_key', 5)
    assert len(aws_tokens) == 5
    assert all(t['type'] == 'aws_key' for t in aws_tokens)
    
    # Змішані
    mixed = gen.generate_mixed({
        'aws_key': 3,
        'github_token': 2,
        'url': 1
    })
    assert len(mixed) == 6
    
    print("✅ Масова генерація: OK")

def test_unique_ids():
    """Тест унікальності ID"""
    gen = TokenGenerator()
    tokens = gen.generate_batch('aws_key', 10)
    
    ids = [t['id'] for t in tokens]
    assert len(ids) == len(set(ids))  # Всі ID унікальні
    
    print("✅ Унікальні ID: OK")

if __name__ == "__main__":
    print("🔬 Тестування генератора токенів\n")
    
    test_aws_key()
    test_github_token()
    test_url_token()
    test_document_token()
    test_batch_generation()
    test_unique_ids()
    
    print("\n🎉 Всі тести пройдено!")