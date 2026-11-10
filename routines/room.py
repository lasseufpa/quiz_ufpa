"""Informações da sala aberta: qual turma está aceitando alunos agora.

Como só existe uma sala por vez, quem abre a sala (o apresentador) define a
turma, e o aluno não precisa informar nada além do nome.
"""

from routines import classes, constants, runtime


def payload():
    """Dados sobre a sala atual, enviados aos navegadores (`room_info`)."""
    game_state = runtime.game_state
    slug = game_state.get('class_slug')
    return {
        'class': slug or None,
        'class_name': classes.name_of(slug) if slug else None,
        'state': game_state.get('state', constants.STATE_LOBBY),
        # Modo time: a tela do aluno mostra o seletor de time ao entrar
        'team_mode': bool(game_state.get('team_mode')),
        'teams': constants.TEAM_NAMES,
    }


def current_class():
    """Slug da turma da sala aberta (ou None)."""
    return runtime.game_state.get('class_slug')
