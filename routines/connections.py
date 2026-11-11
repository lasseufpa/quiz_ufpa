from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import logging
import time

from routines import logger  # noqa: F401  (configura o console + arquivo)
from routines import constants
from routines import game_logic
from routines import game_state_handler as game_handler

log = logging.getLogger(__name__)

def connect_host(game_state, QUIZ_DATA):
    # Require host authentication
    if not session.get('host_logged_in'):
        emit('admin_error', {'message': 'Você precisa estar logado como anfitrião para controlar o jogo.'}, to=request.sid)
        return

    # --- Overwrite any existing host ---
    old_host_sid = game_state.get('host_sid')
    if old_host_sid and old_host_sid != request.sid:
        # Notify the old host that they have been replaced
        emit('host_replaced', {'message': 'Um novo anfitrião assumiu o controle.'}, to=old_host_sid)
        log.info(f"Anfitrião {old_host_sid} foi substituído por {request.sid}")

    # Set the new host
    game_state['host_sid'] = request.sid
    join_room(constants.GAME_ROOM)
    log.info(f"Anfitrião conectado/substituído: {request.sid}")

    # --- Act like a page refresh: send current state to the new host ---
    # 1. Send current player list (may be empty)
    emit('update_player_list', game_handler.players_payload(game_state), to=game_state['host_sid'])


    elapsed_time = None

    def _remaining():
        """Tempo restante da pergunta (None enquanto a fase de leitura roda)."""
        if elapsed_time is None:
            return None
        duration = game_state.get('answer_duration') or constants.QUESTION_DURATION
        return max(0, duration - elapsed_time)

    def _reading_left():
        """Segundos que faltam da fase de leitura (None se ela já acabou)."""
        started = game_state.get('reading_started_at')
        duration = game_state.get('reading_duration')
        if started is None or not duration:
            return None
        left = duration - (time.time() - started)
        return round(left) if left > 0 else None

    # 2. If there are players and a quiz is loaded, send the appropriate state
    if game_state['players'] and QUIZ_DATA is not None:
        # Tell host the current question index and game state
        q_index = game_state['current_question']
        question_data = QUIZ_DATA['questions'][q_index]
        
        if game_state['question_start_time'] is not None:
            elapsed_time = time.time() - game_state['question_start_time']
        emit('resume_host_state', {
            'current_question': game_state['current_question'],
            'question_data': question_data,
            'state': game_state['state'],
            'total_questions': len(QUIZ_DATA['questions']),
            'question_index': q_index,
            'total_players': game_handler.online_count(game_state),
            'answered_count': len(game_state['answers']),
            'remaining_time': _remaining(),
            'leaderboard': game_state.get('final_leaderboard', []),
            'teams': game_state.get('final_teams', []),
            'team_mode': bool(game_state.get('team_mode')),
            'quiz_name': game_state.get('quiz_name')
        }, to=game_state['host_sid'])

        # If game is in QUESTION state, resend the current question
        if game_state['state'] == constants.STATE_QUESTION and game_state['current_question'] >= 0:
            q_index = game_state['current_question']
            question_data = QUIZ_DATA['questions'][q_index]
            figure = question_data['figure']
            chart_path = f"{constants.UPLOAD_FOLDER}/{figure}" if figure != "none" else ""
            payload = {
                'text': question_data['text'],
                'options': question_data['options'],
                'question_index': q_index,
                'total_questions': len(QUIZ_DATA['questions']),
                'chart_path': chart_path,
                'remaining_time': _remaining(),
                'reading_time': game_state.get('reading_duration'),
                'reading_remaining': _reading_left(),
                'answer_time': game_state.get('answer_duration')
            }
            emit('show_question', payload, to=game_state['host_sid'])  # only to host (others already have it)
            # Also optionally broadcast the answer count to the new host
            emit('update_answer_count', {
                'answered': len(game_state['answers']),
                'total': game_handler.online_count(game_state)
            }, to=game_state['host_sid'])

        # If game is in ANSWER state, resend the results
        elif game_state['state'] == constants.STATE_ANSWER and game_state['current_question'] >= 0:
            # O mesmo payload da tela de resultados (o apresentador desenha no
            # navegador, então o F5 volta exatamente para a mesma tela).
            payload = game_state.get('last_results')
            if payload is None:
                payload = game_logic.build_results_payload(game_state, QUIZ_DATA)
            if payload:
                emit('show_results', payload, to=game_state['host_sid'])

    # Optional: broadcast to players that a new host is in control (if desired)
    if old_host_sid != request.sid:
        emit('host_changed', {'message': 'Um novo anfitrião assumiu o controle do jogo.'}, broadcast=True)

        emit('update_player_list', game_handler.players_payload(game_state), to=game_state['host_sid'])