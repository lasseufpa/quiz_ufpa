"""Regras do jogo: pontuação, avanço de perguntas, fase de leitura e fim de partida.

As funções recebem `game_state` e `quiz_data` explicitamente (o estado é mutado
in-place) e usam `emit`/`request` dos local-proxies do Flask-SocketIO, portanto
devem ser chamadas de dentro de um handler de socket.
"""

import csv
import logging
import os
import time
from datetime import datetime

import numpy as np
from flask import request
from flask_socketio import emit

from routines import logger  # noqa: F401  (configura o console + arquivo)
from routines import chart
from routines import classes
from routines import constants
from routines import game_state_handler as game_handler

log = logging.getLogger(__name__)


def _safe_filename(text):
    """Deixa um texto seguro para usar como parte do nome de arquivo."""
    safe = "".join(c if c.isalnum() or c in '.-_' else '_' for c in text or '')
    return safe.strip('_') or 'sem_nome'


# -------------------- Exportação de resultados --------------------
def export_scores_to_csv(scores, competition_scores, players, quiz_data=None,
                         class_name=None):
    """
    Exporta os resultados do quiz para um arquivo CSV local.
    Inclui colunas: Jogador, Pontuação (Avaliação), Pontuação (Competição).
    O nome do arquivo leva a turma e o quiz, para não misturar resultados.
    """
    quiz_title = "unknown_quiz"
    if quiz_data and 'title' in quiz_data:
        quiz_title = _safe_filename(quiz_data['title'])

    date_str = datetime.now().strftime("%Y%m%d")
    if class_name:
        base_filename = f"scores_{_safe_filename(class_name)}_{quiz_title}_{date_str}.csv"
    else:
        base_filename = f"scores_{quiz_title}_{date_str}.csv"
    filepath = os.path.join(constants.SCORES_FOLDER, base_filename)
    os.makedirs(constants.SCORES_FOLDER, exist_ok=True)

    if os.path.exists(filepath):
        index = 2
        while True:
            name, ext = os.path.splitext(base_filename)
            new_name = f"{name}_{index}{ext}"
            new_path = os.path.join(constants.SCORES_FOLDER, new_name)
            if not os.path.exists(new_path):
                filepath = new_path
                break
            index += 1

    with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Jogador', 'Pontuação (Avaliação)', 'Pontuação (Competição)'])
        for sid, player_name in players.items():
            writer.writerow([
                player_name,
                scores.get(sid, 0),
                competition_scores.get(sid, 0)
            ])

    log.info(f"✅ Resultados exportados para {filepath}")


# -------------------- Estado da partida --------------------
def reset_game_state(game_state):
    """Reseta o estado EM MEMÓRIA in-place (preserva a referência do dict)."""
    game_state.clear()
    game_state.update(game_handler.clear_game_state())
    game_state['state'] = constants.STATE_GAMEOVER

    if os.path.exists(constants.GAME_SAVE_FILE):
        os.remove(constants.GAME_SAVE_FILE)
        log.info("Saved game file deleted by host.")


def _build_leaderboard(game_state):
    """Placar ordenado por pontos de competição (decrescente)."""
    leaderboard = [
        {'nickname': nickname, 'score': game_state['competition_scores'].get(sid, 0)}
        for sid, nickname in game_state['players'].items()
    ]
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return leaderboard


def finish_game(game_state, quiz_data):
    """Encerra o quiz: exporta o CSV, anuncia o placar e reseta o estado."""
    log.info("Fim do quiz.")
    leaderboard = _build_leaderboard(game_state)
    export_scores_to_csv(
        game_state['scores'],
        game_state['competition_scores'],
        game_state['players'],
        quiz_data,
        classes.name_of(game_state.get('class_slug')) or None,
    )
    emit('game_over', leaderboard, broadcast=True)
    reset_game_state(game_state)


# -------------------- Fase de leitura --------------------
def reading_timer(socketio, game_state, quiz_data):
    """Agenda a liberação das respostas após READING_DURATION segundos."""
    log.debug("called reading_timer()")
    token = game_state.get('question_token', 0)
    socketio.start_background_task(
        _timeout_reading_timer, socketio, game_state, quiz_data, token
    )


def _timeout_reading_timer(socketio, game_state, quiz_data, token):
    socketio.sleep(constants.READING_DURATION)

    # Ignora o timer se a pergunta já mudou ou se os resultados já apareceram.
    if (game_state.get('question_token', 0) != token
            or game_state['state'] != constants.STATE_QUESTION):
        log.debug("Timer de leitura descartado (pergunta já mudou).")
        return

    game_state['question_start_time'] = time.time()

    game_handler.save_full_state(game_state, quiz_data)

    current_host = game_state.get('host_sid')
    log.debug("Timeout")
    if current_host:
        socketio.emit('answer_allowed')


# -------------------- Fluxo de perguntas --------------------
def advance_question(socketio, game_state, quiz_data):
    """Avança para a próxima pergunta (ou encerra o quiz, se acabaram)."""
    # Bloqueia só durante a pergunta: evita pular questões com clique duplo,
    # mas permite iniciar do lobby (ou de um jogo já encerrado).
    if game_state['state'] == constants.STATE_QUESTION:
        log.warning("advance_question ignorado: a pergunta atual ainda está aberta")
        return

    game_state['answers'] = {}
    game_state['answers_time'] = {}          # reset for new question
    game_state['current_question'] += 1
    game_state['state'] = constants.STATE_QUESTION
    game_state['question_start_time'] = None
    game_state['question_token'] = game_state.get('question_token', 0) + 1
    q_index = game_state['current_question']

    if q_index >= len(quiz_data['questions']):
        finish_game(game_state, quiz_data)
        return

    question_data = quiz_data['questions'][q_index]
    figure = question_data['figure']
    chart_path = ""
    if figure != "none":
        chart_path = f"{constants.UPLOAD_FOLDER}/{figure}"
    payload = {
        'text': question_data['text'],
        'options': question_data['options'],
        'question_index': q_index,
        'total_questions': len(quiz_data['questions']),
        'chart_path': chart_path
    }

    emit('show_question', payload, broadcast=True)
    if game_state['host_sid']:
        emit('update_answer_count', {
            'answered': 0,
            'total': game_handler.online_count(game_state)
        }, to=game_state['host_sid'])
    reading_timer(socketio, game_state, quiz_data)
    game_handler.save_full_state(game_state, quiz_data)


# -------------------- Respostas --------------------
def submit_answer(game_state, quiz_data, data):
    """Registra a resposta de um jogador e o tempo gasto."""
    if request.sid not in game_state['players']:
        return
    if game_state['state'] != constants.STATE_QUESTION:
        return
    if request.sid in game_state['answers']:
        emit('answer_received', to=request.sid)
        return

    option_index = data.get('option_index')
    game_state['answers'][request.sid] = option_index

    # Tempo de resposta (None = respostas ainda não liberadas)
    if game_state['question_start_time'] is not None:
        elapsed = time.time() - game_state['question_start_time']
        game_state['answers_time'][request.sid] = elapsed
    else:
        game_state['answers_time'][request.sid] = None

    log.info(f"Jogador {game_state['players'][request.sid]} respondeu: {option_index} em {game_state['answers_time'][request.sid]}s")
    emit('answer_received', to=request.sid)
    if game_state['host_sid']:
        emit('update_answer_count', {
            'answered': len(game_state['answers']),
            'total': game_handler.online_count(game_state)
        }, to=game_state['host_sid'])
    # force=False: grava no máximo 1x por segundo (evita N escritas por pergunta)
    game_handler.save_full_state(game_state, quiz_data, force=False)


# -------------------- Pontuação --------------------
def _sinc(t):
    """Sinc com epsilon, para evitar divisão por zero em t = 0."""
    return np.sin(np.pi * t + 1e-5) / (np.pi * t + 1e-5)


def _score_answers(game_state, correct_option_index):
    """
    Atualiza as duas pontuações:
      - Avaliação: 1 ponto por resposta correta.
      - Competição: bônus por rapidez, int(200 * sinc(t/60)**4), máx. 200.
    Retorna {nickname: pontos de competição desta questão}.
    """
    # Avaliação
    for sid, answer in game_state['answers'].items():
        try:
            if int(answer) == int(correct_option_index):
                game_state['scores'][sid] = game_state['scores'].get(sid, 0) + 1
        except Exception:
            pass

    # Competição
    question_competition_points = {}
    for sid, answer in game_state['answers'].items():
        try:
            if int(answer) == int(correct_option_index):
                t = game_state['answers_time'].get(sid)
                if t is not None and t >= 0:
                    comp_points = int(200 * _sinc(t / 60) ** 4)
                else:
                    comp_points = 0
                game_state['competition_scores'][sid] = (
                    game_state['competition_scores'].get(sid, 0) + comp_points
                )
                question_competition_points[game_state['players'][sid]] = comp_points
        except Exception:
            pass

    return question_competition_points


def show_results(game_state, quiz_data):
    """Calcula as pontuações, gera o gráfico (distribuição + pódio) e revela os resultados."""
    if request.sid != game_state['host_sid']:
        return
    # Idempotência: clique duplo não pode somar a pontuação duas vezes
    if game_state['state'] != constants.STATE_QUESTION:
        log.warning("show_results ignorado no estado %s", game_state['state'])
        return
    q_index = game_state['current_question']
    if q_index < 0 or q_index >= len(quiz_data['questions']):
        return
    question_data = quiz_data['questions'][q_index]
    correct_option_index = question_data['correct_option']
    correct_option_text = question_data['options'][correct_option_index]

    answer_distribution = [0] * len(question_data['options'])
    for ans in game_state['answers'].values():
        try:
            answer_distribution[int(ans)] += 1
        except (ValueError, TypeError, IndexError):
            pass

    question_competition_points = _score_answers(game_state, correct_option_index)

    # Top 3 desta questão (pódio do gráfico)
    top3 = sorted(question_competition_points.items(), key=lambda x: x[1], reverse=True)[:3]

    combined_chart_path = chart.save_combined_results_chart(
        answer_distribution, question_data, q_index, top3
    )

    payload = {
        'correct_option': correct_option_index,
        'correct_option_text': chr(ord('A') + correct_option_index) + ') ' + correct_option_text,
        'scores': game_state['scores'],
        'players': game_state['players'],
        'answer_distribution': answer_distribution,
        'chart_path': combined_chart_path,
    }
    emit('show_results', payload, broadcast=True)
    log.info("Mostrando resultados com gráfico combinado.")
    game_state['state'] = constants.STATE_ANSWER
    # Invalida o timer de leitura pendente, se ainda houver
    game_state['question_token'] = game_state.get('question_token', 0) + 1
    game_handler.save_full_state(game_state, quiz_data)


def force_end_quiz(game_state, quiz_data):
    """Encerra o quiz antecipadamente, a pedido do host."""
    if request.sid != game_state['host_sid']:
        return
    if game_state['state'] == constants.STATE_GAMEOVER:
        return
    log.info("Quiz finalizado forçadamente pelo host")
    finish_game(game_state, quiz_data)
