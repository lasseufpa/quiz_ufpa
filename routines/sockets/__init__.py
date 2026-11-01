"""Registro dos eventos Socket.IO da aplicação."""

from routines.sockets import admin, connection, game


def register_socket_handlers(socketio):
    """Registra todos os eventos Socket.IO."""
    connection.register(socketio)
    admin.register(socketio)
    game.register(socketio)
