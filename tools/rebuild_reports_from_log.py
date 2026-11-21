"""Reconstrói relatórios por questão a partir de um `server.log` antigo.

Antes de existir o relatório `relatorio_*.json/csv`, o único registro das
partidas era o resumo em `scores/scores_*.csv` (só os totais) e o log, que
guarda cada resposta com alternativa e tempo:

    Jogador Ana respondeu: 1 em 8.123456s
    Mostrando resultados da pergunta 3.
    ...
    ✅ Resultados exportados para scores\\scores_Turma_Quiz_20261119_4.csv

O script lê o log, descobre em qual execução (`scores_...`) cada bloco de
respostas caiu, recalcula acertos e pontos (mesma fórmula do jogo) e **confere
com o CSV de resumo**. Se os totais baterem, grava o relatório no formato
normal — a tela de Análise passa a mostrar o detalhe por pergunta também para
as execuções antigas.

Uso:
    python tools/rebuild_reports_from_log.py                 # simulação (não grava)
    python tools/rebuild_reports_from_log.py --apply         # grava os relatórios
    python tools/rebuild_reports_from_log.py --date 2026-11-19 --force
"""

import argparse
import csv
import math
import os
import re
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from routines import analysis, classes, constants, files_handler  # noqa: E402

_LINE_RE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+'
    r'\[(?P<level>[A-Z]+)\]\s+(?P<logger>[\w.]+):\s(?P<msg>.*)$'
)
_ANSWER_RE = re.compile(
    r'^Jogador (?P<name>.+?) respondeu: (?P<option>-?\d+) em (?P<time>[0-9.]+)s$'
)
_RESULTS_RE = re.compile(r'^Mostrando resultados da pergunta (?P<number>\d+)\.$')
_EXPORT_RE = re.compile(r'Resultados exportados para (?P<path>.+)$')
_OPEN_ROOM_RE = re.compile(r'Sala aberta para a turma .+ \(modo time: (?P<mode>\w+)\)')
_START_RE = re.compile(r"Iniciando o jogo da turma '(?P<class>[^']*)'!")


def competition_points(elapsed):
    """Mesma curva usada em `game_logic._score_answers`."""
    if elapsed is None or elapsed < 0:
        return 0
    t = elapsed / constants.COMPETITION_HALF_WINDOW
    sinc = math.sin(math.pi * t + 1e-5) / (math.pi * t + 1e-5)
    return int(constants.COMPETITION_MAX_POINTS * sinc ** constants.COMPETITION_EXPONENT)


# -------------------- Leitura do log --------------------
def parse_runs(log_path, date=None):
    """Lista de execuções encontradas no log, na ordem em que terminaram."""
    runs = []
    answers = {}
    pending = []
    team_mode = False
    started_at = None

    with open(log_path, encoding='utf-8', errors='replace') as log_file:
        for line in log_file:
            match = _LINE_RE.match(line.rstrip('\n'))
            if not match:
                continue
            timestamp = datetime.strptime(match.group('ts'), '%Y-%m-%d %H:%M:%S')
            if date and timestamp.strftime('%Y-%m-%d') != date:
                # Só ignora depois de limpar o estado de uma execução de outro dia
                continue
            message = match.group('msg')

            start = _START_RE.search(message)
            if start:
                answers = {}
                pending = []
                started_at = timestamp
                continue

            room = _OPEN_ROOM_RE.search(message)
            if room:
                team_mode = room.group('mode') == 'ligado'
                continue

            answer = _ANSWER_RE.match(message)
            if answer:
                pending.append((
                    answer.group('name').strip(),
                    int(answer.group('option')),
                    float(answer.group('time')),
                ))
                continue

            results = _RESULTS_RE.match(message)
            if results:
                answers[int(results.group('number')) - 1] = list(pending)
                pending = []
                continue

            export = _EXPORT_RE.search(message)
            if export:
                runs.append({
                    'finished_at': timestamp,
                    'started_at': started_at,
                    'summary_path': export.group('path').strip(),
                    'answers': {index: list(items) for index, items in answers.items()},
                    'team_mode': team_mode,
                })
                answers = {}
                pending = []
                started_at = None

    return runs


# -------------------- Ligação com os arquivos --------------------
def _read_summary(path):
    """{nome: (acertos, pontos)} do CSV de resumo, na ordem do arquivo."""
    rows = {}
    with open(path, newline='', encoding='utf-8') as csvfile:
        for row in csv.DictReader(csvfile):
            name = (row.get('Jogador') or '').strip()
            if not name:
                continue
            try:
                evaluation = int(row.get('Pontuação (Avaliação)') or 0)
            except ValueError:
                evaluation = 0
            try:
                competition = int(row.get('Pontuação (Competição)') or 0)
            except ValueError:
                competition = 0
            rows.setdefault(name.casefold(), (name, evaluation, competition))
    return rows


def _find_quiz(class_slug, safe_quiz):
    """Carrega o quiz a partir do nome usado no arquivo de resultados."""
    if not class_slug:
        return None
    try:
        names = files_handler.get_quiz_list(class_slug)
    except (OSError, ValueError):
        return None
    for name in names:
        if analysis._safe_filename(name) == safe_quiz:
            try:
                return files_handler.load_quiz(class_slug, name), name
            except (OSError, ValueError):
                return None
    return None


def _build_game_state(summary_rows, answers, quiz_data, class_slug, team_mode):
    """Monta o `game_state` no formato que `analysis.save_run` espera."""
    questions = quiz_data.get('questions') or []
    correct_options = []
    for question in questions:
        try:
            correct_options.append(int(question.get('correct_option', 0)))
        except (TypeError, ValueError):
            correct_options.append(0)

    # Nome no log → nome canônico do CSV (se existir), para casar os dois
    canonical = {name.casefold(): key for key, (name, _e, _c) in summary_rows.items()}

    history = []
    for index, items in sorted(answers.items()):
        correct_option = correct_options[index] if index < len(correct_options) else None
        marks = {}
        for name, option, elapsed in items:
            key = canonical.get(name.casefold())
            if key is None:
                continue
            is_correct = correct_option is not None and option == correct_option
            marks[key] = {
                'answered': True,
                'option': option,
                'correct': is_correct,
                'points': competition_points(elapsed) if is_correct else 0,
                'time': round(elapsed, 2),
            }
        history.append({'index': index, 'players': marks})

    players = {key: name for key, (name, _e, _c) in summary_rows.items()}
    return {
        'players': players,
        'team_names': dict(constants.TEAM_NAMES),
        'teams': {},
        'scores': {key: evaluation for key, (_n, evaluation, _c) in summary_rows.items()},
        'competition_scores': {key: competition for key, (_n, _e, competition)
                               in summary_rows.items()},
        'history': history,
        'class_slug': class_slug,
        'quiz_name': None,
        'team_mode': bool(team_mode),
    }


def _computed_totals(history, players):
    totals = {key: [0, 0] for key in players}
    for entry in history:
        for key, mark in (entry.get('players') or {}).items():
            totals.setdefault(key, [0, 0])
            if mark.get('correct'):
                totals[key][0] += 1
            totals[key][1] += int(mark.get('points') or 0)
    return totals


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', default=os.path.join(BASE_DIR, 'logs', 'server.log'))
    parser.add_argument('--date', help='só execuções deste dia (AAAA-MM-DD)')
    parser.add_argument('--apply', action='store_true',
                        help='grava os relatórios (sem isso, só mostra o que faria)')
    parser.add_argument('--force', action='store_true',
                        help='grava mesmo se os totais não conferirem com o CSV')
    args = parser.parse_args(argv)

    classes.load()
    runs = parse_runs(args.log, args.date)
    if not runs:
        print('Nenhuma execução encontrada no log.', file=sys.stderr)
        return 1

    written = skipped = failed = 0
    for run in runs:
        summary_path = run['summary_path']
        summary_name = os.path.basename(summary_path)
        label = f"{run['finished_at']:%d/%m/%Y %H:%M} · {summary_name}"
        json_path, _csv_path = analysis.report_paths(summary_path)

        if not os.path.isfile(summary_path):
            print(f"— {label}: resumo não encontrado, ignorado")
            skipped += 1
            continue
        if os.path.exists(json_path) and not args.force:
            print(f"— {label}: relatório já existe, ignorado")
            skipped += 1
            continue

        match = analysis._LEGACY_RE.match(summary_name)
        if not match:
            print(f"— {label}: nome de arquivo fora do padrão, ignorado")
            skipped += 1
            continue
        class_slug, _class_name, safe_quiz = analysis._split_legacy(match.group('rest'))
        found = _find_quiz(class_slug, safe_quiz)
        if not found:
            print(f"— {label}: quiz não encontrado, ignorado")
            skipped += 1
            continue
        quiz_data, quiz_name = found

        summary_rows = _read_summary(summary_path)
        game_state = _build_game_state(summary_rows, run['answers'], quiz_data,
                                      class_slug, run['team_mode'])
        game_state['quiz_name'] = quiz_name
        totals = _computed_totals(game_state['history'], game_state['players'])

        mismatches = []
        for key, (name, evaluation, competition) in summary_rows.items():
            computed_eval, computed_comp = totals.get(key, (0, 0))
            if (computed_eval, computed_comp) != (evaluation, competition):
                mismatches.append(
                    f"{name}: log={computed_eval}/{computed_comp} "
                    f"csv={evaluation}/{competition}"
                )

        answered = sum(len(items) for items in run['answers'].values())
        print(f"+ {label}: {len(game_state['players'])} alunos, "
              f"{len(run['answers'])} perguntas, {answered} respostas")

        if mismatches:
            print(f"  ⚠ totais divergentes ({len(mismatches)}):")
            for detail in mismatches[:8]:
                print(f"    {detail}")
            if not args.force:
                print('  → não gravado (use --force para gravar mesmo assim)')
                failed += 1
                continue

        if not args.apply:
            print('  → simulação: use --apply para gravar')
            continue

        saved = analysis.save_run(game_state, quiz_data, summary_path,
                                  finished_at=run['finished_at'])
        if saved[0]:
            written += 1
            print(f'  ✓ {os.path.basename(saved[0])}')
        else:
            failed += 1

    print(f"\nResumo: {written} gravado(s), {skipped} ignorado(s), {failed} com divergência")
    return 0 if not failed else 2


if __name__ == '__main__':
    raise SystemExit(main())
