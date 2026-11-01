"""Eventos de condução da partida (iniciar, avançar, responder, resultados)."""

import logging

from flask import request
from flask_socketio import emit

from routines import files_handler, game_logic, persistence, runtime
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)


def on_start_game(data):
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    try:
        runtime.quiz_data = files_handler.load_quiz_data(data.get('quiz-name'))
    except (FileNotFoundError, ValueError) as e:
        # Não derruba o servidor: avisa o apresentador e mantém o jogo parado
        log.error(f"Falha ao carregar o quiz: {e}")
        emit('admin_error', {'message': str(e)}, to=request.sid)
        return

    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info("Iniciando o jogo!")
    game_logic.advance_question(runtime.socketio, game_state, runtime.quiz_data)


def on_next_question():
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return
    game_logic.advance_question(runtime.socketio, game_state, runtime.quiz_data)


def on_submit_answer(data):
    game_logic.submit_answer(runtime.game_state, runtime.quiz_data, data)


def on_show_results():
    game_logic.show_results(runtime.game_state, runtime.quiz_data)


def on_force_end_quiz():
    game_logic.force_end_quiz(runtime.game_state, runtime.quiz_data)


def register(socketio):
    """Registra os eventos da partida no SocketIO."""
    socketio.on('start_game')(on_start_game)
    socketio.on('next_question')(on_next_question)
    socketio.on('submit_answer')(on_submit_answer)
    socketio.on('show_results')(on_show_results)
    socketio.on('force_end_quiz')(on_force_end_quiz)
