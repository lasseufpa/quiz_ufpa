"""Modo Análise: consulta das execuções de quiz, protegida por senha.

Usa a mesma senha do professor. Quem já entrou no painel de administração
também entra aqui sem digitar de novo.
"""

import logging

from flask import jsonify, redirect, render_template, request, session, url_for

from routines import logger  # noqa: F401  (configura console + arquivo)
from routines import analysis
from routines.routes.auth import _password_matches

log = logging.getLogger(__name__)


def _logged_in():
    return bool(session.get('analysis_logged_in') or session.get('admin_logged_in'))


def analysis_login():
    """Tela de senha do modo Análise."""
    if _logged_in():
        return redirect(url_for('analysis_view'))

    error = None
    if request.method == 'POST':
        if _password_matches(request.form.get('password')):
            session['analysis_logged_in'] = True
            log.info("Modo Análise liberado por senha.")
            return redirect(url_for('analysis_view'))
        error = 'Senha incorreta!'
        log.warning("Senha incorreta no modo Análise.")

    return render_template('analysis_login.html', error=error)


def analysis_view():
    """Página do modo Análise."""
    if not _logged_in():
        return redirect(url_for('analysis_login'))
    return render_template('analysis.html')


def analysis_logout():
    """Sai do modo Análise."""
    session.pop('analysis_logged_in', None)
    return redirect(url_for('analysis_login'))


def api_analysis_runs():
    """Árvore turma → quiz → execuções."""
    if not _logged_in():
        return jsonify({'error': 'Não autorizado'}), 401
    return jsonify({'classes': analysis.grouped_runs()})


def api_analysis_run(run_id):
    """Detalhe de uma execução (relatório completo ou só totais)."""
    if not _logged_in():
        return jsonify({'error': 'Não autorizado'}), 401
    data = analysis.load_run(run_id)
    if data is None:
        return jsonify({'error': 'Execução não encontrada'}), 404
    return jsonify(data)


def register(app):
    app.add_url_rule('/analise', 'analysis_view', analysis_view)
    app.add_url_rule('/analise/login', 'analysis_login', analysis_login,
                     methods=['GET', 'POST'])
    app.add_url_rule('/analise/logout', 'analysis_logout', analysis_logout)
    app.add_url_rule('/api/analysis/runs', 'api_analysis_runs', api_analysis_runs)
    app.add_url_rule('/api/analysis/runs/<run_id>', 'api_analysis_run', api_analysis_run)
