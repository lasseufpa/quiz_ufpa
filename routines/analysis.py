"""Relatório de cada execução de quiz e índice do modo Análise.

A cada fim de partida o jogo grava, na pasta `scores/`:

- `scores_<turma>_<quiz>_<data>[_n].csv` — resumo (já existia): acertos de
  avaliação e pontos de competição por aluno;
- `relatorio_<turma>_<quiz>_<data>[_n].csv` — detalhe "longo": uma linha por
  aluno × pergunta, com alternativa marcada, acerto, pontos e tempo;
- `relatorio_<...>.json` — o mesmo conteúdo estruturado, usado pela tela de
  Análise (turmas → quizzes → "Quiz #n de dd/mm/aaaa").

O `_n` vem do nome do resumo para que os dois arquivos de uma execução fiquem
sempre com o mesmo número.
"""

import csv
import logging
import os
import re
from datetime import datetime

from routines import classes, constants, files_handler, json_store
from routines import game_state_handler as game_handler
from routines import logger  # noqa: F401  (configura console + arquivo)

log = logging.getLogger(__name__)

REPORT_PREFIX = 'relatorio_'
SUMMARY_PREFIX = 'scores_'

# scores_<turma>_<quiz>_AAAAMMDD[_n].csv
_LEGACY_RE = re.compile(
    r'^' + SUMMARY_PREFIX + r'(?P<rest>.+)_(?P<date>\d{8})(?:_(?P<index>\d+))?\.csv$'
)


def _safe_filename(text):
    """Mesmo critério usado em `game_logic.export_scores_to_csv`."""
    safe = ''.join(c if c.isalnum() or c in '.-_' else '_' for c in text or '')
    return safe.strip('_') or 'sem_nome'


def _folder():
    os.makedirs(constants.SCORES_FOLDER, exist_ok=True)
    return constants.SCORES_FOLDER


# -------------------- Gravação da execução --------------------
def report_paths(summary_path):
    """Caminhos (json, csv) do relatório que acompanha o resumo da partida."""
    stem = os.path.splitext(os.path.basename(summary_path))[0]
    if stem.startswith(SUMMARY_PREFIX):
        stem = REPORT_PREFIX + stem[len(SUMMARY_PREFIX):]
    else:
        stem = REPORT_PREFIX + stem
    folder = _folder()
    return os.path.join(folder, stem + '.json'), os.path.join(folder, stem + '.csv')


def _question_rows(quiz_data, history, players):
    """Uma linha por aluno × pergunta (o que alimenta o CSV e a tela)."""
    questions = quiz_data.get('questions') or []
    by_index = {}
    for entry in history or []:
        by_index[entry.get('index')] = entry.get('players') or {}

    rows = []
    for sid, nickname in players.items():
        for index, question in enumerate(questions):
            info = (by_index.get(index) or {}).get(sid) or {}
            option = info.get('option')
            correct = bool(info.get('correct'))
            rows.append({
                'nickname': nickname,
                'question': index,
                'question_text': question.get('text', ''),
                'option': option,
                'answer_text': (
                    (question.get('options') or [])[option]
                    if isinstance(option, int) and 0 <= option < len(question.get('options') or [])
                    else ''
                ),
                'correct_option': question.get('correct_option'),
                'correct_answer_text': _option_text(question),
                'answered': bool(info.get('answered')),
                'correct': correct,
                'evaluation': 1 if correct else 0,
                'competition': int(info.get('points') or 0),
                'time': info.get('time'),
            })
    return rows


def _option_text(question):
    try:
        index = int(question.get('correct_option', 0))
    except (TypeError, ValueError):
        return ''
    options = question.get('options') or []
    return options[index] if 0 <= index < len(options) else ''


def _question_summary(quiz_data, history, players):
    """Estatísticas por pergunta: acertos, distribuição e média de pontos."""
    questions = quiz_data.get('questions') or []
    by_index = {}
    for entry in history or []:
        by_index[entry.get('index')] = entry.get('players') or {}

    summary = []
    for index, question in enumerate(questions):
        marks = by_index.get(index) or {}
        option_count = len(question.get('options') or [])
        distribution = [0] * option_count
        answered = correct = 0
        points = []
        times = []
        for sid in players:
            info = marks.get(sid)
            if not info:
                continue
            option = info.get('option')
            if info.get('answered'):
                answered += 1
                if isinstance(option, int) and 0 <= option < option_count:
                    distribution[option] += 1
            if info.get('correct'):
                correct += 1
                points.append(int(info.get('points') or 0))
            if info.get('time') is not None:
                times.append(float(info['time']))

        summary.append({
            'index': index,
            'text': question.get('text', ''),
            'options': question.get('options') or [],
            'correct_option': question.get('correct_option'),
            'correct_text': _option_text(question),
            'answered': answered,
            'correct': correct,
            'accuracy': round(correct / answered, 3) if answered else None,
            'distribution': distribution,
            'avg_points': round(sum(points) / len(points), 1) if points else 0.0,
            'avg_time': round(sum(times) / len(times), 1) if times else None,
        })
    return summary


def save_run(game_state, quiz_data, summary_path, finished_at=None):
    """Grava o relatório detalhado da execução que acabou de terminar.

    `finished_at` permite gravar um relatório de uma execução antiga (ex.:
    reconstruída a partir do log) com a data/hora originais.

    Nunca levanta exceção: um problema no relatório não pode estragar o fim da
    partida (o resumo em CSV já foi gravado nesse ponto).
    """
    try:
        players = game_state.get('players') or {}
        history = game_state.get('history') or []
        teams = game_state.get('teams') or {}
        names = game_handler.team_names(game_state)
        class_slug = game_state.get('class_slug')

        completed = [entry.get('index') for entry in history]
        question_count = len(quiz_data.get('questions') or [])

        json_path, csv_path = report_paths(summary_path)
        finished_at = finished_at or datetime.now()
        run_index = _run_index_from_name(summary_path)

        rows = _question_rows(quiz_data, history, players)
        by_nickname = {}
        for row in rows:
            by_nickname.setdefault(row['nickname'], []).append(row)

        player_entries = []
        for sid, nickname in players.items():
            marks = by_nickname.get(nickname, [])
            player_entries.append({
                'nickname': nickname,
                'team': teams.get(sid),
                'team_name': names.get(teams.get(sid)) if teams.get(sid) else None,
                'evaluation': int(game_state['scores'].get(sid, 0)),
                'competition': int(game_state['competition_scores'].get(sid, 0)),
                'answers': [
                    {
                        'question': mark['question'],
                        'answered': mark['answered'],
                        'option': mark['option'],
                        'correct': mark['correct'],
                        'points': mark['competition'],
                        'time': mark['time'],
                    }
                    for mark in marks
                ],
            })

        data = {
            'version': 1,
            'class_slug': class_slug,
            'class_name': classes.name_of(class_slug) or class_slug,
            'quiz_title': quiz_data.get('title') or 'Quiz',
            'quiz_name': game_state.get('quiz_name'),
            'finished_at': finished_at.isoformat(timespec='seconds'),
            'date': finished_at.strftime('%Y-%m-%d'),
            'run_index': run_index,
            'team_mode': bool(game_state.get('team_mode')),
            'team_names': names,
            'question_count': question_count,
            'answered_questions': len(set(completed)),
            'players': player_entries,
            'questions': _question_summary(quiz_data, history, players),
        }

        json_store.write_json(json_path, data)
        _write_csv(csv_path, data, rows)
        log.info(f"Relatório da execução gravado em {json_path}")
        return json_path, csv_path
    except Exception as e:  # não derruba o fim da partida
        log.error(f"Falha ao gravar o relatório da execução: {e}")
        return None, None


def _run_index_from_name(summary_path):
    """Número da execução no dia (o `_n` depois da data; sem sufixo é 1)."""
    stem = os.path.splitext(os.path.basename(summary_path))[0]
    match = re.search(r'_\d{8}_(\d+)$', stem)
    return int(match.group(1)) if match else 1


def _write_csv(path, data, rows):
    header = ['Turma', 'Quiz', 'Data', 'Execução', 'Jogador', 'Time', 'Pergunta',
              'Enunciado', 'Resposta', 'Resposta correta', 'Acertou',
              'Pontos Avaliação', 'Pontos Competição', 'Tempo (s)']
    teams = {player['nickname']: player['team_name'] for player in data['players']}
    questions = {q['index']: q for q in data['questions']}

    with open(path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(header)
        for row in rows:
            question = questions.get(row['question']) or {}
            writer.writerow([
                data['class_name'],
                data['quiz_title'],
                data['date'],
                data['run_index'],
                row['nickname'],
                teams.get(row['nickname']) or '',
                row['question'] + 1,
                question.get('text', ''),
                row['answer_text'],
                row['correct_answer_text'],
                'Sim' if row['correct'] else 'Não',
                row['evaluation'],
                row['competition'],
                '' if row['time'] is None else f"{row['time']:.2f}".replace('.', ','),
            ])


# -------------------- Índice para o modo Análise --------------------
def _label(date_text, run_index):
    """'Quiz #4 de 19/11/2026'."""
    try:
        parsed = datetime.strptime(date_text, '%Y-%m-%d')
    except (TypeError, ValueError):
        return f'Quiz #{run_index}'
    return f'Quiz #{run_index} de {parsed.strftime("%d/%m/%Y")}'


def _read_json_header(path):
    data, _source = json_store.read_json(path)
    return data if isinstance(data, dict) else None


def _legacy_players(path):
    try:
        with open(path, newline='', encoding='utf-8') as csvfile:
            return list(csv.DictReader(csvfile))
    except OSError:
        return []


def _split_legacy(rest):
    """Separa '<turma>_<quiz>' usando os nomes de turma conhecidos."""
    known = sorted(classes.all_classes().items(),
                   key=lambda item: len(item[1]['name']), reverse=True)
    for slug, info in known:
        safe_class = _safe_filename(info['name'])
        if rest.startswith(safe_class + '_'):
            return slug, info['name'], rest[len(safe_class) + 1:]
    return None, 'Sem turma', rest


def _quiz_title_from_safe(slug, safe_quiz):
    """Tenta recuperar o título bonito a partir do arquivo do quiz."""
    if not slug:
        return safe_quiz
    try:
        names = files_handler.get_quiz_list(slug)
    except (OSError, ValueError):
        return safe_quiz
    for name in names:
        if _safe_filename(name) == safe_quiz:
            try:
                data = files_handler.load_quiz(slug, name)
            except (OSError, ValueError):
                continue
            if data and data.get('title'):
                return data['title']
            return name
    return safe_quiz


def list_runs():
    """Todas as execuções encontradas na pasta de resultados.

    Lê primeiro os relatórios completos (JSON) e, para resumos antigos que não
    têm relatório, devolve uma entrada só com os totais.
    """
    folder = _folder()
    try:
        names = os.listdir(folder)
    except OSError as e:
        log.warning(f"Não foi possível listar {folder}: {e}")
        return []

    runs = []
    covered = set()
    for name in sorted(names):
        if not (name.startswith(REPORT_PREFIX) and name.endswith('.json')):
            continue
        path = os.path.join(folder, name)
        data = _read_json_header(path)
        if not data:
            continue
        covered.add(name[len(REPORT_PREFIX):-len('.json')])
        date = data.get('date')
        index = int(data.get('run_index') or 1)
        runs.append({
            'id': name,
            'kind': 'full',
            'class_name': data.get('class_name') or 'Sem turma',
            'class_slug': data.get('class_slug'),
            'quiz_title': data.get('quiz_title') or 'Quiz',
            'date': date,
            'run_index': index,
            'label': _label(date, index),
            'finished_at': data.get('finished_at'),
            'player_count': len(data.get('players') or []),
            'question_count': int(data.get('question_count') or 0),
        })

    for name in sorted(names):
        if not (name.startswith(SUMMARY_PREFIX) and name.endswith('.csv')):
            continue
        if name[len(SUMMARY_PREFIX):-len('.csv')] in covered:
            continue
        match = _LEGACY_RE.match(name)
        if not match:
            continue
        slug, class_name, safe_quiz = _split_legacy(match.group('rest'))
        index = int(match.group('index') or 1)
        raw_date = match.group('date')
        date = f'{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}'
        players = _legacy_players(os.path.join(folder, name))
        runs.append({
            'id': name,
            'kind': 'totals',
            'class_name': class_name,
            'class_slug': slug,
            'quiz_title': _quiz_title_from_safe(slug, safe_quiz),
            'date': date,
            'run_index': index,
            'label': _label(date, index),
            'finished_at': _file_time(os.path.join(folder, name)),
            'player_count': len(players),
            'question_count': 0,
        })

    runs.sort(key=lambda run: (run.get('finished_at') or '', run['run_index']))
    return runs


def _file_time(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec='seconds')
    except OSError:
        return None


def grouped_runs():
    """Árvore turma → quiz → execuções, pronta para a tela de Análise."""
    tree = {}
    for run in list_runs():
        class_key = run['class_name']
        quiz_key = run['quiz_title']
        node = tree.setdefault(class_key, {
            'class_name': class_key,
            'class_slug': run['class_slug'],
            'quizzes': {},
        })
        bucket = node['quizzes'].setdefault(quiz_key, {'quiz_title': quiz_key, 'runs': []})
        bucket['runs'].append({
            'id': run['id'],
            'kind': run['kind'],
            'label': run['label'],
            'date': run['date'],
            'run_index': run['run_index'],
            'player_count': run['player_count'],
            'question_count': run['question_count'],
        })

    result = []
    for class_name in sorted(tree):
        node = tree[class_name]
        quizzes = []
        for title in sorted(node['quizzes']):
            bucket = node['quizzes'][title]
            bucket['runs'].sort(key=lambda run: (run['date'], run['run_index']), reverse=True)
            quizzes.append(bucket)
        result.append({
            'class_name': node['class_name'],
            'class_slug': node['class_slug'],
            'quizzes': quizzes,
        })
    return result


def load_run(run_id):
    """Carrega uma execução do índice (relatório completo ou resumo antigo)."""
    if not run_id or os.path.basename(run_id) != run_id:
        return None
    if not (run_id.startswith(REPORT_PREFIX) or run_id.startswith(SUMMARY_PREFIX)):
        return None

    folder = _folder()
    path = os.path.join(folder, run_id)
    if not os.path.isfile(path):
        return None

    if run_id.endswith('.json'):
        data = _read_json_header(path)
        if not data:
            return None
        data['id'] = run_id
        data['kind'] = 'full'
        data['label'] = _label(data.get('date'), int(data.get('run_index') or 1))
        return data

    match = _LEGACY_RE.match(run_id)
    if not match:
        return None
    slug, class_name, safe_quiz = _split_legacy(match.group('rest'))
    raw_date = match.group('date')
    date = f'{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}'
    index = int(match.group('index') or 1)
    players = []
    for row in _legacy_players(path):
        try:
            evaluation = int(row.get('Pontuação (Avaliação)') or 0)
        except ValueError:
            evaluation = 0
        try:
            competition = int(row.get('Pontuação (Competição)') or 0)
        except ValueError:
            competition = 0
        players.append({
            'nickname': row.get('Jogador') or '?',
            'team': None,
            'team_name': None,
            'evaluation': evaluation,
            'competition': competition,
            'answers': [],
        })
    players.sort(key=lambda player: player['competition'], reverse=True)
    return {
        'id': run_id,
        'kind': 'totals',
        'class_slug': slug,
        'class_name': class_name,
        'quiz_title': _quiz_title_from_safe(slug, safe_quiz),
        'date': date,
        'run_index': index,
        'label': _label(date, index),
        'finished_at': _file_time(path),
        'team_mode': False,
        'team_names': {},
        'player_count': len(players),
        'question_count': 0,
        'answered_questions': 0,
        'players': players,
        'questions': [],
    }
