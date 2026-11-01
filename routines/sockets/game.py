"""Eventos de condução da partida (iniciar, avançar, responder, resultados)."""

import logging

from flask import request
from flask_socketio import emit

from routines import classes, files_handler, game_logic, persistence, room, runtime
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)


def on_start_game(data):
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    class_slug = data.get('class')
    if not class_slug or not classes.exists(class_slug):
        emit('admin_error', {'message': 'Selecione a turma antes de iniciar o jogo.'},
             to=request.sid)
        return

    try:
        runtime.quiz_data = files_handler.load_quiz_data(class_slug, data.get('quiz-name'))
    except (FileNotFoundError, ValueError) as e:
        # Não derruba o servidor: avisa o apresentador e mantém o jogo parado
        log.error(f"Falha ao carregar o quiz: {e}")
        emit('admin_error', {'message': str(e)}, to=request.sid)
        return

    game_state['class_slug'] = class_slug
    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info(f"Iniciando o jogo da turma '{classes.name_of(class_slug)}'!")
    game_logic.advance_question(runtime.socketio, game_state, runtime.quiz_data)


def on_open_room(data):
    """O apresentador abriu a sala: fixa a turma que pode entrar agora."""
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    class_slug = (data or {}).get('class')
    if not class_slug or not classes.exists(class_slug):
        emit('admin_error', {'message': 'Turma inválida para abrir a sala.'}, to=request.sid)
        return

    game_state['class_slug'] = class_slug
    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info(f"Sala aberta para a turma '{classes.name_of(class_slug)}'.")
    emit('room_info', room.payload(), broadcast=True)


def on_close_room():
    """O apresentador voltou para a escolha de turma/quiz (só se a sala está vazia)."""
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    if game_state['players']:
        emit('admin_error', {
            'message': 'Já há alunos na sala: não dá para fechar agora.'
        }, to=request.sid)
        return

    game_state['class_slug'] = None
    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info("Sala fechada (apresentador voltou à escolha de turma/quiz).")
    emit('room_info', room.payload(), broadcast=True)


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
    socketio.on('open_room')(on_open_room)
    socketio.on('close_room')(on_close_room)
    socketio.on('start_game')(on_start_game)
    socketio.on('next_question')(on_next_question)
    socketio.on('submit_answer')(on_submit_answer)
    socketio.on('show_results')(on_show_results)
    socketio.on('force_end_quiz')(on_force_end_quiz)
