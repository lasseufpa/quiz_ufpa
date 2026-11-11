"""Regras do jogo: pontuação, avanço de perguntas, fase de leitura e fim de partida.

As funções recebem `game_state` e `quiz_data` explicitamente (o estado é mutado
in-place) e usam `emit`/`request` dos local-proxies do Flask-SocketIO, portanto
devem ser chamadas de dentro de um handler de socket.
"""

import csv
import logging
import math
import os
import re
import time
from datetime import datetime

import numpy as np
from flask import request
from flask_socketio import emit

from routines import logger  # noqa: F401  (configura o console + arquivo)
from routines import chart
from routines import classes
from routines import constants
from routines import json_store
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
        json_store.delete_json(constants.GAME_SAVE_FILE)
        log.info("Saved game file deleted by host.")


def _build_leaderboard(game_state):
    """Placar ordenado por pontos de competição (decrescente)."""
    leaderboard = [
        {'nickname': nickname, 'score': game_state['competition_scores'].get(sid, 0)}
        for sid, nickname in game_state['players'].items()
    ]
    leaderboard.sort(key=lambda x: x['score'], reverse=True)
    return leaderboard


# -------------------- Modo time --------------------
def normalize_team(value):
    """Converte o que veio do cliente ('A', 'Time A', 'TIME B'…) em 'A'/'B'."""
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text:
        return None
    if text in constants.TEAM_KEYS:
        return text
    for key, name in constants.TEAM_NAMES.items():
        if text == name.upper() or text.endswith(' ' + key):
            return key
    last = text[-1]
    return last if last in constants.TEAM_KEYS else None


def _team_members(game_state, key):
    """Jogadores de um time, do maior para o menor placar de competição."""
    teams = game_state.get('teams', {}) or {}
    scores = game_state.get('competition_scores', {}) or {}
    players = game_state.get('players', {}) or {}
    members = [
        {'nickname': nickname, 'score': scores.get(sid, 0)}
        for sid, nickname in players.items() if teams.get(sid) == key
    ]
    members.sort(key=lambda member: member['score'], reverse=True)
    return members


def build_team_standings(game_state):
    """Placar por time, do que está ganhando para o que está perdendo.

    A pontuação de cada time é a soma dos pontos de competição dos seus
    jogadores (os mesmos que formavam o pódio). Cada time leva até
    `TEAM_TOP_N` jogadores em `top` para aparecer nos resultados.
    """
    standings = []
    for key in constants.TEAM_KEYS:
        members = _team_members(game_state, key)
        standings.append({
            'key': key,
            'name': constants.TEAM_NAMES.get(key, key),
            'score': sum(member['score'] for member in members),
            'count': len(members),
            'top': members[:constants.TEAM_TOP_N],
        })

    standings.sort(key=lambda team: team['score'], reverse=True)
    best = standings[0]['score'] if standings else 0
    tied = [team for team in standings if team['score'] == best]

    for index, team in enumerate(standings):
        team['position'] = index + 1
        team['tied'] = len(tied) > 1
        team['winning'] = team['score'] == best
    return standings


def finish_game(game_state, quiz_data):
    """Encerra o quiz: exporta o CSV, anuncia o placar e MANTÉM o estado final.

    O estado não é limpo de propósito: enquanto o professor estiver na tela de
    fim de quiz, host e alunos podem recarregar a página (F5) e voltam para o
    mesmo lugar. A partida só é zerada quando o professor clica em "Jogar
    novamente" (`reset_for_new_match`).
    """
    log.info("Fim do quiz.")
    leaderboard = _build_leaderboard(game_state)
    export_scores_to_csv(
        game_state['scores'],
        game_state['competition_scores'],
        game_state['players'],
        quiz_data,
        classes.name_of(game_state.get('class_slug')) or None,
    )

    team_mode = bool(game_state.get('team_mode'))
    team_standings = build_team_standings(game_state) if team_mode else []

    game_state['state'] = constants.STATE_GAMEOVER
    game_state['final_leaderboard'] = leaderboard
    game_state['final_teams'] = team_standings
    game_state['question_start_time'] = None
    game_state['answers'] = {}
    game_state['answers_time'] = {}
    game_handler.save_full_state(game_state, quiz_data)

    emit('game_over', {
        'leaderboard': leaderboard,
        'teams': team_standings,
        'team_mode': team_mode,
    }, to=constants.GAME_ROOM)


def reset_for_new_match(game_state, quiz_data):
    """Zera a partida mantendo os alunos na sala (botão "Jogar novamente").

    Diferente de `reset_game_state`, não apaga jogadores nem a turma: todos
    continuam no contexto do apresentador e basta clicar em "Iniciar Jogo".
    """
    game_state['current_question'] = -1
    game_state['answers'] = {}
    game_state['answers_time'] = {}
    game_state['scores'] = {sid: 0 for sid in game_state['players']}
    game_state['competition_scores'] = {sid: 0 for sid in game_state['players']}
    game_state['state'] = constants.STATE_LOBBY
    game_state['final_leaderboard'] = []
    game_state['final_teams'] = []
    game_state['last_results'] = None
    game_state['history'] = []
    game_state['question_start_time'] = None
    game_state['reading_duration'] = None
    game_state['reading_started_at'] = None
    game_state['answer_duration'] = None
    game_state['question_token'] = game_state.get('question_token', 0) + 1
    game_handler.save_full_state(game_state, quiz_data)
    log.info("Partida zerada para um novo jogo (alunos mantidos na sala).")


# -------------------- Fase de leitura --------------------
_MATH_MARKUP = re.compile(r'\\[a-zA-Z]+|[{}$\\]')


def visible_length(text):
    """Nº de caracteres "legíveis" do enunciado (ignora o markup de LaTeX).

    Assim uma fórmula como `$\\dfrac{\\Delta}{2}$` não inflaciona o tempo de
    leitura: contam-se apenas os caracteres que o aluno realmente lê.
    """
    if not text:
        return 0
    return len(_MATH_MARKUP.sub('', text).strip())


def answer_seconds_for(question):
    """Tempo (s) para o aluno escolher uma alternativa.

    Prioridade:
      1. `answer_time` definido na pergunta (0 = encerra na hora);
      2. cálculo automático pelo tamanho das ALTERNATIVAS — com piso
         (ANSWER_MIN_DURATION) e teto (ANSWER_MAX_DURATION). Alternativas
         longas dão mais tempo; alternativas curtas ainda precisam de tempo
         para o aluno resolver a conta.
    """
    if not isinstance(question, dict):
        return constants.QUESTION_DURATION

    explicit = question.get('answer_time')
    if explicit is not None and explicit != '':
        try:
            value = int(round(float(explicit)))
            return max(0, min(value, constants.ANSWER_MAX_EXPLICIT))
        except (TypeError, ValueError):
            log.warning(
                f"answer_time inválido ({explicit!r}); usando o cálculo automático."
            )

    chars = sum(visible_length(opt) for opt in (question.get('options') or []))
    if chars <= 0:
        return constants.QUESTION_DURATION

    seconds = int(math.ceil(chars / constants.ANSWER_CHARS_PER_SECOND))
    return max(constants.ANSWER_MIN_DURATION,
               min(seconds, constants.ANSWER_MAX_DURATION))


def reading_seconds_for(question):
    """Tempo (s) entre exibir a pergunta e liberar as respostas.

    Prioridade:
      1. `reading_time` definido na pergunta (0 = libera as respostas na hora);
      2. cálculo automático pelo tamanho do enunciado — comportamento legado de
         ~15 caracteres por segundo, limitado entre READING_MIN_DURATION e
         READING_MAX_DURATION.
    """
    if not isinstance(question, dict):
        return constants.READING_DURATION

    explicit = question.get('reading_time')
    if explicit is not None and explicit != '':
        try:
            value = int(round(float(explicit)))
            return max(0, min(value, constants.READING_MAX_EXPLICIT))
        except (TypeError, ValueError):
            log.warning(
                f"reading_time inválido ({explicit!r}); usando o cálculo automático."
            )

    chars = visible_length(question.get('text', ''))
    if chars <= 0:
        return constants.READING_DURATION

    seconds = round(chars / constants.READING_CHARS_PER_SECOND)
    return max(constants.READING_MIN_DURATION,
               min(constants.READING_MAX_DURATION, seconds))


def reading_timer(socketio, game_state, quiz_data, seconds=None):
    """Agenda a liberação das respostas após o tempo de leitura da pergunta."""
    log.debug("called reading_timer()")
    token = game_state.get('question_token', 0)
    if seconds is None:
        question = quiz_data['questions'][game_state['current_question']]
        seconds = reading_seconds_for(question)

    game_state['reading_duration'] = seconds
    game_state['reading_started_at'] = time.time()

    socketio.start_background_task(
        _timeout_reading_timer, socketio, game_state, quiz_data, token, seconds
    )


def _timeout_reading_timer(socketio, game_state, quiz_data, token, seconds):
    if seconds > 0:
        socketio.sleep(seconds)

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
        socketio.emit('answer_allowed', to=constants.GAME_ROOM)


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
    game_state['reading_duration'] = None
    game_state['reading_started_at'] = None
    game_state['answer_duration'] = None
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
    reading_seconds = reading_seconds_for(question_data)
    answer_seconds = answer_seconds_for(question_data)
    game_state['answer_duration'] = answer_seconds
    payload = {
        'text': question_data['text'],
        'options': question_data['options'],
        'question_index': q_index,
        'total_questions': len(quiz_data['questions']),
        'chart_path': chart_path,
        'reading_time': reading_seconds,
        'answer_time': answer_seconds,
    }

    emit('show_question', payload, to=constants.GAME_ROOM)
    if game_state['host_sid']:
        emit('update_answer_count', {
            'answered': 0,
            'total': game_handler.online_count(game_state)
        }, to=game_state['host_sid'])
    reading_timer(socketio, game_state, quiz_data, reading_seconds)
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
      - Competição: bônus por rapidez, até COMPETITION_MAX_POINTS, que zera em
        COMPETITION_HALF_WINDOW segundos (a curva está em routines/figures.py).
    Retorna {sid: pontos de competição desta questão}.
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
                    comp_points = int(
                        constants.COMPETITION_MAX_POINTS
                        * _sinc(t / constants.COMPETITION_HALF_WINDOW)
                        ** constants.COMPETITION_EXPONENT
                    )
                else:
                    comp_points = 0
                game_state['competition_scores'][sid] = (
                    game_state['competition_scores'].get(sid, 0) + comp_points
                )
                question_competition_points[sid] = comp_points
        except Exception:
            pass

    return question_competition_points


def _podium(question_competition_points, game_state):
    """Top 3 da pergunta (nickname, pontos) para o card do apresentador."""
    players = game_state.get('players', {})
    itens = [
        (players.get(sid, '?'), pts)
        for sid, pts in question_competition_points.items()
    ]
    itens.sort(key=lambda item: item[1], reverse=True)
    return itens[:3]


# -------------------- Histórico do aluno --------------------
def _record_history_entry(game_state, correct_option_index, points_by_sid):
    """Guarda o resultado desta pergunta para cada aluno (tabela do celular)."""
    answers = game_state.get('answers') or {}
    entry = {
        'index': game_state.get('current_question', -1),
        'players': {},
    }
    for sid in game_state.get('players', {}):
        answer = answers.get(sid)
        try:
            correct = answer is not None and int(answer) == int(correct_option_index)
        except (TypeError, ValueError):
            correct = False
        entry['players'][sid] = {
            'answered': answer is not None,
            'correct': correct,
            'points': int(points_by_sid.get(sid, 0)),
        }

    game_state.setdefault('history', []).append(entry)
    return entry


def player_score_history(game_state, sid):
    """Linhas da tabela de pontuação de um aluno (mais recente primeiro).

    Cada linha: {'question_index', 'answered', 'correct', 'points'}.
    Inclui também os totais acumulados (pontos de competição e acertos).
    """
    rows = []
    for entry in game_state.get('history') or []:
        info = (entry.get('players') or {}).get(sid)
        if not info:
            continue
        rows.append({
            'question_index': entry.get('index', -1),
            'answered': bool(info.get('answered')),
            'correct': bool(info.get('correct')),
            'points': int(info.get('points', 0)),
        })

    # Mais recente no topo, primeira pergunta na última linha
    rows.sort(key=lambda row: row['question_index'], reverse=True)

    return {
        'rows': rows,
        'total_points': int(game_state['competition_scores'].get(sid, 0)),
        'total_correct': int(game_state['scores'].get(sid, 0)),
        'total_questions': int(game_state.get('total_questions') or 0),
    }


def emit_player_score_history(game_state, sid):
    """Envia a tabela de pontuação só para um aluno (evento personalizado)."""
    emit('score_history', player_score_history(game_state, sid), to=sid)


def remap_player_history(game_state, old_sid, new_sid):
    """Move o histórico do aluno para o novo SID (reconexão/reassumir lugar)."""
    for entry in game_state.get('history') or []:
        players = entry.get('players') or {}
        if old_sid in players:
            players[new_sid] = players.pop(old_sid)


def build_results_payload(game_state, quiz_data, podium=None):
    """Dados da tela de resultados de uma pergunta (sem desenhar nada).

    O apresentador monta o gráfico no próprio navegador; a imagem (PNG) só é
    gerada quando alguém pede para exportar (`export_results_image`).
    """
    q_index = game_state.get('current_question', -1)
    if q_index < 0 or q_index >= len(quiz_data['questions']):
        return None

    question_data = quiz_data['questions'][q_index]
    options = question_data.get('options') or []
    correct_option_index = int(question_data.get('correct_option', 0))

    answer_distribution = [0] * len(options)
    for ans in (game_state.get('answers') or {}).values():
        try:
            answer_distribution[int(ans)] += 1
        except (ValueError, TypeError, IndexError):
            pass

    correct_text = options[correct_option_index] if correct_option_index < len(options) else ''
    team_mode = bool(game_state.get('team_mode'))

    return {
        'question_index': q_index,
        'total_questions': len(quiz_data['questions']),
        'question_text': question_data.get('text', ''),
        'options': options,
        'correct_option': correct_option_index,
        'correct_option_text': chr(ord('A') + correct_option_index) + ') ' + correct_text,
        'explanation': (question_data.get('explanation') or '').strip(),
        'answer_distribution': answer_distribution,
        'answers_total': sum(answer_distribution),
        'players_online': game_handler.online_count(game_state),
        'scores': game_state['scores'],
        'players': game_state['players'],
        'podium': [
            {'nickname': nickname, 'score': score}
            for nickname, score in (podium or [])
        ],
        'team_mode': team_mode,
        'teams': build_team_standings(game_state) if team_mode else [],
    }


def show_results(game_state, quiz_data):
    """Calcula as pontuações e revela os resultados (renderizados no cliente)."""
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
    correct_index = int(question_data['correct_option'])

    points_by_sid = _score_answers(game_state, correct_index)

    # Top 3 desta questão (pódio mostrado pelo apresentador)
    top3 = _podium(points_by_sid, game_state)

    # Guarda o resultado da pergunta para a tabela do celular de cada aluno
    _record_history_entry(game_state, correct_index, points_by_sid)

    payload = build_results_payload(game_state, quiz_data, podium=top3)
    if payload is None:
        return

    # Guarda para o F5 (o apresentador volta na mesma tela) e para a exportação
    game_state['last_results'] = payload

    emit('show_results', payload, to=constants.GAME_ROOM)

    # Tabela de pontuação de cada aluno (personalizada, com o total acumulado)
    for sid in list(game_state['players'].keys()):
        emit_player_score_history(game_state, sid)

    log.info("Mostrando resultados da pergunta %d.", q_index + 1)
    game_state['state'] = constants.STATE_ANSWER
    # Invalida o timer de leitura pendente, se ainda houver
    game_state['question_token'] = game_state.get('question_token', 0) + 1
    game_handler.save_full_state(game_state, quiz_data)


def export_results_image(game_state, quiz_data):
    """Gera o PNG dos resultados (mesmo desenho usado antes na tela).

    Chamado apenas quando o apresentador clica em "Baixar imagem": a partida
    não fica esperando o matplotlib.
    """
    if request.sid != game_state['host_sid']:
        return
    payload = game_state.get('last_results') or build_results_payload(game_state, quiz_data)
    if not payload:
        emit('admin_error', {'message': 'Não há resultados para exportar agora.'},
             to=request.sid)
        return

    q_index = payload['question_index']
    question_data = quiz_data['questions'][q_index]
    podium = [(item['nickname'], item['score']) for item in payload.get('podium') or []]

    try:
        path = chart.save_combined_results_chart(
            payload['answer_distribution'], question_data, q_index, podium,
            team_standings=payload.get('teams') or None,
        )
    except Exception as e:  # não derruba a partida por causa de um gráfico
        log.error("Falha ao gerar a imagem dos resultados: %s", e)
        emit('admin_error', {'message': 'Não foi possível gerar a imagem dos resultados.'},
             to=request.sid)
        return

    emit('results_image_ready', {
        'path': path,
        'filename': f"resultados_pergunta_{q_index + 1}.png",
    }, to=request.sid)
    log.info("Imagem dos resultados exportada: %s", path)


def force_end_quiz(game_state, quiz_data):
    """Encerra o quiz antecipadamente, a pedido do host."""
    if request.sid != game_state['host_sid']:
        return
    if game_state['state'] == constants.STATE_GAMEOVER:
        return
    log.info("Quiz finalizado forçadamente pelo host")
    finish_game(game_state, quiz_data)
