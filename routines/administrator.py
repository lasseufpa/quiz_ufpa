"""Administração de usuários: allow-list de jogadores que podem entrar no quiz.

Responsável por carregar/salvar `.private/users.json` (dicionário
{nome_minusculo: NomeOriginal}) e pelos eventos Socket.IO do painel /admin.
"""

import logging

from flask import request, session
from flask_socketio import emit

from routines import json_store
from routines import logger  # noqa: F401  (configura o console + arquivo)

USERS_FILE = '.private/users.json'

log = logging.getLogger(__name__)


def load_users(filename=USERS_FILE):
    """Carrega a lista de usuários do JSON. Retorna um DICIONÁRIO {lower: canonical}."""
    data, source = json_store.read_json(filename)

    if data is None:
        if source == 'missing':
            log.warning(f"Aviso: {filename} não encontrado. Criando um novo.")
            save_users({})
        else:
            log.error(f"Aviso: {filename} inválido e sem backup. Tratando como lista vazia.")
        return {}

    if not isinstance(data, list) or not all(isinstance(s, str) for s in data):
        log.warning(f"Aviso: {filename} mal formatado. Tratando como lista vazia.")
        return {}

    # Cria um dicionário {nome_minusculo: NomeOriginal}
    return {user.lower(): user for user in data}


def save_users(users_dict, filename=USERS_FILE):
    """Salva o DICIONÁRIO de usuários de volta no JSON (apenas os nomes originais)."""
    canonical_names = list(users_dict.values())
    json_store.write_json(filename, canonical_names)


# Estado em memória: {nome_minusculo: NomeOriginal}
REGISTERED_USERS = load_users()
log.info(f"--- {len(REGISTERED_USERS)} usuários carregados de '{USERS_FILE}' ---")


def is_registered(nickname):
    """Retorna o nome canônico do usuário, ou None se não estiver cadastrado."""
    if not nickname:
        return None
    return REGISTERED_USERS.get(nickname.strip().lower())


def _broadcast_user_list():
    """Envia a lista atualizada de usuários para todos os admins conectados."""
    emit('update_user_list', sorted(REGISTERED_USERS.values()), broadcast=True)


# -------------------- Eventos do painel /admin --------------------
def admin_join():
    """Admin se conectou à página de gerenciamento."""
    if not session.get('admin_logged_in'):
        return

    log.info(f"Admin se conectou: {request.sid}")
    emit('update_user_list', sorted(REGISTERED_USERS.values()), to=request.sid)


def add_user(data):
    """Admin adicionou um novo usuário."""
    if not session.get('admin_logged_in'):
        return

    nickname = data.get('nickname', '').strip()
    nickname_lower = nickname.lower()

    if nickname and nickname_lower not in REGISTERED_USERS:
        REGISTERED_USERS[nickname_lower] = nickname
        save_users(REGISTERED_USERS)
        log.info(f"Admin adicionou usuário: {nickname}")
        _broadcast_user_list()
    elif nickname_lower in REGISTERED_USERS:
        emit('admin_error', {'message': f'O nome "{nickname}" (ou variação) já existe.'}, to=request.sid)


def remove_user(data):
    """Admin removeu um usuário."""
    if not session.get('admin_logged_in'):
        return

    nickname = data.get('nickname', '')
    nickname_lower = nickname.lower()

    if nickname_lower in REGISTERED_USERS:
        del REGISTERED_USERS[nickname_lower]
        save_users(REGISTERED_USERS)
        log.info(f"Admin removeu usuário: {nickname}")
        _broadcast_user_list()


def edit_user(data):
    """Admin editou o nome de um usuário."""
    if not session.get('admin_logged_in'):
        return

    old_nickname = data.get('old_nickname')
    new_nickname = data.get('new_nickname', '').strip()

    if not old_nickname or not new_nickname:
        emit('admin_error', {'message': 'O novo nome não pode ser vazio.'}, to=request.sid)
        return

    old_lower = old_nickname.lower()
    new_lower = new_nickname.lower()

    if old_lower not in REGISTERED_USERS:
        emit('admin_error', {'message': 'Usuário original não encontrado.'}, to=request.sid)
        return

    if new_lower in REGISTERED_USERS and new_lower != old_lower:
        emit('admin_error', {'message': f'O nome "{new_nickname}" (ou variação) já existe.'}, to=request.sid)
        return

    del REGISTERED_USERS[old_lower]
    REGISTERED_USERS[new_lower] = new_nickname
    save_users(REGISTERED_USERS)

    log.info(f"Admin editou usuário: de '{old_nickname}' para '{new_nickname}'")
    _broadcast_user_list()
