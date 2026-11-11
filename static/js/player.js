const joinView = document.getElementById('join-view');
const waitView = document.getElementById('wait-view');
const questionView = document.getElementById('question-view');
const resultView = document.getElementById('result-view');

const nicknameInput = document.getElementById('nickname-input');
const nicknameDisplay = document.getElementById('nickname-display');
const teamPicker = document.getElementById('team-picker');
const teamDisplay = document.getElementById('team-display');
const teamResultDisplay = document.getElementById('team-result-display');
const optionsGrid = document.getElementById('options-grid');
const questionTextEl = document.getElementById('question-text');
const resultTextEl = document.getElementById('result-text');
const scoreDisplayEl = document.getElementById('score-display');
const waitMessageEl = document.getElementById('wait-message');
const teamLineEl = document.getElementById('team-line');
const scoreHistoryEl = document.getElementById('score-history');
const scoreHistoryBodyEl = document.getElementById('score-history-body');

const STATE_LOBBY = 0
const STATE_QUESTION = 1
const STATE_ANSWER = 2
const STATE_GAMEOVER = 3
let allow_answer = false;

let myLastAnswerIndex = null;
let lastAnsweredQuestionIndex = null; // stores the index of the question answered

let mySid = null;
let myTeam = null;
let teamMode = false;   // o professor ligou o modo time?
let selectedTeam = null; // 'A' ou 'B' — escolhido nos botões de time
let currentTotalQuestions = 0;   // total de perguntas do quiz atual
let sessionToken = localStorage.getItem('quizSessionToken');
// Só recebe/mostra eventos de jogo depois que o servidor confirma a entrada.
// Sem isso, quem ainda está digitando o nome via as alternativas aparecerem
// quando o professor iniciava a partida.
let joined = false;

// Verificar sessão existente ao carregar a página
window.addEventListener('load', () => {
    if (sessionToken) {
        checkExistingSession();
    }
});

function checkExistingSession() {
    fetch(`/check_session?token=${sessionToken}`)
        .then(response => response.json())
        .then(data => {
            if (data.valid) {
                // Sessão válida, ocultar tela de login e aguardar reconexão
                joinView.style.display = 'none';
                // Não sobrepõe a tela de pergunta/resultado caso o socket já
                // tenha restaurado a sessão antes desta resposta chegar
                const emJogo = (questionView.style.display === 'block')
                    || (resultView.style.display === 'block');
                if (!emJogo) waitView.style.display = 'block';
                nicknameDisplay.textContent = data.nickname;
                console.log('Sessão existente encontrada, aguardando reconexão...');
            } else {
                // Sessão inválida, limpar token
                localStorage.removeItem('quizSessionToken');
                localStorage.removeItem('answerSubmitted');
                sessionToken = null;
            }
        })
        .catch(error => {
            console.error('Erro ao verificar sessão:', error);
            localStorage.removeItem('quizSessionToken');
            sessionToken = null;
        });
}

socket.on('connect', () => {
    mySid = socket.id;
    console.log('Conectado com SID:', mySid);
    
    // Se temos um token de sessão, tentar restaurar a sessão
    if (sessionToken && mySid) {
        restorePlayerSession();
    } else {
        joinView.style = 'block';
    }
});

function restorePlayerSession() {
    socket.emit('restore_session', { 
        'token': sessionToken,
        'new_sid': mySid 
    });
}
// ========== FUNÇÃO show_question MODIFICADA ==========
function show_question(data) {
    console.log('gamestate = ' + data.state);
    if (data && data.total_questions) {
        currentTotalQuestions = data.total_questions;
    }
    waitView.style.display = 'none';
    resultView.style.display = 'none';
    questionView.style.display = 'block';

    questionTextEl.textContent = '';
    optionsGrid.innerHTML = '';

    const letters = ['A', 'B', 'C', 'D'];

    data.options.forEach((option, index) => {
        const btn = document.createElement('button');
        btn.textContent = letters[index] || '?';
        btn.classList.add('option-btn');
        btn.dataset.index = index;

        // Inicialmente desabilitado e com estilo cinza
        btn.disabled = true;
        btn.style.cursor = 'not-allowed';

        // Listener de clique (só será executado se o botão estiver habilitado)
        btn.addEventListener('click', () => {
            // Se já respondeu, não faz nada (segurança extra)
            if (myLastAnswerIndex !== null) return;

            socket.emit('submit_answer', { 'option_index': index });
            myLastAnswerIndex = index.toString();
            lastAnsweredQuestionIndex = data.question_index;
            localStorage.setItem("answerSubmitted", myLastAnswerIndex);
            localStorage.setItem("lastAnsweredQuestionIndex", lastAnsweredQuestionIndex);

            // Desabilita todos e destaca o escolhido
            optionsGrid.querySelectorAll('button').forEach(b => b.disabled = true);
            btn.style.backgroundColor = '#007bff';
            btn.style.color = 'white';
        });

        optionsGrid.appendChild(btn);
    });
}

function allow_answers(){
const buttons = optionsGrid.querySelectorAll('.option-btn');
    buttons.forEach(btn => {
        if (myLastAnswerIndex === null) {
            btn.disabled = false;
            btn.style.cursor = 'pointer';
        }
    });
    console.log('Respostas liberadas');
}

socket.on('answer_allowed', () => {
    if (!joined) return;
    // Habilita todos os botões que ainda não foram respondidos
    allow_answers();
});





function update_waiting_screen(myLastAnswerIndex, correctOptionIndex){
    if (myLastAnswerIndex !== null) {
        // Compara a resposta que salvamos (string) com a correta (string)
        if (myLastAnswerIndex === correctOptionIndex) {
            resultTextEl.textContent = 'Você Acertou!';
        } else {
            resultTextEl.textContent = 'Você Errou!';
        }
    } else {
        resultTextEl.textContent = 'Você não respondeu a tempo!';
    }
}

// -------------------- Tabela de pontuação --------------------
// O servidor manda a tabela pronta, com a pergunta mais recente no topo e o
// total acumulado no fim (evento `score_history`, personalizado por aluno).
function renderScoreHistory(data) {
    if (!scoreHistoryEl || !scoreHistoryBodyEl) return;

    const rows = (data && data.rows) || [];
    scoreHistoryBodyEl.innerHTML = '';

    if (rows.length === 0) {
        scoreHistoryEl.style.display = 'none';
        return;
    }

    const totalPerguntas = (data && data.total_questions)
        || ((currentTotalQuestions > 0)
            ? currentTotalQuestions
            : rows.reduce((maior, row) => Math.max(maior, row.question_index + 1), 0));

    rows.forEach((row) => {
        const tr = document.createElement('tr');
        tr.className = row.correct ? 'hit' : 'miss';

        const numero = document.createElement('td');
        numero.textContent = `Pergunta ${row.question_index + 1}/${totalPerguntas}`;

        const resultado = document.createElement('td');
        resultado.textContent = row.correct ? '✓' : (row.answered ? '✗' : '–');

        const pontos = document.createElement('td');
        pontos.textContent = row.correct ? `+${row.points}` : '0';

        tr.appendChild(numero);
        tr.appendChild(resultado);
        tr.appendChild(pontos);
        scoreHistoryBodyEl.appendChild(tr);
    });

    // Linha do agregado, sempre por último
    const total = document.createElement('tr');
    total.className = 'total';
    const rotulo = document.createElement('td');
    rotulo.textContent = 'Total';
    const acertos = document.createElement('td');
    acertos.textContent = `${data.total_correct || 0} acerto${(data.total_correct === 1) ? '' : 's'}`;
    const soma = document.createElement('td');
    soma.textContent = `${data.total_points || 0} pts`;
    total.appendChild(rotulo);
    total.appendChild(acertos);
    total.appendChild(soma);
    scoreHistoryBodyEl.appendChild(total);

    scoreHistoryEl.style.display = 'block';
}

socket.on('score_history', (data) => {
    if (!joined) return;
    renderScoreHistory(data);
});


// Entrar no Jogo
const joinBtn = document.getElementById('join-btn'); // Pega o botão

joinBtn.addEventListener('click', () => {
    const nickname = nicknameInput.value.trim(); // Usa .trim()

    // No modo time, o aluno precisa escolher onde vai competir
    let team = null;
    if (teamMode) {
        team = selectedTeam;
        if (!team) {
            alert('Escolha o seu time (Time A ou Time B) para entrar!');
            if (teamPicker) teamPicker.scrollIntoView({ block: 'center' });
            return;
        }
    }

    if (nickname) {
        joinBtn.disabled = true; // Desabilita o botão
        socket.emit('player_join', { 'nickname': nickname, 'team': team });
        console.log("Jogador " + nickname + " pediu para entrar");
        myTeam = team;
    } else{
        alert("Por favor adicione um nome!")
    }
    
}); 

// O servidor avisa se a sala está aberta e de qual turma é.
// O aluno não escolhe turma: só precisa digitar o nome quando a sala abrir.
const roomInfoEl = document.getElementById('room-info');
const roomClassNameEl = document.getElementById('room-class-name');
const roomClosedEl = document.getElementById('room-closed');

// Marca o time escolhido (visual + estado)
function selectTeam(key) {
    selectedTeam = key;
    if (!teamPicker) return;
    Array.prototype.forEach.call(teamPicker.querySelectorAll('.team-choice'), (btn) => {
        const ativo = btn.dataset.team === key;
        btn.classList.toggle('selected', ativo);
        btn.setAttribute('aria-pressed', ativo ? 'true' : 'false');
    });
}

// Monta os dois botões de time com os nomes que o servidor informou
function renderTeamOptions(teams) {
    if (!teamPicker) return;
    const mapa = teams || { A: 'Time A', B: 'Time B' };

    teamPicker.innerHTML = '';
    Object.keys(mapa).forEach((key) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'team-choice team-' + key.toLowerCase() +
            (selectedTeam === key ? ' selected' : '');
        btn.dataset.team = key;
        btn.textContent = mapa[key];
        btn.setAttribute('aria-pressed', selectedTeam === key ? 'true' : 'false');
        btn.addEventListener('click', () => selectTeam(key));
        teamPicker.appendChild(btn);
    });

    teamPicker.style.display = teamMode ? 'flex' : 'none';
}

function showMyTeam(teamName) {
    if (!teamLineEl || !teamDisplay) return;
    teamDisplay.textContent = teamName || '';
    teamLineEl.style.display = teamName ? 'block' : 'none';
}

socket.on('room_info', (data) => {
    const aberta = !!(data && data.class_name);

    teamMode = !!(data && data.team_mode);
    renderTeamOptions(data && data.teams);

    roomClassNameEl.textContent = aberta ? data.class_name : '';
    roomInfoEl.style.display = aberta ? 'block' : 'none';
    roomClosedEl.style.display = aberta ? 'none' : 'block';
    if (aberta) {
        roomClosedEl.textContent = 'Aguardando o professor abrir a sala...';
    }

    if (!aberta) {
        joinBtn.disabled = true;
    } else if (!sessionToken) {
        joinBtn.disabled = false;
        if (document.activeElement.tagName !== 'INPUT') nicknameInput.focus();
    }
});

// O professor fechou a sala (para trocar turma/quiz): todos precisam entrar
// de novo quando ela abrir. Mesmo quem já estava jogando volta para a entrada.
socket.on('room_closed', (data) => {
    localStorage.removeItem('quizSessionToken');
    localStorage.removeItem('answerSubmitted');
    localStorage.removeItem('lastAnsweredQuestionIndex');
    localStorage.removeItem('correctOptionIndex');

    sessionToken = null;
    myLastAnswerIndex = null;
    lastAnsweredQuestionIndex = null;
    allow_answer = false;
    joined = false;
    scoreDisplayEl.textContent = '0';
    nicknameDisplay.textContent = '';
    nicknameInput.value = '';
    showMyTeam(null);
    renderScoreHistory(null);
    selectedTeam = null;
    renderTeamOptions(null);

    questionView.style.display = 'none';
    resultView.style.display = 'none';
    waitView.style.display = 'none';
    joinView.style.display = 'block';

    if (data && data.reason) {
        roomClosedEl.textContent = data.reason;
    }
    roomClosedEl.style.display = 'block';
    joinBtn.disabled = true;
});


// Servidor confirmou a entrada

socket.on('join_success', (data) => {
    joined = true;
    joinView.style.display = 'none';
    waitView.style.display = 'block';
    nicknameDisplay.textContent = data.nickname;
    showMyTeam(data.team_name);
    if (data.team) selectTeam(data.team);

    // Tabela de pontuação (vem pronta do servidor, quando existir)
    renderScoreHistory(data.score_history);

    // O aluno pode ter entrado com o jogo já em andamento: avisa em vez de
    // jogar as alternativas na tela dele.
    if (waitMessageEl) {
        if (data && data.state === STATE_LOBBY) {
            waitMessageEl.textContent = 'Aguarde o professor iniciar o jogo...';
        } else {
            waitMessageEl.textContent =
                'A partida já começou! Você entra na próxima pergunta.';
        }
    }
    
    // Salvar o token da sessão no localStorage
    if (data.session_token) {
        sessionToken = data.session_token;
        localStorage.setItem('quizSessionToken', sessionToken);
    }
});

// Servidor restaurou a sessão
socket.on('session_restored', (data) => {
console.log('Sessão restaurada com sucesso, gamestate = '+data.state);
joined = true;
joinView.style.display = 'none';
waitView.style.display = 'block';
nicknameDisplay.textContent = data.nickname;
showMyTeam(data.team_name);
if (data.team) selectTeam(data.team);
renderScoreHistory(data.score_history);
allow_answer = data.allow_answer;



// Retrieve stored data
const storedAnswer = localStorage.getItem('answerSubmitted');
const storedQuestionIdx = localStorage.getItem('lastAnsweredQuestionIndex');
myLastAnswerIndex = storedAnswer;
correctOptionIndex = localStorage.getItem('correctOptionIndex');

// Update current score if available
if (data.current_score !== undefined) {
    scoreDisplayEl.textContent = data.current_score;
}

if (data.current_question >= 0) {
    // Game already started
    waitView.style.display = 'none';
    resultView.style.display = 'block';
    
    if (data.state == STATE_QUESTION) {
        // Check if the stored answer belongs to the CURRENT question
        if (storedAnswer !== null && storedQuestionIdx !== null && 
            parseInt(storedQuestionIdx) === data.current_question) {
            // Already answered this exact question → show waiting screen
            resultTextEl.textContent = 'Resposta recebida! Aguardando resultados...';
        } else {
            // No answer for the current question → clear stale data and show question
            myLastAnswerIndex = null;
            lastAnsweredQuestionIndex = null;
            localStorage.removeItem('answerSubmitted');
            localStorage.removeItem('lastAnsweredQuestionIndex');
            show_question(data);
        }
    }
    if (data.state == STATE_ANSWER) {
        update_waiting_screen(myLastAnswerIndex, correctOptionIndex);
    }
    if (data.state == STATE_GAMEOVER) {
        resultView.style.display = 'block';
        resultTextEl.textContent = 'O JOGO TERMINOU! Obrigado por jogar.';
    }
    if (allow_answer){
    allow_answers();
    }
}
});

socket.on('session_restore_failed', (data) => {
    console.log('Falha ao restaurar sessão:', data.reason);
    localStorage.removeItem('quizSessionToken');
    sessionToken = null;
    joined = false;
    joinView.style.display = 'block';
    waitView.style.display = 'none';
    joinBtn.disabled = false;
});


// Servidor enviou uma pergunta
socket.on('show_question', (data) => {
    if (!joined) return;
    console.log('inside socket.on');
    show_question(data);
    localStorage.removeItem('answerSubmitted');
    myLastAnswerIndex = null;
});

// Servidor confirmou o recebimento da resposta
socket.on('answer_received', () => {
    questionView.style.display = 'none';
    resultView.style.display = 'block';
    resultTextEl.textContent = 'Resposta recebida! Aguardando resultados...';
    localStorage.setItem('answerReceived', true);
});


// Servidor enviou os resultados
socket.on('show_results', (data) => {
    if (!joined) return;
    questionView.style.display = 'none';
    resultView.style.display = 'block';

    const myScore = data.scores[mySid] || 0;
    scoreDisplayEl.textContent = myScore;

    // Pega a resposta correta (como string)
    const correctOptionIndex = data.correct_option.toString();
    localStorage.setItem("correctOptionIndex", correctOptionIndex);

    update_waiting_screen(myLastAnswerIndex,correctOptionIndex);

    // Limpa a variável para a próxima pergunta
    // myLastAnswerIndex = null;
    // localStorage.removeItem("answerSubmitted");
    // --- FIM DA LÓGICA CORRIGIDA ---
});

socket.on('game_over', (payload) => {
    if (!joined) return;
    // O servidor manda {leaderboard, teams, team_mode} (ou uma lista, em
    // versões antigas): para o aluno basta o placar geral.
    const lista = Array.isArray(payload) ? payload : ((payload && payload.leaderboard) || []);
    questionView.style.display = 'none';
    resultView.style.display = 'block';
    resultTextEl.textContent = 'O JOGO TERMINOU! Obrigado por jogar.';
    // Encontrar o score correto para este jogador
    const playerEntry = lista.find(player => player.nickname === nicknameDisplay.textContent);
    if (playerEntry) {
        scoreDisplayEl.textContent = playerEntry.score;
    }
});

// O professor clicou em "Jogar novamente": volta para a tela de espera,
// sem sair da sala (os pontos zeram, o nome continua valendo).
socket.on('game_restarted', () => {
    questionView.style.display = 'none';
    resultView.style.display = 'none';
    joinView.style.display = 'none';
    waitView.style.display = 'block';
    renderScoreHistory(null);
    if (waitMessageEl) {
        waitMessageEl.textContent = 'Aguarde o professor iniciar o jogo...';
    }
    scoreDisplayEl.textContent = '0';
    myLastAnswerIndex = null;
    lastAnsweredQuestionIndex = null;
    allow_answer = false;
    localStorage.removeItem('answerSubmitted');
    localStorage.removeItem('lastAnsweredQuestionIndex');
    localStorage.removeItem('correctOptionIndex');
});
    

socket.on('game_reset', () => {
    alert("O anfitrião saiu. O jogo será reiniciado.");
    localStorage.removeItem('quizSessionToken');
    window.location.reload();
});

// ### Recebe a falha no login ###
socket.on('join_failed', (data) => {
    alert('Falha ao entrar: ' + data.reason);
    // Reabilita o botão para o usuário tentar de novo
    document.getElementById('join-btn').disabled = false;
});