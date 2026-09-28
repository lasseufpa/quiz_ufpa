from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import time
import os

from routines import constants
from routines import game_state_handler as game_handler
from routines import chart

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
        print(f"Anfitrião {old_host_sid} foi substituído por {request.sid}")

    # Set the new host
    game_state['host_sid'] = request.sid
    print(f"Anfitrião conectado/substituído: {request.sid}")

    # --- Act like a page refresh: send current state to the new host ---
    # 1. Send current player list (may be empty)
    emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])


    elapsed_time = None

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
            'total_players': len(game_state['players']),
            'answered_count': len(game_state['answers']),
            'remaining_time' : constants.QUESTION_DURATION - elapsed_time 
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
                'remaining_time' : constants.QUESTION_DURATION - elapsed_time
            }
            emit('show_question', payload, to=game_state['host_sid'])  # only to host (others already have it)
            # Also optionally broadcast the answer count to the new host
            emit('update_answer_count', {
                'answered': len(game_state['answers']),
                'total': len(game_state['players'])
            }, to=game_state['host_sid'])

        # If game is in ANSWER state, resend the results
        elif game_state['state'] == constants.STATE_ANSWER and game_state['current_question'] >= 0:
            q_index = game_state['current_question']
            question_data = QUIZ_DATA['questions'][q_index]
            correct_option_index = question_data['correct_option']
            correct_option_text = question_data['options'][correct_option_index]
            answer_distribution = [0] * len(question_data['options'])
            for ans in game_state['answers'].values():
                try:
                    answer_distribution[int(ans)] += 1
                except:
                    pass
            chart_path = f"static/graphs/q{q_index + 1}_results.png"
            if not os.path.exists(chart_path):
                chart_path = chart.save_answer_distribution_chart(answer_distribution, question_data, q_index)
            payload = {
                'correct_option': correct_option_index,
                'correct_option_text': chr(ord('A')+correct_option_index) + ') ' + correct_option_text,
                'scores': game_state['scores'],
                'players': game_state['players'],
                'answer_distribution': answer_distribution,
                'chart_path': chart_path
            }
            emit('show_results', payload, to=game_state['host_sid'])

    # Optional: broadcast to players that a new host is in control (if desired)
    if old_host_sid != request.sid:
        emit('host_changed', {'message': 'Um novo anfitrião assumiu o controle do jogo.'}, broadcast=True)

    # Require host authentication (separate from admin)
    if not session.get('host_logged_in'):
        emit('admin_error', {'message': 'Você precisa estar logado como anfitrião para controlar o jogo.'}, to=request.sid)
        return    # If there is already a host, ignore
    
    if game_state['host_sid'] is not None:
        emit('admin_error', {'message': 'Já existe um anfitrião conectado.'}, to=request.sid)
        return
    
    # Check if there is an existing game in progress (players present)
    if game_state['players']:
        # Resume existing game
        game_state['host_sid'] = request.sid
        print(f"Anfitrião reconectou e retomou o jogo: {request.sid}")
        
        # Notify host of current state
        emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])
        # Tell host the current question index and game state
        emit('resume_host_state', {
            'current_question': game_state['current_question'],
            'state': game_state['state'],
            'total_players': len(game_state['players']),
            'answered_count': len(game_state['answers'])
        }, to=game_state['host_sid'])
        
        # Broadcast to all players that host is back
        emit('host_reconnected', {'message': 'O apresentador reconectou. O jogo vai continuar.'}, broadcast=True)
        
        # If game was in QUESTION state, resend the current question to all players
        if game_state['state'] == constants.STATE_QUESTION and game_state['current_question'] >= 0 and QUIZ_DATA:
            q_index = game_state['current_question']
            question_data = QUIZ_DATA['questions'][q_index]
            figure = question_data['figure']
            chart_path = ""
            if figure != "none":
                chart_path = f"{constants.UPLOAD_FOLDER}/{figure}"
            payload = {
                'text': question_data['text'],
                'options': question_data['options'],
                'question_index': q_index,
                'total_questions': len(QUIZ_DATA['questions']),
                'chart_path': chart_path,
                'remaining_time': constants.QUESTION_DURATION - elapsed_time if elapsed_time is not None else None
            }
            emit('show_question', payload, broadcast=True)
        # If game was in ANSWER state, resend results
        elif game_state['state'] == constants.STATE_ANSWER and game_state['current_question'] >= 0 and QUIZ_DATA:
            q_index = game_state['current_question']
            question_data = QUIZ_DATA['questions'][q_index]
            correct_option_index = question_data['correct_option']
            correct_option_text = question_data['options'][correct_option_index]
            answer_distribution = [0] * len(question_data['options'])
            for ans in game_state['answers'].values():
                try:
                    answer_distribution[int(ans)] += 1
                except:
                    pass
            chart_path = f"static/graphs/q{q_index + 1}_results.png"
            if not os.path.exists(chart_path):
                chart_path = chart.save_answer_distribution_chart(answer_distribution, question_data, q_index)
            payload = {
                'correct_option': correct_option_index,
                'correct_option_text': chr(ord('A')+correct_option_index) + ') ' + correct_option_text,
                'scores': game_state['scores'],
                'players': game_state['players'],
                'answer_distribution': answer_distribution,
                'chart_path': chart_path
            }
            emit('show_results', payload, broadcast=True)
            emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])
    else:
        # No game in progress – fresh host join
        game_state['host_sid'] = request.sid
        print(f"Novo anfitrião se juntou: {request.sid}")
        emit('update_player_list', list(game_state['players'].values()), to=game_state['host_sid'])