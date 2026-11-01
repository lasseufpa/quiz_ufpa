"""Ponto de entrada do quiz_ufpa.

Toda a lógica vive em `routines/`. Aqui apenas criamos a aplicação e, quando
executado diretamente, subimos o servidor.
"""

from routines.bootstrap import create_app, run_app

app, socketio = create_app()

if __name__ == '__main__':
    run_app(app, socketio)
