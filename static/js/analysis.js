// Modo Análise: árvore turma → quiz → execução e detalhe de cada partida.

const treeEl = document.getElementById('analysis-tree');
const panelEl = document.getElementById('analysis-panel');

let currentRunId = null;

function escapeHtml(value) {
    return String(value == null ? '' : value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

function formatPoints(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '0';
    return Number.isInteger(n) ? String(n) : n.toFixed(1).replace('.', ',');
}

function formatDate(value) {
    if (!value) return '';
    const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return match ? `${match[3]}/${match[2]}/${match[1]}` : String(value);
}

// -------------------- Árvore --------------------
async function loadTree() {
    try {
        const res = await fetch('/api/analysis/runs');
        if (res.status === 401) {
            window.location.href = '/analise/login';
            return;
        }
        const data = await res.json();
        renderTree(data.classes || []);
    } catch (err) {
        treeEl.innerHTML = '<p class="analysis-empty">Não foi possível carregar a lista.</p>';
        console.warn('Falha ao carregar execuções:', err);
    }
}

function renderTree(classes) {
    treeEl.innerHTML = '';
    if (classes.length === 0) {
        treeEl.innerHTML = '<p class="analysis-empty">Nenhuma execução encontrada em <code>scores/</code>.</p>';
        return;
    }

    classes.forEach((group, index) => {
        const details = document.createElement('details');
        details.className = 'tree-class';
        details.open = index === 0;

        const summary = document.createElement('summary');
        const quizzes = group.quizzes || [];
        const total = quizzes.reduce((sum, quiz) => sum + quiz.runs.length, 0);
        summary.textContent = `${group.class_name} (${total})`;
        details.appendChild(summary);

        quizzes.forEach((quiz) => {
            const quizBlock = document.createElement('div');
            quizBlock.className = 'tree-quiz';

            const title = document.createElement('p');
            title.className = 'tree-quiz-title';
            title.textContent = quiz.quiz_title;
            quizBlock.appendChild(title);

            const list = document.createElement('div');
            list.className = 'tree-quiz-list';

            quiz.runs.forEach((run) => {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'tree-run';
                button.dataset.runId = run.id;
                button.innerHTML =
                    `${escapeHtml(run.label)}<span class="run-meta">` +
                    `${run.player_count} aluno${run.player_count === 1 ? '' : 's'}` +
                    (run.kind === 'full'
                        ? ` · ${run.question_count} pergunta${run.question_count === 1 ? '' : 's'}`
                        : ' · somente totais') +
                    '</span>';
                button.addEventListener('click', () => selectRun(run.id, button));
                list.appendChild(button);
            });

            quizBlock.appendChild(list);
            details.appendChild(quizBlock);
        });

        treeEl.appendChild(details);
    });
}

function selectRun(runId, button) {
    currentRunId = runId;
    treeEl.querySelectorAll('.tree-run').forEach((el) => el.classList.remove('active'));
    if (button) button.classList.add('active');
    loadRun(runId);
}

// -------------------- Detalhe --------------------
async function loadRun(runId) {
    panelEl.innerHTML = '<div class="analysis-empty">Carregando…</div>';
    try {
        const res = await fetch(`/api/analysis/runs/${encodeURIComponent(runId)}`);
        if (res.status === 401) {
            window.location.href = '/analise/login';
            return;
        }
        if (!res.ok) throw new Error('Execução não encontrada');
        const run = await res.json();
        renderRun(run);
    } catch (err) {
        panelEl.innerHTML = `<div class="analysis-empty">${escapeHtml(err.message)}</div>`;
    }
}

function statCard(label, value) {
    return `<div class="stat-card">
        <div class="stat-label">${escapeHtml(label)}</div>
        <div class="stat-value">${escapeHtml(value)}</div>
    </div>`;
}

function renderRun(run) {
    const players = run.players || [];
    const questions = run.questions || [];
    const totalEvaluation = players.reduce((sum, p) => sum + (p.evaluation || 0), 0);
    const totalCompetition = players.reduce((sum, p) => sum + (p.competition || 0), 0);
    const maxEvaluation = questions.length || run.question_count || 0;
    const avgEvaluation = players.length ? totalEvaluation / players.length : 0;

    const parts = [];
    parts.push(`<div class="run-title">${escapeHtml(run.label || 'Execução')}</div>`);
    parts.push(`<div class="run-subtitle">${escapeHtml(run.class_name || '')} · ${escapeHtml(run.quiz_title || '')}</div>`);

    const stats = [
        statCard('Alunos', String(players.length)),
        statCard('Perguntas', String(maxEvaluation || '—')),
        statCard('Acertos (total)', formatPoints(totalEvaluation)),
        statCard('Média de acertos', players.length ? formatPoints(avgEvaluation) : '—'),
        statCard('Pontos de competição', formatPoints(totalCompetition)),
    ];
    if (run.team_mode) {
        stats.push(statCard('Modo time', 'ligado'));
    }
    parts.push(`<div class="stats-grid">${stats.join('')}</div>`);

    if (run.kind !== 'full') {
        parts.push(`<div class="analysis-note">
            Esta execução foi registrada antes do relatório por pergunta existir,
            então só temos os totais de cada aluno.
        </div>`);
    }

    if (questions.length) {
        parts.push(renderQuestionSection(questions));
    }
    if (players.length) {
        parts.push(renderPlayersSection(run, players, questions));
    } else {
        parts.push('<div class="analysis-empty">Nenhum aluno participou desta execução.</div>');
    }

    panelEl.innerHTML = parts.join('');
    bindPlayerFilter();
}

function renderQuestionSection(questions) {
    const rows = questions.map((q) => {
        const answered = q.answered || 0;
        const accuracy = q.accuracy == null ? '—' : `${Math.round(q.accuracy * 100)}%`;
        const distribution = (q.distribution || [])
            .map((count, index) => `${String.fromCharCode(65 + index)}:${count}`)
            .join(' · ');
        return `<tr>
            <td class="num">${q.index + 1}</td>
            <td class="q-text">${escapeHtml(q.text || '')}</td>
            <td class="num">${q.correct}/${answered}</td>
            <td class="num">${accuracy}</td>
            <td class="num">${formatPoints(q.avg_points)}</td>
            <td class="num">${q.avg_time == null ? '—' : formatPoints(q.avg_time) + ' s'}</td>
            <td class="dist">${escapeHtml(distribution || '—')}</td>
        </tr>`;
    }).join('');

    return `<section class="analysis-section">
        <h2>Por pergunta</h2>
        <div class="analysis-table-wrap">
            <table class="analysis-table">
                <thead>
                    <tr>
                        <th class="num">#</th>
                        <th>Enunciado</th>
                        <th class="num">Acertos</th>
                        <th class="num">%</th>
                        <th class="num">Média pts</th>
                        <th class="num">Tempo médio</th>
                        <th>Respostas</th>
                    </tr>
                </thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    </section>`;
}

function renderPlayersSection(run, players, questions) {
    const ordered = players.slice().sort((a, b) => (b.competition || 0) - (a.competition || 0));
    const hasMatrix = questions.length > 0;

    const head = ['<th>Aluno</th>', '<th class="num">Acertos</th>', '<th class="num">Competição</th>'];
    if (hasMatrix) {
        questions.forEach((q) => head.push(`<th class="num" title="${escapeHtml(q.text || '')}">P${q.index + 1}</th>`));
    }

    const rows = ordered.map((player) => {
        const team = player.team_name
            ? `<span class="team-tag">${escapeHtml(player.team_name)}</span>`
            : '';
        const answerMap = new Map((player.answers || []).map((a) => [a.question, a]));
        const cells = [`<td class="player-name">${escapeHtml(player.nickname)}${team}</td>`,
            `<td class="num">${player.evaluation}</td>`,
            `<td class="num">${formatPoints(player.competition)}</td>`];

        if (hasMatrix) {
            questions.forEach((q) => {
                const answer = answerMap.get(q.index) || {};
                if (!answer.answered) {
                    cells.push('<td class="cell blank" title="Não respondeu">—</td>');
                } else if (answer.correct) {
                    const time = answer.time == null ? '' : ` · ${formatPoints(answer.time)} s`;
                    cells.push(`<td class="cell hit" title="Acertou${time}">+${formatPoints(answer.points)}</td>`);
                } else {
                    cells.push('<td class="cell miss" title="Errou">✗</td>');
                }
            });
        }
        return `<tr>${cells.join('')}</tr>`;
    }).join('');

    const legend = hasMatrix
        ? 'Cada célula mostra os pontos de competição ganhos na pergunta (✗ = errou, — = não respondeu).'
        : 'Esta execução só tem os totais; o detalhe por pergunta começa a ser gravado nas próximas partidas.';

    return `<section class="analysis-section">
        <h2>Pontuações individuais</h2>
        <div class="filter-row">
            <input id="player-filter" type="search" placeholder="Filtrar por aluno…" autocomplete="off">
            <span class="dist">${escapeHtml(legend)}</span>
        </div>
        <div class="analysis-table-wrap">
            <table class="analysis-table matrix-table">
                <thead><tr>${head.join('')}</tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    </section>`;
}

function bindPlayerFilter() {
    const input = document.getElementById('player-filter');
    if (!input) return;
    input.addEventListener('input', () => {
        const term = input.value.trim().toLowerCase();
        document.querySelectorAll('.matrix-table tbody tr').forEach((tr) => {
            const name = tr.querySelector('.player-name')?.textContent?.toLowerCase() || '';
            tr.style.display = name.includes(term) ? '' : 'none';
        });
    });
}

loadTree();
