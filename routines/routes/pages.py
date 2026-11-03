"""Páginas do aluno, do apresentador e do editor de quizzes."""

import os

from flask import jsonify, redirect, render_template, request, session, url_for

from routines import runtime
from routines.network import get_local_ip


def player_join():
    """Página inicial do aluno."""
    return render_template('player.html')


def host_view():
    """Painel do professor (protegido por login)."""
    if not session.get('host_logged_in'):
        return redirect(url_for('host_login'))
    return render_template(
        'host.html',
        quiz_title="Quiz UFPA",
        host_ip=get_local_ip(),
        port=os.environ.get('QUIZ_PORT', '5000'),
    )


def check_session():
    """Informa se um token de sessão de jogador ainda é válido."""
    token = request.args.get('token')
    sessions = runtime.game_state['PLAYER_SESSIONS']

    if token in sessions and sessions[token]['sid'] in runtime.game_state['players']:
        return jsonify({'valid': True, 'nickname': sessions[token]['nickname']})
    return jsonify({'valid': False})


def editor_view():
    """Página de gerenciamento de quizzes."""
    return render_template('editor.html')


def tutorial():
    """Guias de uso: apresentador, editor, administrador e aluno."""
    return render_template('tutorials.html')


def register(app):
    app.add_url_rule('/', 'player_join', player_join)
    app.add_url_rule('/host', 'host_view', host_view)
    app.add_url_rule('/check_session', 'check_session', check_session)
    app.add_url_rule('/editor', 'editor_view', editor_view)
    app.add_url_rule('/guia', 'tutorial', tutorial)
