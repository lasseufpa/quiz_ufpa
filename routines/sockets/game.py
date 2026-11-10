"""Eventos de condução da partida (iniciar, avançar, responder, resultados)."""

import logging
import os

from flask import request
from flask_socketio import emit, leave_room

from routines import (classes, constants, files_handler, game_logic, json_store,
                      persistence, room, runtime)
from routines import game_state_handler as game_handler
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
    game_state['quiz_name'] = data.get('quiz-name')
    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info(f"Iniciando o jogo da turma '{classes.name_of(class_slug)}'!")
    game_logic.advance_question(runtime.socketio, game_state, runtime.quiz_data)


def on_open_room(data):
    """O apresentador abriu a sala: fixa a turma que pode entrar agora."""
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    data = data or {}
    class_slug = data.get('class')
    if not class_slug or not classes.exists(class_slug):
        emit('admin_error', {'message': 'Turma inválida para abrir a sala.'}, to=request.sid)
        return

    game_state['class_slug'] = class_slug
    game_state['team_mode'] = bool(data.get('team_mode', game_state.get('team_mode', False)))

    if game_state['team_mode']:
        # Quem já estava na sala precisa de um time (reabertura da sala)
        teams = game_state.setdefault('teams', {})
        for index, sid in enumerate(game_state['players']):
            if sid not in teams:
                teams[sid] = constants.TEAM_KEYS[index % len(constants.TEAM_KEYS)]
    else:
        game_state['teams'] = {}

    persistence.save_full_state(game_state, runtime.quiz_data)
    log.info("Sala aberta para a turma '%s' (modo time: %s).",
             classes.name_of(class_slug), 'ligado' if game_state['team_mode'] else 'desligado')
    emit('room_info', room.payload(), broadcast=True)
    emit('update_player_list', game_handler.players_payload(game_state),
         to=game_state['host_sid'])


def on_close_room():
    """O apresentador voltou para a escolha de turma/quiz.

    A troca NÃO é mais bloqueada quando há alunos na sala: a sala é fechada e
    todos são expulsos (precisam entrar de novo quando outra sala abrir).
    """
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    had_players = len(game_state['players'])
    player_sids = list(game_state['players'].keys())

    if had_players:
        emit('room_closed', {
            'reason': 'O professor fechou a sala para trocar a turma/quiz. '
                      'Digite seu nome novamente quando ela abrir.'
        }, broadcast=True)

    # Tira os expulsos da sala da partida: se ficassem, receberiam as
    # perguntas da próxima partida enquanto ainda estão na tela de entrada.
    for sid in player_sids:
        try:
            leave_room(constants.GAME_ROOM, sid=sid, namespace='/')
        except Exception as e:  # sid já desconectado
            log.debug("Não foi possível remover %s da sala: %s", sid, e)

    runtime.quiz_data = None
    game_state.clear()
    game_state.update(game_handler.clear_game_state())
    game_state['host_sid'] = request.sid   # o apresentador continua conectado
    game_state['state'] = constants.STATE_LOBBY

    # O estado salvo era da partida anterior e não serve mais (apaga também o
    # backup, senão a partida voltaria ao reiniciar o servidor)
    json_store.delete_json(constants.GAME_SAVE_FILE)

    log.info("Sala fechada para troca de turma/quiz (%d aluno(s) desconectado(s)).",
             had_players)

    emit('room_info', room.payload(), broadcast=True)
    emit('update_player_list', [], to=request.sid)

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


def on_play_again():
    """O professor clicou em "Jogar novamente" na tela de fim de quiz.

    Zera a partida mas mantém os alunos na sala: todos continuam no mesmo
    contexto e basta clicar em "Iniciar Jogo" para valer de novo.
    """
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return
    if game_state['state'] != constants.STATE_GAMEOVER:
        log.warning("play_again ignorado: a partida ainda está em andamento")
        return

    game_logic.reset_for_new_match(game_state, runtime.quiz_data)

    emit('game_restarted', {
        'class': game_state.get('class_slug'),
        'class_name': classes.name_of(game_state.get('class_slug')),
        'quiz_name': game_state.get('quiz_name'),
    }, broadcast=True)

    if game_state['host_sid']:
        emit('update_player_list', game_handler.players_payload(game_state),
             to=game_state['host_sid'])
        emit('update_answer_count', {
            'answered': 0,
            'total': game_handler.online_count(game_state)
        }, to=game_state['host_sid'])


def register(socketio):
    """Registra os eventos da partida no SocketIO."""
    socketio.on('open_room')(on_open_room)
    socketio.on('close_room')(on_close_room)
    socketio.on('start_game')(on_start_game)
    socketio.on('next_question')(on_next_question)
    socketio.on('submit_answer')(on_submit_answer)
    socketio.on('show_results')(on_show_results)
    socketio.on('force_end_quiz')(on_force_end_quiz)
    socketio.on('play_again')(on_play_again)
