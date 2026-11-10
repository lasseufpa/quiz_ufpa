from routines import  constants
import logging
import time

from routines import json_store
from routines import logger  # noqa: F401  (configura o console + arquivo)

log = logging.getLogger(__name__)

# Intervalo mínimo entre gravações "não forçadas" (respostas individuais).
SAVE_MIN_INTERVAL = 1.0
_last_save_at = 0.0


def clear_game_state():
    game_state = {
        'host_sid': None,
        'players': {},
        'current_question': -1,
        'answers': {},
        'scores': {},
        'competition_scores': {},
        'state': constants.STATE_LOBBY,
        'question_start_time': None,
        'answers_time': {},
        'reading_duration': None,   # segundos de leitura da pergunta atual
        'reading_started_at': None,  # quando a fase de leitura começou
        'answer_duration': None,    # segundos para responder a pergunta atual
        'final_leaderboard': [],    # placar da última partida (tela de fim)
        'connected': {},        # {sid: True/False} — jogador online/offline
        'question_token': 0,    # invalida timers de perguntas antigas
        'class_slug': None,     # turma da partida atual
        'quiz_name': None,      # quiz escolhido (para repetir a partida)
        'PLAYER_SESSIONS': {}
    }
    return game_state


def is_connected(game_state, sid):
    """Considera conectado quem não tem registro explícito (compatibilidade)."""
    return game_state.get('connected', {}).get(sid, True)


def online_count(game_state):
    """Quantos jogadores estão online agora."""
    connected = game_state.get('connected', {})
    return sum(1 for sid in game_state['players'] if connected.get(sid, True))

def save_full_state(game_state, QUIZ_DATA, force=True):
    """Grava o estado em disco de forma atômica.

    Com force=False aplica um limite de frequência — usado a cada resposta,
    para não serializar o estado inteiro N vezes por pergunta.
    """
    global _last_save_at

    now = time.monotonic()
    if not force and (now - _last_save_at) < SAVE_MIN_INTERVAL:
        return False

    state = {
        'game_state': {
            'host_sid': game_state['host_sid'],
            'players': game_state['players'],
            'current_question': game_state['current_question'],
            'answers': game_state['answers'],
            'scores': game_state['scores'],
            'competition_scores': game_state['competition_scores'],
            'state': game_state['state'],
            'question_start_time': game_state['question_start_time'],
            'answers_time': game_state['answers_time'],
            'reading_duration': game_state.get('reading_duration'),
            'reading_started_at': game_state.get('reading_started_at'),
            'answer_duration': game_state.get('answer_duration'),
            'final_leaderboard': game_state.get('final_leaderboard', []),
            'connected': game_state.get('connected', {}),
            'question_token': game_state.get('question_token', 0),
            'class_slug': game_state.get('class_slug'),
            'quiz_name': game_state.get('quiz_name'),
            'PLAYER_SESSIONS': game_state['PLAYER_SESSIONS']
        },
        'quiz_data': QUIZ_DATA  # current quiz being played
    }

    try:
        json_store.write_json(constants.GAME_SAVE_FILE, state)
        _last_save_at = now
        log.debug("✅ Game state saved to file.")
        return True
    except Exception as e:
        log.error(f"❌ Failed to save game state: {e}")
        return False