"""Eventos de conexão: entrada de jogadores, reconexão e desconexão."""

import logging
import os
import secrets
import time

from flask import request
from flask_socketio import emit, join_room

from routines import classes, constants, json_store, persistence, room
from routines import game_logic
from routines import game_state_handler as game_handler
from routines import runtime
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)


def _generate_session_token():
    """Gera um token único para a sessão do jogador."""
    return secrets.token_hex(16)


def on_connect():
    log.info(f"Cliente conectado: {request.sid}")
    # Informa se a sala está aberta e de qual turma (o aluno não escolhe turma)
    emit('room_info', room.payload(), to=request.sid)


def on_disconnect():
    game_state = runtime.game_state
    log.info(f"Cliente desconectado: {request.sid}")

    if request.sid == game_state['host_sid']:
        log.warning("!!! O ANFITRIÃO DESCONECTOU. Salvando estado e pausando o jogo. !!!")
        persistence.save_full_state(game_state, runtime.quiz_data)
        game_state['host_sid'] = None
        emit('host_disconnected', {
            'message': 'O apresentador desconectou. Aguarde a reconexão para retomar o jogo.'
        }, broadcast=True)

    elif request.sid in game_state['players']:
        nickname = game_state['players'].get(request.sid, '??')
        # Marca como offline, mas mantém pontos/respostas para quando voltar
        game_state.setdefault('connected', {})[request.sid] = False
        persistence.save_full_state(game_state, runtime.quiz_data)

        if game_state['host_sid']:
            emit('player_left', {'nickname': nickname}, to=game_state['host_sid'])
            emit('update_answer_count', {
                'answered': len(game_state['answers']),
                'total': game_handler.online_count(game_state)
            }, to=game_state['host_sid'])

        log.info(f"Jogador {nickname} desconectou (segue no jogo como offline).")


def on_host_join():
    from routines import connections

    connections.connect_host(runtime.game_state, runtime.quiz_data)


def on_restore_session(data):
    """Restaura a sessão de um jogador após recarregar a página."""
    game_state = runtime.game_state
    token = data.get('token')
    new_sid = data.get('new_sid')

    if token in game_state['PLAYER_SESSIONS']:
        session_data = game_state['PLAYER_SESSIONS'][token]
        old_sid = session_data['sid']
        nickname = session_data['nickname']

        log.debug('verificando reconexão')
        if old_sid in game_state['players']:
            # Atualiza o SID para o novo
            game_state['players'][new_sid] = game_state['players'].pop(old_sid)
            game_state['scores'][new_sid] = game_state['scores'].pop(old_sid, 0)
            game_state['competition_scores'][new_sid] = game_state['competition_scores'].pop(old_sid, 0)

            # Se tinha uma resposta, transfere também
            if old_sid in game_state['answers']:
                game_state['answers'][new_sid] = game_state['answers'].pop(old_sid)

            # Se tinha tempo, transfere também
            if old_sid in game_state['answers_time']:
                game_state['answers_time'][new_sid] = game_state['answers_time'].pop(old_sid)

            # Marca o novo SID como online (o antigo deixa de existir)
            game_state.setdefault('connected', {}).pop(old_sid, None)
            game_state['connected'][new_sid] = True

            # Leva o time junto (modo time)
            if old_sid in game_state.get('teams', {}):
                game_state['teams'][new_sid] = game_state['teams'].pop(old_sid)

            # Atualiza o token com o novo SID
            game_state['PLAYER_SESSIONS'][token]['sid'] = new_sid

            allow_answer = False
            if game_state['question_start_time'] is not None:
                elapsed_time = time.time() - game_state['question_start_time']
                duration = (game_state.get('answer_duration')
                            or constants.QUESTION_DURATION)
                if elapsed_time < duration:
                    allow_answer = True

            # Volta para a sala da partida: só quem está nela recebe
            # perguntas/resultados.
            join_room(constants.GAME_ROOM, sid=new_sid)

            player_team = game_state.get('teams', {}).get(new_sid)

            emit('session_restored', {
                'nickname': nickname,
                'current_question': game_state['current_question'],
                'current_score': game_state['scores'].get(new_sid, 0),
                'options': [0, 1, 2, 3],
                'state': game_state['state'],
                'allow_answer': allow_answer,
                'team': player_team,
                'team_name': constants.TEAM_NAMES.get(player_team),
            }, to=new_sid)

            # Atualiza o host (lista e contagem)
            if game_state['host_sid']:
                emit('update_player_list', game_handler.players_payload(game_state),
                     to=game_state['host_sid'])
                emit('update_answer_count', {
                    'answered': len(game_state['answers']),
                    'total': game_handler.online_count(game_state)
                }, to=game_state['host_sid'])

            persistence.save_full_state(game_state, runtime.quiz_data)
            log.info(f"Sessão restaurada para {nickname}. Novo SID: {new_sid}")
            return

    emit('session_restore_failed', {'reason': 'Sessão não encontrada ou expirada'}, to=new_sid)


def on_player_join(data):
    """Um aluno tentou entrar no jogo."""
    game_state = runtime.game_state
    nickname = data.get('nickname', '').strip()

    if not nickname:
        return

    # A turma vem da sala aberta pelo apresentador (não do jogador)
    class_slug = room.current_class()
    if not class_slug or not classes.exists(class_slug):
        emit('join_failed', {
            'reason': 'O professor ainda não abriu a sala. Aguarde um instante e tente de novo.'
        }, to=request.sid)
        log.warning(f"Falha no login: sala fechada ('{nickname}' tentou entrar).")
        return

    # --- Validação case-insensitive contra a lista de alunos da turma ---
    canonical_name = classes.find_student(class_slug, nickname)

    if canonical_name is None:
        emit('join_failed', {
            'reason': f'Não cadastrado na turma "{classes.name_of(class_slug)}". '
                      f'Fale com o professor.'
        }, to=request.sid)
        log.warning(f"Falha no login: '{nickname}' não está na turma {class_slug}.")
        return

    # --- Modo time: o aluno precisa dizer em qual time vai competir ---
    team = None
    if game_state.get('team_mode'):
        team = game_logic.normalize_team(data.get('team'))
        if team is None:
            emit('join_failed', {
                'reason': 'Escolha o seu time (Time A ou Time B) antes de entrar.'
            }, to=request.sid)
            log.warning(f"Falha no login: '{nickname}' não escolheu o time.")
            return

    # Já existe alguém com esse nome?
    existing_sid = next(
        (sid for sid, name in game_state['players'].items() if name == canonical_name),
        None,
    )
    if existing_sid is not None:
        if game_handler.is_connected(game_state, existing_sid):
            emit('join_failed', {'reason': 'Este usuário já está no jogo.'}, to=request.sid)
            log.warning(f"Falha no login: Usuário '{canonical_name}' já está no jogo.")
            return

        # O jogador havia saído: reassume o lugar, mantendo pontos e respostas
        log.info(f"Jogador {canonical_name} reassumiu o lugar (estava offline).")
        game_state['players'][request.sid] = game_state['players'].pop(existing_sid)
        game_state['scores'][request.sid] = game_state['scores'].pop(existing_sid, 0)
        game_state['competition_scores'][request.sid] = game_state['competition_scores'].pop(existing_sid, 0)
        if existing_sid in game_state['answers']:
            game_state['answers'][request.sid] = game_state['answers'].pop(existing_sid)
        if existing_sid in game_state['answers_time']:
            game_state['answers_time'][request.sid] = game_state['answers_time'].pop(existing_sid)
        game_state.setdefault('connected', {}).pop(existing_sid, None)
        # Mantém o time do lugar reassumido (se o aluno não escolheu outro)
        previous_team = game_state.setdefault('teams', {}).pop(existing_sid, None)
        if previous_team and team is None:
            team = previous_team
        # Tokens antigos daquele SID deixam de valer
        for old_token in [t for t, s in game_state['PLAYER_SESSIONS'].items()
                          if s['sid'] == existing_sid]:
            del game_state['PLAYER_SESSIONS'][old_token]

    log.info(f"Jogador {canonical_name} (autorizado) entrou.")
    game_state['players'][request.sid] = canonical_name
    game_state['scores'].setdefault(request.sid, 0)
    game_state['competition_scores'].setdefault(request.sid, 0)
    game_state.setdefault('connected', {})[request.sid] = True

    # Registra o time do jogador (apenas no modo time)
    if team is not None:
        game_state.setdefault('teams', {})[request.sid] = team
    else:
        game_state.setdefault('teams', {}).pop(request.sid, None)

    # Cria token de sessão para permitir reconexão
    session_token = _generate_session_token()
    game_state['PLAYER_SESSIONS'][session_token] = {
        'sid': request.sid,
        'nickname': canonical_name,
    }

    if game_state['host_sid']:
        emit('update_player_list', game_handler.players_payload(game_state),
             to=game_state['host_sid'])
        emit('update_answer_count', {
            'answered': len(game_state['answers']),
            'total': game_handler.online_count(game_state)
        }, to=game_state['host_sid'])

    # Entra na sala da partida: a partir daqui (e só a partir daqui) o aluno
    # recebe pergunta, resultados e liberação de respostas.
    join_room(constants.GAME_ROOM)

    emit('join_success', {
        'nickname': canonical_name,
        'session_token': session_token,
        # Em que fase está o jogo agora (o aluno pode ter entrado no meio)
        'state': game_state['state'],
        'current_question': game_state['current_question'],
        'players': len(game_state['players']),
        'team': team,
        'team_name': constants.TEAM_NAMES.get(team),
    }, to=request.sid)
    persistence.save_full_state(game_state, runtime.quiz_data)


def on_clear_saved_game():
    """Host apaga o estado salvo e reinicia a partida."""
    game_state = runtime.game_state
    if request.sid != game_state['host_sid']:
        return

    if os.path.exists(constants.GAME_SAVE_FILE):
        json_store.delete_json(constants.GAME_SAVE_FILE)
        log.info("Saved game file deleted by host.")

    game_state.clear()
    game_state.update(game_handler.clear_game_state())
    runtime.quiz_data = None

    emit('game_reset', broadcast=True)
    emit('admin_error', {'message': 'Jogo foi resetado completamente.'}, to=request.sid)


def register(socketio):
    """Registra os eventos de conexão no SocketIO."""
    socketio.on('connect')(on_connect)
    socketio.on('disconnect')(on_disconnect)
    socketio.on('host_join')(on_host_join)
    socketio.on('restore_session')(on_restore_session)
    socketio.on('player_join')(on_player_join)
    socketio.on('clear_saved_game')(on_clear_saved_game)
