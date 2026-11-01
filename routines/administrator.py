"""Administração de alunos por turma (eventos Socket.IO do painel /admin).

O cadastro em si fica em `routines/classes.py`; aqui só ficam as validações de
permissão e a conversa com o navegador. Todas as operações informam a turma.
"""

import logging

from flask import request, session
from flask_socketio import emit

from routines import classes
from routines import logger  # noqa: F401  (configura o console + arquivo)

log = logging.getLogger(__name__)


# -------------------- Helpers --------------------
def _is_admin():
    return bool(session.get('admin_logged_in'))


def _requested_class(data):
    """Turma pedida pelo cliente (ou a primeira cadastrada)."""
    slug = (data or {}).get('class') or classes.first_slug()
    if slug and classes.exists(slug):
        return slug
    return None


def _student_payload(class_slug):
    return {
        'class': class_slug,
        'class_name': classes.name_of(class_slug),
        'students': sorted(classes.students(class_slug)),
    }


def _broadcast_user_list(class_slug):
    """Envia a lista de alunos dessa turma para todos os admins conectados."""
    emit('update_user_list', _student_payload(class_slug), broadcast=True)


def _error(message):
    emit('admin_error', {'message': message}, to=request.sid)


# -------------------- Eventos do painel /admin --------------------
def admin_join(data=None):
    """Admin se conectou à página de gerenciamento."""
    if not _is_admin():
        return

    class_slug = _requested_class(data)
    if class_slug is None:
        _error('Nenhuma turma cadastrada.')
        return

    log.info(f"Admin se conectou: {request.sid} (turma {class_slug})")
    emit('update_user_list', _student_payload(class_slug), to=request.sid)


def add_user(data):
    """Admin adicionou um aluno à turma."""
    if not _is_admin():
        return

    class_slug = _requested_class(data)
    if class_slug is None:
        _error('Turma não encontrada.')
        return

    nickname, error = classes.add_student(class_slug, data.get('nickname'))
    if error:
        _error(error)
        return

    log.info(f"Aluno adicionado em {class_slug}: {nickname}")
    _broadcast_user_list(class_slug)


def remove_user(data):
    """Admin removeu um aluno da turma."""
    if not _is_admin():
        return

    class_slug = _requested_class(data)
    if class_slug is None:
        _error('Turma não encontrada.')
        return

    removed, error = classes.remove_student(class_slug, data.get('nickname'))
    if error:
        _error(error)
        return
    if removed:
        log.info(f"Aluno removido de {class_slug}: {data.get('nickname')}")
        _broadcast_user_list(class_slug)


def edit_user(data):
    """Admin renomeou um aluno da turma."""
    if not _is_admin():
        return

    class_slug = _requested_class(data)
    if class_slug is None:
        _error('Turma não encontrada.')
        return

    old_nickname = data.get('old_nickname')
    new_nickname, error = classes.rename_student(
        class_slug, old_nickname, data.get('new_nickname')
    )
    if error:
        _error(error)
        return

    log.info(f"Aluno renomeado em {class_slug}: '{old_nickname}' -> '{new_nickname}'")
    _broadcast_user_list(class_slug)
