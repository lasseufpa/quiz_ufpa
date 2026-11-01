"""Eventos do painel de administração (delegam para routines/administrator.py)."""

from routines import administrator


def on_admin_join(data=None):
    """Admin se conectou à página de gerenciamento (de uma turma)."""
    administrator.admin_join(data)


def on_add_user(data):
    """Admin adicionou um novo usuário."""
    administrator.add_user(data)


def on_remove_user(data):
    """Admin removeu um usuário."""
    administrator.remove_user(data)


def on_edit_user(data):
    """Admin editou o nome de um usuário."""
    administrator.edit_user(data)


def register(socketio):
    """Registra os eventos do painel no SocketIO."""
    socketio.on('admin_join')(on_admin_join)
    socketio.on('add_user')(on_add_user)
    socketio.on('remove_user')(on_remove_user)
    socketio.on('edit_user')(on_edit_user)
