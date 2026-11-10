const joinView = document.getElementById('join-view');
const waitView = document.getElementById('wait-view');
const questionView = document.getElementById('question-view');
const resultView = document.getElementById('result-view');

const nicknameInput = document.getElementById('nickname-input');
const nicknameDisplay = document.getElementById('nickname-display');
const teamSelect = document.getElementById('team-select');
const teamDisplay = document.getElementById('team-display');
const teamResultDisplay = document.getElementById('team-result-display');
const optionsGrid = document.getElementById('options-grid');
const questionTextEl = document.getElementById('question-text');
const resultTextEl = document.getElementById('result-text');
const scoreDisplayEl = document.getElementById('score-display');
const waitMessageEl = document.getElementById('wait-message');
const teamLineEl = document.getElementById('team-line');

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
                waitView.style.display = 'block';
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


// Entrar no Jogo
const joinBtn = document.getElementById('join-btn'); // Pega o botão

joinBtn.addEventListener('click', () => {
    const nickname = nicknameInput.value.trim(); // Usa .trim()

    // No modo time, o aluno precisa escolher onde vai competir
    let team = null;
    if (teamMode) {
        team = teamSelect ? teamSelect.value : '';
        if (!team) {
            alert('Escolha o seu time (Time A ou Time B) para entrar!');
            if (teamSelect) teamSelect.focus();
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

// Preenche o seletor de times com os nomes que o servidor informou
function renderTeamOptions(teams) {
    if (!teamSelect) return;
    const selecionado = teamSelect.value;
    const mapa = teams || { A: 'Time A', B: 'Time B' };

    teamSelect.innerHTML = '<option value="">Selecione seu time</option>';
    Object.keys(mapa).forEach((key) => {
        const opt = document.createElement('option');
        opt.value = key;
        opt.textContent = mapa[key];
        teamSelect.appendChild(opt);
    });

    if (selecionado) teamSelect.value = selecionado;
    teamSelect.style.display = teamMode ? 'block' : 'none';
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
    if (teamSelect) teamSelect.style.display = teamMode ? 'block' : 'none';

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