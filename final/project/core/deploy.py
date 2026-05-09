"""
Механізм автоматичного розміщення honeypot-токенів
Розміщує приманки в публічних джерелах
"""

import os
import json
import base64
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.token_generator import TokenGenerator


class DeployEngine:
    """Автоматичне розміщення токенів на різних платформах"""
    
    def __init__(self):
        self.token_generator = TokenGenerator()
    
    def deploy_local(self, tokens: List[Dict], user=None) -> Dict:
        """Розміщення токенів у локальній файловій системі"""
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'tokens')
        deploy_dir = base_dir

        if user is not None:
            from web.app import DeploymentConfig
            cfg = DeploymentConfig.query.filter_by(user_id=user.id, name='default').first()
            if cfg and cfg.local_path:
                lp = cfg.local_path.strip().rstrip('/\\')
                deploy_dir = lp if os.path.isabs(lp) else os.path.join(base_dir, lp)

        os.makedirs(deploy_dir, exist_ok=True)
        
        results = []
        for token in tokens:
            token_file = os.path.join(deploy_dir, f"{token['type']}_{token['id'][:8]}.txt")
            with open(token_file, 'w', encoding='utf-8') as f:
                f.write(json.dumps(token, indent=2))
            results.append({
                'token_id': token['id'],
                'path': token_file,
                'status': 'deployed'
            })
        
        return {
            'platform': 'local',
            'count': len(results),
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
    
    def deploy_github(self, tokens: List[Dict], user) -> Dict:
        """Створює файл у репозиторії GitHub через Contents API."""
        from config import Config
        from web.app import DeploymentConfig

        cfg = DeploymentConfig.query.filter_by(user_id=user.id, name='default').first()
        repo = (cfg.github_repo.strip() if cfg and cfg.github_repo else None) or (
            Config.GITHUB_REPO.strip() if getattr(Config, 'GITHUB_REPO', None) else None
        )
        branch = (cfg.github_branch if cfg and cfg.github_branch else None) or 'main'
        pat = None
        if cfg and cfg.github_token:
            pat = cfg.github_token.strip()
        if not pat:
            pat = (os.environ.get('GITHUB_TOKEN') or getattr(Config, 'GITHUB_TOKEN', '') or '').strip()

        org_name = user.organization.name if getattr(user, 'organization', None) else 'N/A'

        if not repo:
            return {'error': 'Репозиторій не налаштовано', 'platform': 'github', 'count': 0}
        if not pat:
            return {
                'error': 'Потрібен GitHub PAT (налаштування або змінна GITHUB_TOKEN)',
                'platform': 'github',
                'count': 0
            }

        content_lines = [
            f"# CanaryTrap — токени для {org_name}",
            f"# Створено: {datetime.now().isoformat()}",
            "",
        ]
        for token in tokens:
            content_lines.extend([
                f"## {token['type'].upper()}",
                f"ID: {token['id']}",
                f"Value: {token['value']}",
                "",
            ])
        content_raw = "\n".join(content_lines)
        content_b64 = base64.b64encode(content_raw.encode('utf-8')).decode('ascii')

        path = f"canarytrap/tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        url = f"https://api.github.com/repos/{repo}/contents/{path}"
        headers = {
            'Authorization': f'Bearer {pat}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }
        body = {
            'message': f'CanaryTrap deploy {datetime.now().isoformat()}',
            'content': content_b64,
            'branch': branch,
        }

        try:
            response = requests.put(url, headers=headers, json=body, timeout=60)
        except requests.RequestException as e:
            return {'error': str(e), 'platform': 'github', 'count': 0}

        if response.status_code not in (200, 201):
            detail = response.text[:2000]
            return {
                'error': f'GitHub API {response.status_code}: {detail}',
                'platform': 'github',
                'count': 0
            }

        return {
            'platform': 'github',
            'repo': repo,
            'path': path,
            'branch': branch,
            'count': len(tokens),
            'status': 'success',
            'timestamp': datetime.now().isoformat()
        }

    def save_deployment_log(self, deployment: Dict) -> None:
        """Зберігає запис про розгортання (без додавання рядків у tokens — токени з UI)."""
        from web.app import app, db, Deployment

        with app.app_context():
            deploy_record = Deployment(
                platform=deployment.get('platform', 'unknown'),
                tokens_count=deployment.get('count', 0),
                deployment_details=json.dumps(deployment, default=str)
            )
            db.session.add(deploy_record)
            db.session.commit()
        
    def deploy_all(self):
        """Планове локальне розгортання (без ідентифікатора користувача / GitHub)."""
        print(f"\n📤 [{datetime.now().strftime('%H:%M:%S')}] Розміщення токенів (локально)...")
        
        counts = {
            'aws_key': 5,
            'github_token': 5,
            'url': 3,
            'document': 2
        }
        
        tokens = self.token_generator.generate_mixed(counts)
        print(f"   Згенеровано {len(tokens)} нових токенів (фоновий цикл, без БД)")
        
        try:
            result = self.deploy_local(tokens, user=None)
            print(f"   ✅ local: {result.get('count', 0)} токенів")
            self.save_deployment_log(result)
        except Exception as e:
            print(f"   ❌ local: помилка - {e}")
