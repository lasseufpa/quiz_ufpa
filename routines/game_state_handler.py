from routines import  constants
import logging
import json
import os
import time

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
        'connected': {},        # {sid: True/False} — jogador online/offline
        'question_token': 0,    # invalida timers de perguntas antigas
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
            'connected': game_state.get('connected', {}),
            'question_token': game_state.get('question_token', 0),
            'PLAYER_SESSIONS': game_state['PLAYER_SESSIONS']
        },
        'quiz_data': QUIZ_DATA  # current quiz being played
    }

    tmp_path = constants.GAME_SAVE_FILE + '.tmp'
    try:
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, constants.GAME_SAVE_FILE)  # troca atômica
        _last_save_at = now
        log.debug("✅ Game state saved to file.")
        return True
    except Exception as e:
        log.error(f"❌ Failed to save game state: {e}")
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False