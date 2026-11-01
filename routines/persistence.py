"""Persistência da partida em disco, para retomar após reiniciar o servidor."""

import logging

from routines import constants, json_store
from routines import logger  # noqa: F401  (configura console + arquivo)
from routines import runtime
from routines import game_state_handler as game_handler

log = logging.getLogger(__name__)


def save_full_state(game_state, quiz_data, force=True):
    """Grava o estado da partida (delegado a game_state_handler)."""
    return game_handler.save_full_state(game_state, quiz_data, force)


def load_full_state():
    """Lê o estado salvo do disco; retorna None se não existir."""
    state, source = json_store.read_json(constants.GAME_SAVE_FILE)

    if state is None:
        if source == 'corrupt':
            log.error("❌ Estado salvo corrompido e sem backup válido.")
        return None

    if source == 'backup':
        log.warning("⚠️ Estado da partida recuperado a partir do backup.")
    log.info("✅ Game state loaded from file.")
    return state


def restore_full_state():
    """Restaura `runtime.game_state` e `runtime.quiz_data` do arquivo salvo."""
    state = load_full_state()
    if not state:
        return False

    saved = state.get('game_state', {})
    runtime.game_state.update(saved)

    # Compatibilidade com arquivos gerados por versões anteriores
    runtime.game_state.setdefault('competition_scores', {})
    runtime.game_state.setdefault('question_start_time', None)
    runtime.game_state.setdefault('answers_time', {})
    runtime.game_state.setdefault('connected', {})
    runtime.game_state.setdefault('question_token', 0)
    runtime.game_state['PLAYER_SESSIONS'] = saved.get('PLAYER_SESSIONS', {})

    runtime.quiz_data = state.get('quiz_data')
    log.info("--- Game state restored from backup ---")
    return True
