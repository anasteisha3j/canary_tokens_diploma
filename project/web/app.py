"""
Flask веб-додаток для CanaryTrap
Інтерфейс керування системою
"""

import os
import re
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.sql import expression as sql_expr

from config import Config

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========== МОДЕЛІ БАЗИ ДАНИХ ==========

class Organization(db.Model):
    """Організації"""
    __tablename__ = 'organizations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    users = db.relationship('User', back_populates='organization', lazy=True)
    tokens = db.relationship('Token', back_populates='organization', lazy=True)

class User(UserMixin, db.Model):
    """Користувач системи"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    role = db.Column(db.String(20), default='user')
    
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    organization = db.relationship('Organization', back_populates='users')
    tokens = db.relationship('Token', backref='owner', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Token(db.Model):
    """Honeypot-токени"""
    __tablename__ = 'tokens'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.String(50), unique=True, nullable=False)
    token_type = db.Column(db.String(50), nullable=False)
    token_value = db.Column(db.String(500), nullable=False)
    tracker = db.Column(db.String(50), nullable=False)
    token_metadata = db.Column(db.Text, default='{}')
    status = db.Column(db.String(20), default='active')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    organization = db.relationship('Organization', back_populates='tokens')
    created_at = db.Column(db.DateTime, default=datetime.now)
    triggered_at = db.Column(db.DateTime, nullable=True)
    url_slug = db.Column(db.String(48), unique=True, nullable=True)
    
    activations = db.relationship('Activation', backref='token', lazy=True)

class Activation(db.Model):
    """Активації токенів"""
    __tablename__ = 'activations'
    
    id = db.Column(db.Integer, primary_key=True)
    token_id = db.Column(db.Integer, db.ForeignKey('tokens.id'), nullable=False)
    ip_address = db.Column(db.String(50))
    country = db.Column(db.String(100))
    city = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    source = db.Column(db.String(100))  # github, web, dns, etc
    activation_metadata = db.Column(db.Text, default='{}')  # ЗМІНА: metadata -> activation_metadata
    timestamp = db.Column(db.DateTime, default=datetime.now)

class Deployment(db.Model):
    """Історія розміщень"""
    __tablename__ = 'deployments'
    
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50))
    tokens_count = db.Column(db.Integer)
    deployment_details = db.Column(db.Text, default='{}')  # ЗМІНА: details -> deployment_details
    created_at = db.Column(db.DateTime, default=datetime.now)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class DeploymentConfig(db.Model):
    """Конфігурації розгортання користувача"""
    __tablename__ = 'deployment_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100))  # наприклад "Основний GitHub", "Тестовий репозиторій"
    
    # Тип розгортання (github, local, pastebin)
    platform = db.Column(db.String(50), nullable=False)  # github, local, pastebin
    
    # Для GitHub
    github_repo = db.Column(db.String(200))
    github_branch = db.Column(db.String(50), default='main')
    github_token = db.Column(db.String(500), nullable=True)
    
    # Для локального
    local_path = db.Column(db.String(200))
    
    # Для Pastebin
    pastebin_api = db.Column(db.String(200))
    pastebin_expiry = db.Column(db.String(20), default='1W')
    
    # Спільні поля
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    
    # Зв'язок
    user = db.relationship('User', backref='deployment_configs')


def _migrate_sqlite_schema():
    if 'sqlite' not in str(db.engine.url):
        return
    try:
        from sqlalchemy import text
        with db.engine.begin() as conn:
            rows = conn.execute(text('PRAGMA table_info(deployment_configs)')).fetchall()
            if not rows:
                return
            cols = {r[1] for r in rows}
            if 'github_token' not in cols:
                conn.execute(text('ALTER TABLE deployment_configs ADD COLUMN github_token VARCHAR(500)'))
            rows_t = conn.execute(text('PRAGMA table_info(tokens)')).fetchall()
            cols_t = {r[1] for r in rows_t} if rows_t else set()
            if cols_t and 'url_slug' not in cols_t:
                conn.execute(text('ALTER TABLE tokens ADD COLUMN url_slug VARCHAR(48)'))
                conn.execute(text(
                    'CREATE UNIQUE INDEX IF NOT EXISTS ix_tokens_url_slug '
                    'ON tokens(url_slug) WHERE url_slug IS NOT NULL'
                ))
    except Exception as e:
        print(f'⚠️ Міграція схеми SQLite: {e}')


def get_default_deploy_config(user):
    c = DeploymentConfig.query.filter_by(user_id=user.id, name='default').first()
    if not c:
        c = DeploymentConfig(user_id=user.id, name='default', platform='github')
        db.session.add(c)
        db.session.commit()
    return c


def get_client_ip():
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or '0.0.0.0'


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
        Token.organization_id == current_user.organization_id
    )


def token_row_to_deploy_dict(t):
    return {
        'id': t.token_id,
        'type': t.token_type,
        'value': t.token_value,
        'tracker': t.tracker,
        'metadata': json.loads(t.token_metadata or '{}')
    }


def user_can_view_token(token):
    if current_user.role == 'admin':
        return True
    if not current_user.organization_id or not token.organization_id:
        return False
    return token.organization_id == current_user.organization_id


def _delete_token_with_activations(token):
    Activation.query.filter_by(token_id=token.id).delete()
    db.session.delete(token)


def _tokens_redirect_status():
    st = (request.form.get('filter_status') or request.args.get('status') or '').strip().lower()
    if st in ('active', 'triggered'):
        return {'status': st}
    return {}


# ========== МАРШРУТИ ==========

@app.route('/')
def index():
    """Головна сторінка"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вхід в систему"""
    # session.clear()
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"🔍 Спроба входу: {username}")
        
        user = User.query.filter_by(username=username).first()
        
        if user:
            print(f"✅ Користувача знайдено: {user.username}")
            if user.check_password(password):
                print(f"✅ Пароль правильний")
                login_user(user)
                flash('Вхід успішний!', 'success')
                return redirect(url_for('dashboard'))
            else:
                print(f"❌ Пароль неправильний")
                flash('Невірний пароль', 'error')
        else:
            print(f"❌ Користувача не знайдено: {username}")
            flash('Невірне ім\'я користувача', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Реєстрація нового користувача та прив'язка до організації"""
    if request.method == 'POST':
        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        organization_name = (request.form.get('organization') or '').strip()
        
        print(f"📝 Спроба реєстрації: {username} ({email})")
        
        if not organization_name:
            flash('Вкажіть назву організації', 'error')
            return redirect(url_for('register'))
        
        if password != confirm_password:
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
            org = Organization.query.filter_by(name=organization_name).first()
            if not org:
                org = Organization(name=organization_name)
                db.session.add(org)
                db.session.flush()

            existing_members = User.query.filter_by(organization_id=org.id).count()
            role = 'org_admin' if existing_members == 0 else 'user'

            user = User(
                username=username,
                email=email,
                organization_id=org.id,
                role=role
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            print(f"✅ Користувача {username} створено (орг: {org.name}, роль: {role})")
            flash('Реєстрація успішна! Тепер можна увійти', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"❌ Помилка при створенні користувача: {e}")
            flash('Помилка при реєстрації. Спробуйте ще раз.', 'error')
            db.session.rollback()
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    """Вихід з системи"""
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Головний дашборд (дані обмежені організацією, крім глобального admin)"""
    tq = org_tokens_query()
    aq = org_activations_query()
    total_tokens = tq.count()
    active_tokens = tq.filter_by(status='active').count()
    total_activations = aq.count()
    
    recent_activations = aq.order_by(Activation.timestamp.desc()).limit(5).all()
    
    if current_user.role == 'admin':
        token_types = db.session.query(
            Token.token_type, db.func.count(Token.id)
        ).group_by(Token.token_type).all()
    elif current_user.organization_id:
        token_types = db.session.query(
            Token.token_type, db.func.count(Token.id)
        ).filter(
            Token.organization_id == current_user.organization_id
        ).group_by(Token.token_type).all()
    else:
        token_types = []
    
    return render_template('dashboard.html',
                         total_tokens=total_tokens,
                         active_tokens=active_tokens,
                         total_activations=total_activations,
                         recent_activations=recent_activations,
                         token_types=token_types)

@app.route('/tokens')
@login_required
def tokens():
    """Список токенів організації (глобальний admin — усі)"""
    status_filter = (request.args.get('status') or '').strip().lower()
    if status_filter not in ('', 'active', 'triggered'):
        status_filter = ''
    q = org_tokens_query().order_by(Token.created_at.desc())
    if status_filter == 'active':
        q = q.filter_by(status='active')
    elif status_filter == 'triggered':
        q = q.filter_by(status='triggered')
    all_tokens = q.all()
    return render_template('tokens.html', tokens=all_tokens, status_filter=status_filter)

@app.route('/tokens/generate', methods=['POST'])
@login_required
def generate_tokens():
    """Генерація токенів для організації поточного користувача"""
    from core.token_generator import TokenGenerator
    from core.deploy import DeployEngine

    if current_user.role != 'admin' and not current_user.organization_id:
        flash('Спочатку додайте організацію у профілі (налаштування).', 'error')
        return redirect(url_for('tokens'))
    
    token_type = request.form.get('token_type')
    count = int(request.form.get('count', 5))
    
    platforms = [p for p in request.form.getlist('platforms') if p != 'pastebin']
    if 'pastebin' in request.form.getlist('platforms'):
        flash('Pastebin поки не підтримується; токени згенеровано без Pastebin.', 'warning')

    gen = TokenGenerator(
        public_base_url=app.config.get('PUBLIC_BASE_URL', Config.PUBLIC_BASE_URL),
        link_prefix=app.config.get('CANARY_LINK_PREFIX', Config.CANARY_LINK_PREFIX),
    )
    if token_type == 'mixed':
        tokens = gen.generate_mixed({
            'aws_key': count,
            'github_token': count,
            'url': count//2,
            'document': count//2
        })
    else:
        tokens = gen.generate_batch(token_type, count)

    org_id = current_user.organization_id
    if current_user.role == 'admin' and not org_id:
        flash('Для глобального адміністратора потрібна організація в профілі, щоб прив\'язати токени.', 'error')
        return redirect(url_for('settings'))
    
    for t in tokens:
        token = Token(
            token_id=t['id'],
            token_type=t['type'],
            token_value=t['value'],
            tracker=t['tracker'],
            token_metadata=json.dumps(t['metadata']),
            user_id=current_user.id,
            organization_id=org_id,
            url_slug=t.get('url_slug'),
        )
        db.session.add(token)
    
    db.session.commit()
    
    if platforms:
        engine = DeployEngine()
        for platform in platforms:
            if platform == 'github':
                result = engine.deploy_github(tokens, current_user)
                if result.get('error'):
                    flash(f"GitHub: {result['error']}", 'error')
                else:
                    flash(
                        f"GitHub: {result.get('path', '')} → {result.get('repo', '')}",
                        'success'
                    )
            elif platform == 'local':
                engine.deploy_local(tokens, current_user)
                flash('Локальне розміщення виконано.', 'success')
    
    org_label = current_user.organization.name if current_user.organization else 'N/A'
    flash(f'Згенеровано {len(tokens)} токенів для «{org_label}»', 'success')
    return redirect(url_for('tokens'))

@app.route('/tokens/<int:token_id>')
@login_required
def token_detail(token_id):
    """Деталі токена"""
    token = Token.query.get_or_404(token_id)
    if not user_can_view_token(token):
        abort(403)
    activations = Activation.query.filter_by(token_id=token.id)\
        .order_by(Activation.timestamp.desc())\
        .all()
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
    to_remove = q.all()
    n = 0
    for t in to_remove:
        _delete_token_with_activations(t)
        n += 1
    db.session.commit()
    flash(f'Видалено токенів: {n}', 'success')
    return redirect(url_for('tokens', **_tokens_redirect_status()))


@app.route('/activations')
@login_required
def activations():
    """Активації токенів вашої організації"""
    all_activations = org_activations_query().order_by(Activation.timestamp.desc()).all()
    return render_template('activations.html', activations=all_activations)

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Налаштування"""
    if request.method == 'POST':
        org_name = (request.form.get('organization') or '').strip()
        if org_name:
            if current_user.organization_id:
                org = Organization.query.get(current_user.organization_id)
                if org and org.name != org_name:
                    taken = Organization.query.filter(
                        Organization.name == org_name,
                        Organization.id != org.id
                    ).first()
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
    tq = org_tokens_query()
    total_tokens = tq.count()
    total_activations = org_activations_query().count()
    total_users = User.query.filter_by(organization_id=current_user.organization_id).count() \
        if current_user.organization_id else User.query.count()
    if current_user.role == 'admin':
        total_users = User.query.count()
    last_activation = org_activations_query().order_by(Activation.timestamp.desc()).first()
    
    return render_template('settings.html',
                         user=current_user,
                         deploy_config=deploy_config,
                         total_tokens=total_tokens,
                         total_activations=total_activations,
                         total_users=total_users,
                         last_activation=last_activation,
                         public_base_url=app.config.get('PUBLIC_BASE_URL', ''),
                         canary_link_prefix=app.config.get('CANARY_LINK_PREFIX', 'i'))

@app.route('/api/ping')
def api_ping():
    """Доступ без логіну: перевірте з телефону / зовнішньої мережі, що трафік доходить."""
    return jsonify({'ok': True})


@app.route('/api/stats')
@login_required
def api_stats():
    """Легкі агрегати для script.js (періодичний poll)."""
    tq = org_tokens_query()
    aq = org_activations_query()
    return jsonify({
        'tokens': tq.count(),
        'activations': aq.count(),
        'triggered': tq.filter(Token.status == 'triggered').count(),
    })


_CANARY_SLUG_RE = re.compile(r'^[A-Za-z0-9_-]{12,48}$')


def _canary_trigger_response(token_uuid: str):
    """Спільна логіка для /api/trigger/<uuid> та короткого /{prefix}/<slug>."""
    from core.monitor import Monitor

    ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', 'Unknown')
    monitor = Monitor()
    if monitor.manual_trigger(token_uuid, ip, user_agent):
        return jsonify({'status': 'triggered', 'message': 'Токен активовано'})
    existing = Token.query.filter_by(token_id=token_uuid).first()
    if existing and existing.status != 'active':
        return jsonify({
            'status': 'already_triggered',
            'message': 'Цей канареєвий URL уже спрацьовував. Створіть новий URL-токен.',
        }), 200
    return jsonify({'status': 'error', 'message': 'Токен не знайдено'}), 404


@app.route('/api/trigger/<token_id>')
def api_trigger(token_id):
    """HTTP-canary (legacy): повний UUID у шляху — для старих токенів."""
    return _canary_trigger_response(token_id)


@app.route(f'/{Config.CANARY_LINK_PREFIX}/<string:slug>')
def canary_short_link(slug):
    """Короткий канареєвий URL без UUID у адресі."""
    if not _CANARY_SLUG_RE.match(slug):
        abort(404)
    row = Token.query.filter_by(url_slug=slug, token_type='url').first()
    if not row:
        abort(404)
    return _canary_trigger_response(row.token_id)

@app.route('/api/save-deploy-settings', methods=['POST'])
@login_required
def save_deploy_settings():
    """Збереження налаштувань розміщення (DeploymentConfig)"""
    data = request.json or {}
    cfg = get_default_deploy_config(current_user)

    if 'github_repo' in data:
        cfg.github_repo = (data.get('github_repo') or '').strip() or None
    if 'github_branch' in data:
        cfg.github_branch = (data.get('github_branch') or 'main').strip() or 'main'
    if data.get('github_token'):
        cfg.github_token = data.get('github_token').strip()
    if 'local_path' in data:
        cfg.local_path = (data.get('local_path') or '').strip() or None
    if 'pastebin_api' in data:
        cfg.pastebin_api = (data.get('pastebin_api') or '').strip() or None

    db.session.commit()
    return jsonify({'status': 'success'})


def _active_tokens_as_deploy_list():
    q = org_tokens_query().filter_by(status='active').order_by(Token.created_at.desc()).limit(200)
    return [token_row_to_deploy_dict(t) for t in q.all()]


@app.route('/api/deploy/github', methods=['POST'])
@login_required
def api_deploy_github():
    from core.deploy import DeployEngine
    tokens = _active_tokens_as_deploy_list()
    if not tokens:
        return jsonify({'message': 'Немає активних токенів для розміщення', 'status': 'empty'})
    result = DeployEngine().deploy_github(tokens, current_user)
    if result.get('error'):
        return jsonify({'message': result['error'], 'status': 'error'}), 400
    return jsonify({'message': f"OK: {result.get('path')} у {result.get('repo')}", 'status': 'success'})


@app.route('/api/deploy/local', methods=['POST'])
@login_required
def api_deploy_local():
    from core.deploy import DeployEngine
    tokens = _active_tokens_as_deploy_list()
    if not tokens:
        return jsonify({'message': 'Немає активних токенів', 'status': 'empty'})
    result = DeployEngine().deploy_local(tokens, current_user)
    return jsonify({'message': f"Локально: {result.get('count')} файлів", 'status': 'success'})


@app.route('/api/deploy/pastebin', methods=['POST'])
@login_required
def api_deploy_pastebin():
    return jsonify({'message': 'Pastebin ще не реалізовано', 'status': 'noop'}), 501


@app.route('/api/deploy', methods=['POST'])
@login_required
def api_deploy():
    from core.deploy import DeployEngine
    DeployEngine().deploy_all()
    return jsonify({'message': 'Фонове локальне розгортання виконано (див. лог сервера)', 'status': 'success'})


@app.route('/api/save-notification-settings', methods=['POST'])
@login_required
def save_notification_settings():
    """Заглушка: канали з config.py / змінних оточення (див. AlertSystem)."""
    return jsonify({'status': 'success', 'message': 'Глобальні канали: TELEGRAM_*, SLACK_*, ALERT_EMAIL у .env'})


@app.route('/api/change-password', methods=['POST'])
@login_required
def api_change_password():
    data = request.json or {}
    password = data.get('password') or ''
    if len(password) < 6:
        return jsonify({'status': 'error', 'message': 'Мінімум 6 символів'}), 400
    current_user.set_password(password)
    db.session.commit()
    return jsonify({'status': 'success'})


@app.route('/api/logout-all', methods=['POST'])
@login_required
def api_logout_all():
    return jsonify({'status': 'success', 'message': 'Увійдіть знову на всіх пристроях вручну (сесії не інвалідуються централізовано).'})


@app.route('/api/export-data')
@login_required
def api_export_data():
    rows = org_tokens_query().order_by(Token.created_at.desc()).all()
    payload = {
        'tokens': [{
            'token_id': t.token_id,
            'type': t.token_type,
            'status': t.status,
            'created_at': t.created_at.isoformat() if t.created_at else None,
        } for t in rows],
        'activations': []
    }
    for t in rows:
        for a in t.activations:
            payload['activations'].append({
                'token_id': t.token_id,
                'ip': a.ip_address,
                'time': a.timestamp.isoformat() if a.timestamp else None,
            })
    return jsonify(payload)


@app.route('/api/regenerate-key', methods=['POST'])
@login_required
def api_regenerate_key():
    import secrets
    return jsonify({'status': 'success', 'api_key': f'ct_{current_user.id}_{secrets.token_hex(8)}'})


# ========== СТВОРЕННЯ ТЕСТОВОГО КОРИСТУВАЧА ==========
@app.before_request
def create_test_user():
    """Ініціалізація БД та тестовий admin при першому запиті"""
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
                admin = User(
                    username='admin',
                    email='admin@localhost',
                    organization_id=org.id,
                    role='admin'
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Створено тестового адміністратора: admin / admin123")
            app.user_created = True

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)