"""Autenticação do apresentador/admin e configuração inicial da senha."""

import hashlib
import logging

from flask import (
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from routines import logger  # noqa: F401  (configura console + arquivo)
from routines import runtime
from routines import secrets as secret_store

log = logging.getLogger(__name__)


def require_initial_setup():
    """Enquanto a senha do professor não for definida, redireciona para /setup."""
    if not runtime.setup_required:
        return None
    if request.endpoint in ('setup', 'static'):
        return None
    if request.path.startswith('/socket.io'):
        return None
    return redirect(url_for('setup'))


def setup():
    """Tela de configuração inicial da senha do professor."""
    if not runtime.setup_required:
        return redirect(url_for('player_join'))

    error = None
    if request.method == 'POST':
        password = (request.form.get('password') or '').strip()
        confirm = (request.form.get('confirm') or '').strip()

        if len(password) < 4:
            error = 'A senha precisa ter pelo menos 4 caracteres.'
        elif password != confirm:
            error = 'As senhas não conferem.'

        if error is None:
            admin_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            secret_store.write_secret_file(
                current_app.config['SECRET_KEY'], admin_hash
            )
            runtime.admin_password = admin_hash
            runtime.setup_required = False
            log.info("Senha do professor definida na tela de configuração inicial.")
            # Já entra como apresentador/admin, para não pedir a senha de novo
            session['host_logged_in'] = True
            session['admin_logged_in'] = True
            return redirect(url_for('host_view'))

    return render_template('setup.html', error=error)


def _password_matches(password):
    """Compara a senha informada com o hash configurado."""
    if not password:
        return False
    digest = hashlib.sha256(password.encode('utf-8')).hexdigest().strip()
    return digest == runtime.admin_password


def host_login():
    """Login do apresentador."""
    if request.method == 'POST':
        if _password_matches(request.form.get('password')):
            session['host_logged_in'] = True
            log.info("Login de anfitrião bem-sucedido.")
            return redirect(url_for('host_view'))
        flash('Senha incorreta!', 'error')
        log.warning("Tentativa de login de anfitrião falhou.")
    return render_template('host_login.html')


def admin_login():
    """Login do painel de administração."""
    if request.method == 'POST':
        if _password_matches(request.form.get('password')):
            session['admin_logged_in'] = True
            log.info("Login de admin bem-sucedido.")
            return redirect(url_for('admin_view'))
        flash('Senha incorreta!', 'error')
        log.warning("Tentativa de login de admin falhou.")
    return render_template('admin_login.html')


def admin_view():
    """Página de gerenciamento de usuários (protegida)."""
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html')


def admin_logout():
    """Remove o admin da sessão."""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


def register(app):
    app.before_request(require_initial_setup)
    app.add_url_rule('/setup', 'setup', setup, methods=['GET', 'POST'])
    app.add_url_rule('/host/login', 'host_login', host_login, methods=['GET', 'POST'])
    app.add_url_rule('/admin/login', 'admin_login', admin_login, methods=['GET', 'POST'])
    app.add_url_rule('/admin', 'admin_view', admin_view)
    app.add_url_rule('/admin/logout', 'admin_logout', admin_logout)
