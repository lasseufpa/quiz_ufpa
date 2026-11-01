"""Criação e inicialização da aplicação Flask + Socket.IO.

Este módulo concentra o "wiring": lê os segredos, cria a app, registra as rotas
(`routines.routes`) e os eventos de socket (`routines.sockets`) e restaura o
estado salvo. O `app.py` da raiz só chama `create_app()` e `run_app()`.
"""

import logging
import os
import secrets
import threading

from flask import Flask, request
from flask_socketio import SocketIO

from routines import logger  # noqa: F401  (configura console + arquivo)
from routines import constants, runtime
from routines import game_state_handler as game_handler
from routines import secrets as secret_store
from routines.network import get_local_ip
from routines.persistence import restore_full_state
from routines.routes import register_routes
from routines.sockets import register_socket_handlers

log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')


def create_app():
    """Cria a aplicação Flask, o Socket.IO e registra tudo. Retorna (app, socketio)."""
    for folder in (constants.QUIZZES_FOLDER, constants.UPLOAD_FOLDER, constants.SECRET_FOLDER):
        os.makedirs(folder, exist_ok=True)

    secret_key, admin_hash = secret_store.read_secret_file()

    # Primeira execução: a senha do professor ainda não existe. O SECRET_KEY é
    # gerado automaticamente (não precisa ser memorizado) e a senha é definida
    # na tela /setup.
    runtime.setup_required = admin_hash is None
    runtime.admin_password = admin_hash or ''
    if secret_key is None:
        secret_key = secrets.token_hex(32)

    app = Flask(
        __name__,
        template_folder=TEMPLATES_DIR,
        static_folder=STATIC_DIR,
    )
    app.config['SECRET_KEY'] = secret_key

    socketio = SocketIO(
        app,
        async_mode='eventlet',  # FORÇA usar eventlet
        logger=False,
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1e7,  # 10MB
    )

    runtime.game_state = game_handler.clear_game_state()
    runtime.quiz_data = None
    runtime.socketio = socketio

    @app.after_request
    def log_request(response):
        """Grava no log cada requisição HTTP (exceto arquivos estáticos)."""
        if not request.path.startswith('/static/'):
            log.info(f"{request.method} {request.path} -> {response.status_code}")
        return response

    register_routes(app)
    register_socket_handlers(socketio)

    if restore_full_state():
        log.info("Server resumed with saved game state.")
    else:
        log.info("No saved game state found. Starting fresh.")

    return app, socketio


def _open_browser(url):
    """Abre o navegador padrão; falha silenciosamente em ambiente headless."""
    try:
        import webbrowser
        webbrowser.open(url)
    except Exception as e:
        log.debug(f"Não foi possível abrir o navegador: {e}")


def run_app(app, socketio):
    """Sobe o servidor HTTP/Socket.IO."""
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    port = int(os.environ.get('QUIZ_PORT', '5000'))

    log.info("Servidor Flask-Quiz iniciado!")

    if runtime.setup_required:
        setup_url = f"http://localhost:{port}/setup"
        log.info("Primeira execução: defina a senha do professor na tela de configuração.")
        log.info(f"Abra {setup_url} (o navegador deve abrir automaticamente).")
        if os.environ.get('QUIZ_OPEN_BROWSER', '1') == '1' and (
                os.environ.get('WERKZEUG_RUN_MAIN') or not debug):
            # Espera o servidor subir; no reloader, só o processo filho abre
            threading.Timer(2.0, _open_browser, args=(setup_url,)).start()
    else:
        log.info(f"Aponte seu navegador de host (professor) para: http://localhost:{port}/host")
        log.info(f"Aponte seu navegador de admin para: http://localhost:{port}/admin")

    local_ip = get_local_ip()
    log.info(f"Alunos devem acessar: http://{local_ip}:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)
