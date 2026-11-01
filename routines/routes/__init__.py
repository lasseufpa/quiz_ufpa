"""Registro das rotas HTTP da aplicação."""

from routines.routes import auth, pages, quiz_api


def register_routes(app):
    """Registra todas as rotas HTTP na aplicação Flask."""
    pages.register(app)
    auth.register(app)
    quiz_api.register(app)
