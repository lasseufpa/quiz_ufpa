"""Registro das rotas HTTP da aplicação."""

from routines import logger  # noqa: F401  (configura o console + arquivo)
from routines import mathjax_setup
from routines.routes import analysis, auth, pages, quiz_api


def register_routes(app):
    """Registra todas as rotas HTTP na aplicação Flask."""
    pages.register(app)
    auth.register(app)
    analysis.register(app)
    quiz_api.register(app)

    # Se faltar a cópia local, o MathJax é baixado em segundo plano. A checagem
    # abaixo é feita a cada página justamente para que o layout passe a usar os
    # arquivos locais assim que o download terminar.
    mathjax_setup.ensure_local_assets(app.static_folder)

    @app.context_processor
    def inject_mathjax_assets():
        return {'mathjax_local_fonts': mathjax_setup.has_local_assets(app.static_folder)}
