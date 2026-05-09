"""
Flask веб-додаток для CanaryTrap
"""

import base64
import io
import mimetypes
import os
import re
import json
import secrets
import urllib.request
import urllib.error
from datetime import datetime

from flask import (Flask, render_template, request, redirect,
                   url_for, flash, jsonify, abort, send_file)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, login_user,
                         login_required, logout_user, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import expression as sql_expr

from config import Config

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, 'instance', 'docs')
os.makedirs(PDF_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# MODELS
# ═══════════════════════════════════════════════════════════════

class Organization(db.Model):
    __tablename__ = 'organizations'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    users       = db.relationship('User',  back_populates='organization', lazy=True)
    tokens      = db.relationship('Token', back_populates='organization', lazy=True)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id              = db.Column(db.Integer, primary_key=True)
    username        = db.Column(db.String(80),  unique=True, nullable=False)
    email           = db.Column(db.String(120), unique=True, nullable=False)
    password_hash   = db.Column(db.String(200), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    role            = db.Column(db.String(20),  default='user')
    api_key         = db.Column(db.String(64),  nullable=True)
    telegram_bot    = db.Column(db.String(500), nullable=True)
    telegram_chat   = db.Column(db.String(100), nullable=True)
    slack_webhook   = db.Column(db.String(500), nullable=True)
    alert_email     = db.Column(db.String(120), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    organization    = db.relationship('Organization', back_populates='users')
    tokens          = db.relationship('Token', backref='owner', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Token(db.Model):
    __tablename__ = 'tokens'
    id              = db.Column(db.Integer, primary_key=True)
    token_id        = db.Column(db.String(50),  unique=True, nullable=False)
    token_type      = db.Column(db.String(50),  nullable=False)
    token_value     = db.Column(db.Text,        nullable=False)  # disk path for docs
    tracker         = db.Column(db.String(50),  nullable=False)
    token_metadata  = db.Column(db.Text, default='{}')
    status          = db.Column(db.String(20),  default='active')
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'),         nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    triggered_at    = db.Column(db.DateTime, nullable=True)
    url_slug        = db.Column(db.String(48), unique=True, nullable=True)
    organization    = db.relationship('Organization', back_populates='tokens')
    activations     = db.relationship('Activation', backref='token', lazy=True)


class Activation(db.Model):
    __tablename__ = 'activations'
    id                  = db.Column(db.Integer, primary_key=True)
    token_id            = db.Column(db.Integer, db.ForeignKey('tokens.id'), nullable=False)
    ip_address          = db.Column(db.String(50))
    country             = db.Column(db.String(100))
    city                = db.Column(db.String(100))
    user_agent          = db.Column(db.String(500))
    source              = db.Column(db.String(100))
    activation_metadata = db.Column(db.Text, default='{}')
    timestamp           = db.Column(db.DateTime, default=datetime.now)


class Deployment(db.Model):
    __tablename__ = 'deployments'
    id                 = db.Column(db.Integer, primary_key=True)
    platform           = db.Column(db.String(50))
    tokens_count       = db.Column(db.Integer)
    deployment_details = db.Column(db.Text, default='{}')
    created_at         = db.Column(db.DateTime, default=datetime.now)


class DeploymentConfig(db.Model):
    __tablename__ = 'deployment_configs'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name            = db.Column(db.String(100))
    platform        = db.Column(db.String(50), nullable=False)
    github_repo     = db.Column(db.String(200))
    github_branch   = db.Column(db.String(50),  default='main')
    github_token    = db.Column(db.String(500),  nullable=True)
    local_path      = db.Column(db.String(200))
    pastebin_api    = db.Column(db.String(200))
    pastebin_expiry = db.Column(db.String(20),   default='1W')
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    user            = db.relationship('User', backref='deployment_configs')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ═══════════════════════════════════════════════════════════════
# SQLITE MIGRATION
# ═══════════════════════════════════════════════════════════════

def _migrate_sqlite_schema():
    if 'sqlite' not in str(db.engine.url):
        return
    try:
        from sqlalchemy import text
        with db.engine.begin() as conn:

            # deployment_configs
            rows = conn.execute(text('PRAGMA table_info(deployment_configs)')).fetchall()
            if rows:
                cols = {r[1] for r in rows}
                if 'github_token' not in cols:
                    conn.execute(text(
                        'ALTER TABLE deployment_configs ADD COLUMN github_token VARCHAR(500)'))

            # tokens
            rows_t = conn.execute(text('PRAGMA table_info(tokens)')).fetchall()
            if rows_t:
                cols_t = {r[1] for r in rows_t}
                if 'url_slug' not in cols_t:
                    conn.execute(text(
                        'ALTER TABLE tokens ADD COLUMN url_slug VARCHAR(48)'))
                    conn.execute(text(
                        'CREATE UNIQUE INDEX IF NOT EXISTS ix_tokens_url_slug '
                        'ON tokens(url_slug) WHERE url_slug IS NOT NULL'))

            # users
            rows_u = conn.execute(text('PRAGMA table_info(users)')).fetchall()
            if rows_u:
                cols_u = {r[1] for r in rows_u}
                new_cols = {
                    'api_key':      'VARCHAR(64)',
                    'telegram_bot': 'VARCHAR(500)',
                    'telegram_chat':'VARCHAR(100)',
                    'slack_webhook':'VARCHAR(500)',
                    'alert_email':  'VARCHAR(120)',
                }
                for col, col_type in new_cols.items():
                    if col not in cols_u:
                        conn.execute(text(
                            f'ALTER TABLE users ADD COLUMN {col} {col_type}'))

    except Exception as e:
        print(f'⚠️ Міграція схеми SQLite: {e}')


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

def get_default_deploy_config(user):
    c = DeploymentConfig.query.filter_by(user_id=user.id, name='default').first()
    if not c:
        c = DeploymentConfig(user_id=user.id, name='default', platform='github')
        db.session.add(c)
        db.session.commit()
    return c


def get_client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    return xff.split(',')[0].strip() if xff else (request.remote_addr or '0.0.0.0')


def org_tokens_query():
    if current_user.role == 'admin':
        return Token.query
    if not current_user.organization_id:
        return Token.query.filter(sql_expr.false())
    return Token.query.filter(Token.organization_id == current_user.organization_id)


def org_activations_query():
    if current_user.role == 'admin':
        return Activation.query
    if not current_user.organization_id:
        return Activation.query.filter(sql_expr.false())
    return Activation.query.join(Token).filter(
        Token.organization_id == current_user.organization_id)


def token_row_to_deploy_dict(t):
    return {
        'id': t.token_id,
        'type': t.token_type,
        'value': t.token_value,
        'tracker': t.tracker,
        'metadata': json.loads(t.token_metadata or '{}'),
    }


def user_can_view_token(token):
    if current_user.role == 'admin':
        return True
    if not current_user.organization_id or not token.organization_id:
        return False
    return token.organization_id == current_user.organization_id


def _delete_token_with_activations(token):
    if token.token_type == 'document' and token.token_value:
        fpath = token.token_value
        if os.path.isfile(fpath):
            try:
                os.remove(fpath)
            except OSError:
                pass
    Activation.query.filter_by(token_id=token.id).delete()
    db.session.delete(token)


def _tokens_redirect_status():
    st = (request.form.get('filter_status') or
          request.args.get('status') or '').strip().lower()
    return {'status': st} if st in ('active', 'triggered') else {}


def _active_tokens_as_deploy_list():
    q = (org_tokens_query()
         .filter_by(status='active')
         .order_by(Token.created_at.desc())
         .limit(200))
    return [token_row_to_deploy_dict(t) for t in q.all()]


# PDF GENERATION

def _build_html_token(token_id: str, trigger_url: str, label: str = "Confidential", org_name: str = "Internal") -> tuple[str, str, dict]:
    """
    Створює HTML файл, який автоматично викликає trigger при відкритті
    """
    os.makedirs(PDF_DIR, exist_ok=True)
    
    filename = f"{label.lower().replace(' ', '_')}_{token_id[:8]}.html"
    filepath = os.path.abspath(os.path.join(PDF_DIR, filename))
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{label}</title>
    <script>
        // Автоматичний виклик trigger при завантаженні сторінки
        fetch('{trigger_url}')
            .then(response => console.log('Trigger sent'))
            .catch(error => console.error('Trigger error:', error));
            
        var img = new Image();
        img.src = '{trigger_url}?t=' + new Date().getTime();
    </script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 50px;
            background: #f5f5f5;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        .confidential {{
            color: red;
            font-weight: bold;
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            border: 2px solid red;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 {label}</h1>
        <p><strong>Організація:</strong> {org_name}</p>
        <p><strong>ID документу:</strong> {token_id[:16]}</p>
        <p><strong>Дата:</strong> {datetime.now().strftime('%d.%m.%Y')}</p>
        <p>Цей документ є конфіденційним.</p>
        <p>Використання та розповсюдження неавторизованим особам заборонено.</p>
        <div class="confidential">
            ⚠️ CONFIDENTIAL - MONITORED DOCUMENT ⚠️
        </div>
        <p style="margin-top: 50px; font-size: 12px; color: gray;">
            Tracking ID: {token_id}
        </p>
    </div>
</body>
</html>"""
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    metadata = {
        "filename": filename,
        "filepath": filepath,
        "mime": "text/html",
        "trigger_url": trigger_url,
        "size_bytes": os.path.getsize(filepath),
        "created": datetime.now().strftime("%d.%m.%Y"),
        "token_id": token_id,
    }
    
    print(f"✅ HTML створено: {filepath}")
    return filepath, filename, metadata

# GITHUB PDF DEPLOY
def _deploy_pdf_to_github(filepath: str, filename: str, user) -> dict:
    """
    Push one PDF to canary-docs/<filename> in the user's configured GitHub repo.
    Returns {'url': ..., 'path': ...} on success or {'error': ...} on failure.
    """
    cfg = get_default_deploy_config(user)
    if not cfg.github_repo:
        return {'error': 'GitHub repo not set — configure it in Settings'}
    if not cfg.github_token:
        return {'error': 'GitHub token not set — configure it in Settings'}

    repo    = cfg.github_repo.strip('/')
    branch  = (cfg.github_branch or 'main').strip()
    path    = f"canary-docs/{filename}"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    with open(filepath, 'rb') as fh:
        b64 = base64.b64encode(fh.read()).decode()

    headers = {
        'Authorization': f'token {cfg.github_token}',
        'Accept':        'application/vnd.github+json',
        'User-Agent':    'CanaryTrap/1.0',
        'Content-Type':  'application/json',
    }

    sha = None
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req) as r:
            sha = json.loads(r.read()).get('sha')
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return {'error': f'GitHub check failed: {e.code} {e.reason}'}

    payload = {
        'message': f'{"Update" if sha else "Add"} canary document {filename}',
        'content': b64,
        'branch':  branch,
    }
    if sha:
        payload['sha'] = sha

    try:
        put = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode(),
            method='PUT',
            headers=headers,
        )
        with urllib.request.urlopen(put) as r:
            resp = json.loads(r.read())
            return {
                'url':  resp.get('content', {}).get('html_url', ''),
                'path': path,
                'repo': repo,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        return {'error': f'GitHub PUT {e.code}: {body[:300]}'}
    except Exception as e:
        return {'error': str(e)}


# ROUTES — AUTH
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Вхід успішний!', 'success')
            return redirect(url_for('dashboard'))
        flash('Невірне ім\'я або пароль', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email    = (request.form.get('email')    or '').strip().lower()
        password = request.form.get('password')
        confirm  = request.form.get('confirm_password')
        org_name = (request.form.get('organization') or '').strip()

        if not org_name:
            flash('Вкажіть назву організації', 'error')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Паролі не співпадають', 'error')
            return redirect(url_for('register'))
        if len(password) < 6:
            flash('Пароль має містити мінімум 6 символів', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('Користувач з таким іменем вже існує', 'error')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Користувач з таким email вже існує', 'error')
            return redirect(url_for('register'))

        try:
            org = Organization.query.filter_by(name=org_name).first()
            if not org:
                org = Organization(name=org_name)
                db.session.add(org)
                db.session.flush()
            role = 'org_admin' if User.query.filter_by(
                organization_id=org.id).count() == 0 else 'user'
            user = User(username=username, email=email,
                        organization_id=org.id, role=role)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash('Реєстрація успішна! Тепер можна увійти', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            print(f'Register error: {e}')
            db.session.rollback()
            flash('Помилка при реєстрації. Спробуйте ще раз.', 'error')

    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ROUTES — DASHBOARD
@app.route('/dashboard')
@login_required
def dashboard():
    tq = org_tokens_query()
    aq = org_activations_query()
    if current_user.role == 'admin':
        token_types = db.session.query(
            Token.token_type, db.func.count(Token.id)
        ).group_by(Token.token_type).all()
    elif current_user.organization_id:
        token_types = db.session.query(
            Token.token_type, db.func.count(Token.id)
        ).filter(Token.organization_id == current_user.organization_id
                 ).group_by(Token.token_type).all()
    else:
        token_types = []
    return render_template('dashboard.html',
        total_tokens=tq.count(),
        active_tokens=tq.filter_by(status='active').count(),
        total_activations=aq.count(),
        recent_activations=aq.order_by(Activation.timestamp.desc()).limit(5).all(),
        token_types=token_types)


# ROUTES — TOKENS
@app.route('/tokens')
@login_required
def tokens():
    status_filter = (request.args.get('status') or '').strip().lower()
    if status_filter not in ('', 'active', 'triggered'):
        status_filter = ''
    q = org_tokens_query().order_by(Token.created_at.desc())
    if status_filter == 'active':
        q = q.filter_by(status='active')
    elif status_filter == 'triggered':
        q = q.filter_by(status='triggered')
    return render_template('tokens.html', tokens=q.all(), status_filter=status_filter)

@app.route('/tokens/generate', methods=['POST'])
@login_required
def generate_tokens():
    from core.token_generator import TokenGenerator
    from core.deploy import DeployEngine
    import traceback

    if current_user.role != 'admin' and not current_user.organization_id:
        flash('Спочатку додайте організацію у профілі (налаштування).', 'error')
        return redirect(url_for('tokens'))

    token_type = request.form.get('token_type')
    count = max(1, min(50, int(request.form.get('count', 5))))
    platforms = request.form.getlist('platforms')

    if 'pastebin' in platforms:
        flash('Pastebin поки не підтримується.', 'warning')
    platforms = [p for p in platforms if p != 'pastebin']

    org_id = current_user.organization_id
    if current_user.role == 'admin' and not org_id:
        flash('Для глобального адміністратора потрібна організація у профілі.', 'error')
        return redirect(url_for('settings'))

    base_url = app.config.get('PUBLIC_BASE_URL', Config.PUBLIC_BASE_URL)
    link_prefix = app.config.get('CANARY_LINK_PREFIX', Config.CANARY_LINK_PREFIX)
    org_label = current_user.organization.name if current_user.organization else 'Internal'

    gen = TokenGenerator(public_base_url=base_url, link_prefix=link_prefix)
    
    # Генерація токенів
    if token_type == 'mixed':
        raw_tokens = gen.generate_mixed({
            'aws_key': count, 
            'github_token': count,
            'url': count // 2, 
            'document': count // 2,
        })
    else:
        raw_tokens = gen.generate_batch(token_type, count)

    pdf_files = []  # [(filepath, filename)] for GitHub push
    created_tokens = []
    errors = []

    for t in raw_tokens:
        token_value = t['value']
        token_metadata = t.get('metadata', {})

        if t['type'] == 'document':
            trigger_url = f"{base_url}/api/trigger/{t['id']}"
            view_url = f"{base_url}/docs/{t['id']}"
            
            try:
                # Спроба створити PDF
                filepath, fname, meta = _build_html_token(
                    token_id=t['id'],
                    trigger_url=trigger_url,
                    label="Confidential Report",
                    org_name=org_label,
                )
                
                # Перевіряємо, що файл дійсно створився
                if not os.path.isfile(filepath):
                    raise Exception(f"PDF file not created at {filepath}")
                
                token_value = filepath
                token_metadata = meta
                token_metadata['view_url'] = view_url
                token_metadata['trigger_url'] = trigger_url
                
                pdf_files.append((filepath, fname))
                print(f"✅ PDF створено: {fname} ({os.path.getsize(filepath)} bytes)")
                
            except Exception as e:
                error_msg = f"PDF generation failed for {t['id']}: {str(e)}"
                print(f"⚠️ {error_msg}")
                print(traceback.format_exc())
                errors.append(error_msg)
                
                token_value = f"DOCUMENT_{t['id']}.pdf"
                token_metadata = {
                    'filename': f'{t["id"]}.pdf',
                    'mime': 'application/pdf',
                    'trigger_url': trigger_url,
                    'view_url': view_url,
                    'error': str(e),
                    'fake': True
                }

        # Створюємо запис в БД
        row = Token(
            token_id=t['id'],
            token_type=t['type'],
            token_value=token_value,
            tracker=t['tracker'],
            token_metadata=json.dumps(token_metadata),
            user_id=current_user.id,
            organization_id=org_id,
            url_slug=t.get('url_slug'),
        )
        db.session.add(row)
        created_tokens.append(row)

    try:
        db.session.commit()
        print(f"✅ Збережено {len(created_tokens)} токенів в БД")
    except Exception as e:
        db.session.rollback()
        error_msg = f"Database error: {str(e)}"
        print(f"❌ {error_msg}")
        flash(error_msg, 'error')
        return redirect(url_for('tokens'))

    if platforms:
        engine = DeployEngine()
        
        deployable_tokens = []
        for t in raw_tokens:
            if t['type'] == 'document':
                # Перевіряємо чи PDF створився успішно
                token_in_db = Token.query.filter_by(token_id=t['id']).first()
                if token_in_db and token_in_db.token_value and os.path.isfile(token_in_db.token_value):
                    deployable_tokens.append(t)
                else:
                    print(f"⚠️ {t['id']} - PDF файл відсутній")
            else:
                deployable_tokens.append(t)
        
        for platform in platforms:
            if platform == 'github':
                try:
                    result = engine.deploy_github(deployable_tokens, current_user)
                    if result.get('error'):
                        flash(f'GitHub (token list): {result["error"]}', 'error')
                    else:
                        flash(f'GitHub token list → {result.get("repo")}', 'success')
                except Exception as e:
                    flash(f'GitHub deploy error: {str(e)}', 'error')
                    
            elif platform == 'local':
                try:
                    engine.deploy_local(deployable_tokens, current_user)
                    flash('Локальне розміщення виконано.', 'success')
                except Exception as e:
                    flash(f'Local deploy error: {str(e)}', 'error')

    if 'github' in platforms and pdf_files:
        for filepath, fname in pdf_files:
            try:
                if os.path.isfile(filepath):
                    result = _deploy_pdf_to_github(filepath, fname, current_user)
                    if result.get('error'):
                        flash(f'GitHub PDF «{fname}»: {result["error"]}', 'error')
                    else:
                        flash(f'GitHub PDF → {result.get("url") or result.get("path")}', 'success')
                else:
                    flash(f'GitHub PDF «{fname}»: File not found', 'error')
            except Exception as e:
                flash(f'GitHub PDF error for {fname}: {str(e)}', 'error')

    success_count = len([t for t in created_tokens if t.token_type != 'document' or 
                        (t.token_type == 'document' and t.token_value and 
                         not json.loads(t.token_metadata or '{}').get('fake'))])
    
    if errors:
        flash(f'Згенеровано {success_count} з {len(raw_tokens)} токенів. Помилки: {" ".join(errors[:3])}', 'warning')
    else:
        flash(f'✅ Згенеровано {len(raw_tokens)} токенів для «{org_label}»', 'success')
    
    return redirect(url_for('tokens'))

@app.route('/debug/check-pdfs')
@login_required
def check_pdfs():
    """Діагностика PDF файлів"""
    if current_user.role != 'admin':
        abort(403)
    
    doc_tokens = Token.query.filter_by(token_type='document').all()
    results = []
    
    for token in doc_tokens:
        file_exists = False
        file_size = 0
        
        if token.token_value and os.path.isfile(token.token_value):
            file_exists = True
            file_size = os.path.getsize(token.token_value)
        else:
            # Перевіряємо альтернативні шляхи
            meta = json.loads(token.token_metadata or '{}')
            filename = meta.get('filename', f'{token.token_id}.pdf')
            alt_path = os.path.join(PDF_DIR, filename)
            if os.path.isfile(alt_path):
                file_exists = True
                file_size = os.path.getsize(alt_path)
                token.token_value = alt_path
                db.session.commit()
        
        results.append({
            'token_id': token.token_id,
            'id': token.id,
            'filepath': token.token_value,
            'exists': file_exists,
            'size': file_size,
            'metadata': json.loads(token.token_metadata or '{}')
        })
    
    return jsonify({
        'pdf_dir': PDF_DIR,
        'pdf_dir_exists': os.path.exists(PDF_DIR),
        'tokens': results
    })

@app.route('/tokens/<int:token_id>/download')
@login_required
def download_token(token_id):
    """Завантаження файлу для адміністратора"""
    token = Token.query.get_or_404(token_id)
    
    # Перевірка прав доступу
    if current_user.role != 'admin':
        if not current_user.organization_id or not token.organization_id:
            abort(403)
        if token.organization_id != current_user.organization_id:
            abort(403)
    
    if token.token_type != 'document':
        flash('Це не документ-токен', 'error')
        return redirect(url_for('token_detail', token_id=token.id))
    
    meta = {}
    if token.token_metadata:
        try:
            meta = json.loads(token.token_metadata)
        except:
            meta = {}
    
    filename = meta.get('filename', f'{token.token_id}.html')
    
    filepath = None
    
    # 1 token_value
    if token.token_value and os.path.isfile(token.token_value):
        filepath = token.token_value
    
    # 2 PDF_DIR за назвою
    elif os.path.isfile(os.path.join(PDF_DIR, filename)):
        filepath = os.path.join(PDF_DIR, filename)
    
    elif os.path.exists(PDF_DIR):
        for f in os.listdir(PDF_DIR):
            if token.token_id in f and (f.endswith('.html') or f.endswith('.pdf')):
                filepath = os.path.join(PDF_DIR, f)
                filename = f
                break
    
    if not filepath or not os.path.isfile(filepath):
        flash(f'Файл не знайдено: {filename}', 'error')
        return redirect(url_for('token_detail', token_id=token.id))
    
    try:
        mime = 'text/html' if filepath.endswith('.html') else 'application/pdf'
        return send_file(
            filepath,
            mimetype=mime,
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Помилка при завантаженні: {str(e)}', 'error')
        return redirect(url_for('token_detail', token_id=token.id))

@app.route('/tokens/<int:token_id>/deploy-github', methods=['POST'])
@login_required
def deploy_token_github(token_id):
    """Manually push a single document token PDF to GitHub."""
    token = Token.query.get_or_404(token_id)
    if not user_can_view_token(token):
        abort(403)
    if token.token_type != 'document':
        return jsonify({'status': 'error', 'message': 'Not a document token'}), 400

    meta     = json.loads(token.token_metadata or '{}')
    filename = meta.get('filename', f'{token.token_id}.pdf')
    filepath = token.token_value

    if not os.path.isfile(filepath):
        filepath = os.path.join(PDF_DIR, filename)
    if not os.path.isfile(filepath):
        return jsonify({'status': 'error', 'message': 'PDF file not found on disk'}), 404

    result = _deploy_pdf_to_github(filepath, filename, current_user)
    if result.get('error'):
        return jsonify({'status': 'error', 'message': result['error']}), 400
    return jsonify({'status': 'success',
                    'url':  result.get('url', ''),
                    'path': result.get('path', '')})


@app.route('/tokens/<int:token_id>')
@login_required
def token_detail(token_id):
    token = Token.query.get_or_404(token_id)
    if not user_can_view_token(token):
        abort(403)
    activations = (Activation.query
                   .filter_by(token_id=token.id)
                   .order_by(Activation.timestamp.desc())
                   .all())
    return render_template('token_detail.html', token=token, activations=activations)


@app.route('/tokens/<int:token_id>/delete', methods=['POST'])
@login_required
def delete_token(token_id):
    token = Token.query.get_or_404(token_id)
    if not user_can_view_token(token):
        abort(403)
    _delete_token_with_activations(token)
    db.session.commit()
    flash('Токен видалено', 'success')
    return redirect(url_for('tokens', **_tokens_redirect_status()))


@app.route('/tokens/delete-all', methods=['POST'])
@login_required
def delete_all_tokens():
    scope = (request.form.get('scope') or 'all').strip().lower()
    if scope not in ('all', 'active', 'triggered'):
        scope = 'all'
    q = org_tokens_query()
    if scope == 'active':
        q = q.filter_by(status='active')
    elif scope == 'triggered':
        q = q.filter_by(status='triggered')
    n = 0
    for t in q.all():
        _delete_token_with_activations(t)
        n += 1
    db.session.commit()
    flash(f'Видалено токенів: {n}', 'success')
    return redirect(url_for('tokens', **_tokens_redirect_status()))


# ROUTES — ACTIVATIONS
@app.route('/activations')
@login_required
def activations():
    all_act = org_activations_query().order_by(Activation.timestamp.desc()).all()
    return render_template('activations.html', activations=all_act)


# ROUTES — SETTINGS
@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        org_name = (request.form.get('organization') or '').strip()
        if org_name:
            if current_user.organization_id:
                org = Organization.query.get(current_user.organization_id)
                if org and org.name != org_name:
                    taken = Organization.query.filter(
                        Organization.name == org_name,
                        Organization.id   != org.id).first()
                    if taken:
                        flash('Організація з такою назвою вже існує', 'error')
                        return redirect(url_for('settings'))
                    org.name = org_name
            else:
                org = Organization.query.filter_by(name=org_name).first()
                if not org:
                    org = Organization(name=org_name)
                    db.session.add(org)
                    db.session.flush()
                current_user.organization_id = org.id
                if current_user.role not in ('admin', 'org_admin'):
                    current_user.role = 'org_admin'
        db.session.commit()
        flash('Налаштування збережено', 'success')
        return redirect(url_for('settings'))

    deploy_config = get_default_deploy_config(current_user)
    total_users   = (User.query.count() if current_user.role == 'admin'
                     else (User.query.filter_by(
                               organization_id=current_user.organization_id).count()
                           if current_user.organization_id else 0))
    return render_template('settings.html',
        user=current_user,
        deploy_config=deploy_config,
        total_tokens=org_tokens_query().count(),
        total_activations=org_activations_query().count(),
        total_users=total_users,
        last_activation=org_activations_query().order_by(
            Activation.timestamp.desc()).first(),
        public_base_url=app.config.get('PUBLIC_BASE_URL', ''),
        canary_link_prefix=app.config.get('CANARY_LINK_PREFIX', 'i'),
        app_port=app.config.get('APP_PORT', Config.APP_PORT))


# ROUTES — API
@app.route('/api/ping')
def api_ping():
    return jsonify({'ok': True})


@app.route('/api/stats')
@login_required
def api_stats():
    tq = org_tokens_query()
    aq = org_activations_query()
    return jsonify({
        'tokens':      tq.count(),
        'activations': aq.count(),
        'triggered':   tq.filter(Token.status == 'triggered').count(),
    })


_CANARY_SLUG_RE = re.compile(r'^[A-Za-z0-9_-]{12,48}$')


def _canary_trigger_response(token_uuid: str):
    from core.monitor import Monitor
    ip         = get_client_ip()
    user_agent = request.headers.get('User-Agent', 'Unknown')
    if Monitor().manual_trigger(token_uuid, ip, user_agent):
        return jsonify({'status': 'triggered', 'message': 'Токен активовано'})
    existing = Token.query.filter_by(token_id=token_uuid).first()
    if existing and existing.status != 'active':
        return jsonify({'status': 'already_triggered',
                        'message': 'Цей токен вже спрацьовував.'}), 200
    return jsonify({'status': 'error', 'message': 'Токен не знайдено'}), 404


@app.route('/api/trigger/<token_id>')
def api_trigger(token_id):
    return _canary_trigger_response(token_id)


@app.route(f'/{Config.CANARY_LINK_PREFIX}/<string:slug>')
def canary_short_link(slug):
    if not _CANARY_SLUG_RE.match(slug):
        abort(404)
    row = Token.query.filter_by(url_slug=slug, token_type='url').first()
    if not row:
        abort(404)
    return _canary_trigger_response(row.token_id)


@app.route('/api/save-deploy-settings', methods=['POST'])
@login_required
def save_deploy_settings():
    data = request.json or {}
    cfg  = get_default_deploy_config(current_user)
    if 'github_repo'   in data:
        cfg.github_repo   = (data['github_repo']   or '').strip() or None
    if 'github_branch' in data:
        cfg.github_branch = (data['github_branch'] or 'main').strip() or 'main'
    if data.get('github_token'):
        cfg.github_token  = data['github_token'].strip()
    if 'local_path'    in data:
        cfg.local_path    = (data['local_path']    or '').strip() or None
    if 'pastebin_api'  in data:
        cfg.pastebin_api  = (data['pastebin_api']  or '').strip() or None
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/save-notification-settings', methods=['POST'])
@login_required
def save_notification_settings():
    data = request.json or {}
    if 'telegram_bot'  in data:
        current_user.telegram_bot  = data['telegram_bot'].strip()  or None
    if 'telegram_chat' in data:
        current_user.telegram_chat = data['telegram_chat'].strip() or None
    if 'slack_webhook' in data:
        current_user.slack_webhook = data['slack_webhook'].strip() or None
    if 'alert_email'   in data:
        current_user.alert_email   = data['alert_email'].strip()   or None
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/deploy/github', methods=['POST'])
@login_required
def api_deploy_github():
    from core.deploy import DeployEngine
    tokens = _active_tokens_as_deploy_list()
    if not tokens:
        return jsonify({'message': 'Немає активних токенів', 'status': 'empty'})
    result = DeployEngine().deploy_github(tokens, current_user)
    if result.get('error'):
        return jsonify({'message': result['error'], 'status': 'error'}), 400
    return jsonify({'message': f"OK: {result.get('path')} у {result.get('repo')}",
                    'status': 'success'})


@app.route('/api/deploy/local', methods=['POST'])
@login_required
def api_deploy_local():
    from core.deploy import DeployEngine
    tokens = _active_tokens_as_deploy_list()
    if not tokens:
        return jsonify({'message': 'Немає активних токенів', 'status': 'empty'})
    result = DeployEngine().deploy_local(tokens, current_user)
    return jsonify({'message': f"Локально: {result.get('count')} файлів",
                    'status': 'success'})


@app.route('/api/deploy/pastebin', methods=['POST'])
@login_required
def api_deploy_pastebin():
    return jsonify({'message': 'Pastebin ще не реалізовано', 'status': 'noop'}), 501


@app.route('/api/deploy', methods=['POST'])
@login_required
def api_deploy():
    from core.deploy import DeployEngine
    DeployEngine().deploy_all()
    return jsonify({'message': 'Фонове розгортання виконано', 'status': 'success'})


@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.json or {}
    pwd  = data.get('password') or ''
    if len(pwd) < 6:
        return jsonify({'status': 'error', 'message': 'Мінімум 6 символів'}), 400
    current_user.set_password(pwd)
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/logout-all', methods=['POST'])
@login_required
def api_logout_all():
    return jsonify({'status': 'success',
                    'message': 'Увійдіть знову на всіх пристроях вручну.'})


@app.route('/api/export-data')
@login_required
def api_export_data():
    rows = org_tokens_query().order_by(Token.created_at.desc()).all()
    payload = {
        'tokens': [{
            'token_id':   t.token_id,
            'type':       t.token_type,
            'status':     t.status,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        } for t in rows],
        'activations': [],
    }
    for t in rows:
        for a in t.activations:
            payload['activations'].append({
                'token_id': t.token_id,
                'ip':       a.ip_address,
                'time':     a.timestamp.isoformat() if a.timestamp else None,
            })
    return jsonify(payload)


@app.route('/api/regenerate-key', methods=['POST'])
@login_required
def api_regenerate_key():
    current_user.api_key = f'ct_{current_user.id}_{secrets.token_hex(8)}'
    db.session.commit()
    return jsonify({'status': 'success', 'api_key': current_user.api_key})


# BOOTSTRAP
@app.before_request
def create_test_user():
    if not hasattr(app, 'user_created'):
        with app.app_context():
            db.create_all()
            _migrate_sqlite_schema()
            if not User.query.filter_by(username='admin').first():
                org = Organization.query.filter_by(name='CanaryTrap').first()
                if not org:
                    org = Organization(name='CanaryTrap', description='Default')
                    db.session.add(org)
                    db.session.flush()
                admin = User(username='admin', email='admin@localhost',
                             organization_id=org.id, role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print('✅ Створено тестового адміністратора: admin / admin123')
            app.user_created = True


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=Config.APP_PORT)