const startBtn = document.getElementById('start-game-btn');
const playerListEl = document.getElementById('player-list');

const forceEndBtn = document.getElementById('force-end-btn');
const forceEndQuestionBtn = document.getElementById('force-end-question-btn');
const forceEndResultsBtn = document.getElementById('force-end-results-btn');


const lobbyView = document.getElementById('lobby');
const questionView = document.getElementById('question-view');
const resultsView = document.getElementById('results-view');
const gameOverView = document.getElementById('game-over-view');

const questionTextEl = document.getElementById('question-text');
const answerCountEl = document.getElementById('answer-count');
const totalPlayersEl = document.getElementById('total-players');

const correctTextEl = document.getElementById('correct-answer-text');
const scoreListEl = document.getElementById('score-list');
const finalScoreListEl = document.getElementById('final-score-list');

const quizSelect = document.getElementById('quiz-select');
const chartImg = document.getElementById('question-chart');

const STATE_LOBBY 	    = 0;
const STATE_QUESTION    = 1;
const STATE_ANSWER 	    = 2;
const STATE_GAMEOVER 	= 3;

const QUESTION_DURATION = 30;

let answering = false;

let currentQuestionData = null; // stores text, options, chart_path, index, total
// Avisa o servidor que esta é a tela do host
socket.emit('host_join');

lobbyView.style.display = 'block';

function renderMath() {
    if (window.MathJax && typeof MathJax.typesetPromise === 'function') {
        MathJax.typesetPromise().catch(err => console.warn('MathJax error:', err));
    }
}

async function loadQuizList() {
    const res = await fetch('/api/quizzes');
    const quizzes = await res.json();
    quizSelect.innerHTML = '<option value="">-- Selecionar Quiz --</option>';
    quizzes.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        quizSelect.appendChild(opt);
    });
}

// Atualiza a lista de jogadores no lobby
socket.on('update_player_list', (players) => {
    //lobbyView.style.display='block'
    playerListEl.innerHTML = '';
    players.forEach(name => {
        const li = document.createElement('li');
        li.textContent = name;
        playerListEl.appendChild(li);
    });
    startBtn.textContent = `Iniciar Jogo (${players.length} Jogadores)`;
    startBtn.disabled = players.length === 0;

    forceEndBtn.style.display = players.length > 0 ? 'block' : 'none';

});

// Função para finalizar o quiz
function forceEndQuiz() {
    if (confirm('Tem certeza que deseja finalizar o quiz? Isso mostrará o placar final imediatamente.')) {
        socket.emit('force_end_quiz');
    }
}

// Event listeners para os botões de finalizar
forceEndBtn.addEventListener('click', forceEndQuiz);
forceEndQuestionBtn.addEventListener('click', forceEndQuiz);
forceEndResultsBtn.addEventListener('click', forceEndQuiz);

// Iniciar Jogo
startBtn.addEventListener('click', (e) => {
const selectedValue = quizSelect.value;

if (selectedValue === "") {
    alert('Selecione um quiz válido!');
} else {
    socket.emit('start_game', {'quiz-name' : quizSelect.value});
}
});

function stopAnswerTimer() {
    if (answerTimerUpdateInterval) {
        clearInterval(answerTimerUpdateInterval);
        answerTimerUpdateInterval = null;
    }
    if (answerTimerNotification) {
        answerTimerNotification.remove();
        answerTimerNotification = null;
    }
    answerTimerStartTime = null;
    answering = false;
}

// Mostra a pergunta
socket.on('show_question', (data) => {
    console.log("show_question triggered.");
    console.log(data);
    
    lobbyView.style.display = 'none';
    resultsView.style.display = 'none';
    questionView.style.display = 'block';

    let remaining_time = data.remaining_time;
    if (remaining_time == null){
        answering = false;
        hideAnswerTimerNotification();
    }
    else{
        answering = true;
        
        if (remaining_time<0) {
            socket.emit('show_results')
            return;
        } else {
            console.log(remaining_time);
            showAnswerTimerWithRemaining(remaining_time);
        }
    }
        



    console.log(data.chart_path);
    if (data.chart_path === "")
        chartImg.style.display = 'none';
    else{ 
        chartImg.src = data.chart_path + '?t=' + new Date().getTime();
        chartImg.style.display = 'block';
    }

    questionTextEl.textContent = `(${data.question_index + 1}/${data.total_questions}) ${data.text}`;

    renderMath();
    const optionsContainerId = 'options-list-host';
    let optionsContainer = document.getElementById(optionsContainerId);
    

    if (optionsContainer && optionsContainer.style.display === 'grid') {
        optionsContainer.style.display = 'none';
        hideAnswerTimerNotification();  
    } else if (optionsContainer) {
        optionsContainer.style.display = 'none';
    }
    if (!optionsContainer) {
        optionsContainer = document.createElement('div');
        optionsContainer.id = optionsContainerId;
        optionsContainer.classList.add('grid-options');
        chartImg.insertAdjacentElement('afterend', optionsContainer);
    }

    if (answering) {
        optionsContainer.style.display = 'grid';
    } else
    {
        optionsContainer.style.display = 'none';
    }
    // Store for later reuse (results view)
    currentQuestionData = {
        text: data.text,
        options: data.options,
        chart_path: data.chart_path,
        question_index: data.question_index,
        total_questions: data.total_questions
    };

});

let answerTimerNotification = null;
let answerTimerUpdateInterval = null;
let answerTimerStartTime = null;

function showAnswerTimerNotification() {
    // Remove existing notification if any
    if (answerTimerNotification) {
        answerTimerNotification.remove();
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.id = 'answer-timer-notification';
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #2196F3;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 3rem;
        font-weight: bold;
        z-index: 1000;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: monospace;
    `;
    notification.textContent = '⏱️ 30s';
    document.body.appendChild(notification);
    answerTimerNotification = notification;
    
    // Start timer updates
    answerTimerStartTime = Date.now();
    if (answerTimerUpdateInterval) clearInterval(answerTimerUpdateInterval);
    answerTimerUpdateInterval = setInterval(() => {
        if (answerTimerNotification) {
            const elapsed = Math.floor((Date.now() - answerTimerStartTime) / 1000);
            answerTimerNotification.textContent = `⏱️ ${QUESTION_DURATION - elapsed}s`;
            if (QUESTION_DURATION-elapsed ==0){
                socket.emit('show_results')   
            }
        }
    }, 1000);
}

function showAnswerTimerWithRemaining(remainingSeconds) {
    console.log("showAnswerTimerWithRemaining", remainingSeconds);
    const totalSeconds = Math.ceil(remainingSeconds); // arredonda pra cima
    const notification = document.createElement('div');
    notification.id = 'answer-timer-notification';
    notification.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #2196F3;
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 3rem;
        font-weight: bold;
        z-index: 1000;
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        font-family: monospace;
    `;
    notification.textContent = `⏱️ ${totalSeconds}s`;
    document.body.appendChild(notification);
    answerTimerNotification = notification;

    let secondsLeft = totalSeconds;
    answerTimerUpdateInterval = setInterval(() => {
        secondsLeft--;
        if (secondsLeft <= 0) {
            clearInterval(answerTimerUpdateInterval);
            if (answerTimerNotification) answerTimerNotification.remove();
            socket.emit('show_results');
        } else {
            if (answerTimerNotification)
                answerTimerNotification.textContent = `⏱️ ${secondsLeft}s`;
        }
    }, 1000);
}
function hideAnswerTimerNotification() {
    if (answerTimerUpdateInterval) {
        clearInterval(answerTimerUpdateInterval);
        answerTimerUpdateInterval = null;
    }
    if (answerTimerNotification) {
        answerTimerNotification.remove();
        answerTimerNotification = null;
    }
    answerTimerStartTime = null;
}

socket.on('answer_allowed', (data) => {
    console.log("Triggered answer_allowed.\n Options:")
    console.log(currentQuestionData.options);
    // Exibe as opções completas
    const optionsContainerId = 'options-list-host';
    
    let optionsContainer = document.getElementById(optionsContainerId);
    
    optionsContainer.innerHTML = '';
    currentQuestionData.options.forEach((opt, i) => {
        const btn = document.createElement('div');
        btn.classList.add('option-btn');
        btn.textContent = `${String.fromCharCode(65 + i)}) ${opt}`;
        optionsContainer.appendChild(btn);
    });
    optionsContainer.style.display = "grid";
    renderMath();
    showAnswerTimerNotification();
});


// Atualiza a contagem de respostas
socket.on('update_answer_count', (data) => {
    answerCountEl.textContent = data.answered;
    totalPlayersEl.textContent = data.total;

    if (data.answered === data.total && data.total > 0) {
        if (resultsView.style.display !== 'block') {
            console.log('All players answered. Auto‑showing results.');
            socket.emit('show_results');
        }
    }
});

// Botão de Mostrar Resultados
document.getElementById('show-results-btn').addEventListener('click', () => {
    socket.emit('show_results');
});

// Mostra os resultados da pergunta
socket.on('show_results', (data) => {
    hideAnswerTimerNotification();
    questionView.style.display = 'none';
    
    correctTextEl.textContent = data.correct_option_text;

    renderMath();
    
    // Atualiza a imagem do gráfico gerado pelo Python
    const chartImg = document.getElementById('results-chart');
    chartImg.src = data.chart_path + '?t=' + new Date().getTime(); // força atualização
    resultsView.style.display = 'block';

});


// Botão de Próxima Pergunta
document.getElementById('next-question-btn').addEventListener('click', () => {
    socket.emit('next_question');
});

// Fim de jogo
socket.on('game_over', (leaderboard) => { // Recebe o placar ordenado (decrescente)
    resultsView.style.display = 'none';
    gameOverView.style.display = 'block';
    lobbyView.style.display = 'none';
    forceEndBtn.style.display = 'none'; // Esconde o botão no lobby

    finalScoreListEl.innerHTML = '';

    if (leaderboard.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'Nenhum jogador participou.';
        finalScoreListEl.appendChild(li);
        return;
    }

    // --- INÍCIO DA LÓGICA DO TOP 3 COM EMPATE ---
    // Encontra a pontuação mínima dentro do top 3
    const thirdScore = leaderboard.length >= 3 ? leaderboard[2].score : leaderboard[leaderboard.length - 1].score;

    // Inclui todos os jogadores com pontuação >= à do 3º colocado
    const topPlayers = leaderboard.filter(p => p.score >= thirdScore);

    // Emojis de medalha (serão atribuídos apenas aos 3 melhores, mesmo que haja empate)
    const medals = ['🥇', '🥈', '🥉'];

    topPlayers.forEach((player, index) => {
        const li = document.createElement('li');

        // Medalha só para os 3 primeiros distintos
        if (index < 3) {
            li.textContent = `${medals[index]} ${player.nickname}: ${player.score} pontos`;
        } else {
            li.textContent = `${player.nickname}: ${player.score} pontos`;
        }

        // Cores e estilos conforme posição
        if (player.score === leaderboard[0].score) {
            li.style.fontWeight = 'bold';
            li.style.fontSize = '1.2em';
            li.style.backgroundColor = '#fff3cd'; // Ouro
        } else if (player.score === leaderboard[1]?.score) {
            li.style.backgroundColor = '#e2e3e5'; // Prata
        } else if (player.score === leaderboard[2]?.score) {
            li.style.backgroundColor = '#ffe8cc'; // Bronze
        }

        finalScoreListEl.appendChild(li);
    });
});


// Alguém saiu
socket.on('player_left', (data) => {
    // Apenas recarrega a lista de jogadores (a lógica completa está no servidor)
    socket.emit('host_join');
});

socket.on('game_reset', () => {
    alert("O Jogo foi resetado!");
    window.location.reload();
});

// Add this to your existing socket.on handlers section

// Handle resume_host_state to restore the host screen
socket.on('resume_host_state', (data) => {
    console.log('Restoring host state:', data);
    console.log('remaining_time type/value:', data.remaining_time, typeof data.remaining_time);
    const gameState = data.state;
    const currentQuestion = data.current_question;
    const question_data = data.question_data;
    const totalPlayers = data.total_players;
    const answeredCount = data.answered_count;

    currentQuestionData = {
        text: question_data.text,
        options: question_data.options,
        chart_path: question_data.chart_path,
        question_index: data.question_index,
        total_questions: data.total_questions
    };

    console.log(currentQuestionData);
    
    // First, hide all views
    lobbyView.style.display = 'none';
    questionView.style.display = 'none';
    resultsView.style.display = 'none';
    gameOverView.style.display = 'none';

    // Restore timer for STATE_QUESTION
    if (gameState === STATE_QUESTION && data.remaining_time !== null && data.remaining_time > 0) {
        //hideAnswerTimerNotification();

        // 1. Mostra o timer com o tempo restante (arredondado)
        //showAnswerTimerWithRemaining(data.remaining_time);

        // 2. Restaura o texto da pergunta
        const questionTextEl = document.getElementById('question-text');
        if (questionTextEl && currentQuestionData) {
            questionTextEl.textContent = `(${currentQuestionData.question_index + 1}/${currentQuestionData.total_questions}) ${currentQuestionData.text}`;
            renderMath(); // se houver MathJax
        }

        // 3. Restaura o gráfico da pergunta
        const chartImg = document.getElementById('question-chart');
        if (chartImg && currentQuestionData.chart_path && currentQuestionData.chart_path !== "") {
            chartImg.src = currentQuestionData.chart_path + '?t=' + Date.now();
            chartImg.style.display = 'block';
        } else if (chartImg) {
            chartImg.style.display = 'none';
        }

        // 4. Garante que o container de opções exista, seja preenchido e fique visível
        let optionsContainer = document.getElementById('options-list-host');
        if (!optionsContainer) {
            optionsContainer = document.createElement('div');
            optionsContainer.id = 'options-list-host';
            optionsContainer.classList.add('grid-options');
            const ref = document.getElementById('question-chart') || document.getElementById('question-text');
            if (ref) ref.insertAdjacentElement('afterend', optionsContainer);
        }
        optionsContainer.innerHTML = '';
        currentQuestionData.options.forEach((opt, i) => {
            const btn = document.createElement('div');
            btn.classList.add('option-btn');
            btn.textContent = `${String.fromCharCode(65 + i)}) ${opt}`;
            optionsContainer.appendChild(btn);
        });
        optionsContainer.style.display = 'grid';
    } 
    else if (gameState !== STATE_QUESTION) {
        hideAnswerTimerNotification();
    }
    
    // Restore based on game state
    switch(gameState) {
        case STATE_LOBBY:
            lobbyView.style.display = 'block';
            // Force end button visibility based on players
            if (forceEndBtn && totalPlayers > 0) {
                forceEndBtn.style.display = 'block';
            }
            break;
            
        case STATE_QUESTION:
            questionView.style.display = 'block';
            // Update answer counts
            if (answerCountEl && totalPlayersEl) {
                answerCountEl.textContent = answeredCount;
                totalPlayersEl.textContent = totalPlayers;
            }
            // The show_question event will be sent separately by the server
            // So we don't need to request it again
            break;
            
        case STATE_ANSWER:
            resultsView.style.display = 'block';
            // The show_results event will be sent separately by the server
            break;
            
        case STATE_GAMEOVER:
            gameOverView.style.display = 'block';
            break;
            
        default:
            console.warn('Unknown game state:', gameState);
            lobbyView.style.display = 'none';
            break;
    }
    
    // Show force end button in appropriate views if there are players
    if (forceEndBtn && totalPlayers > 0 && gameState !== 'game_over') {
        forceEndBtn.style.display = 'block';
    }
    if (forceEndQuestionBtn && questionView.style.display === 'block') {
        forceEndQuestionBtn.style.display = 'block';
    }
    if (forceEndResultsBtn && resultsView.style.display === 'block') {
        forceEndResultsBtn.style.display = 'block';
    }
});

// Handle host_reconnected message (optional but nice)
socket.on('host_reconnected', (data) => {
    // Show a temporary notification that host is back
    const notification = document.createElement('div');
    notification.textContent = data.message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background-color: #4CAF50;
        color: white;
        padding: 15px;
        border-radius: 5px;
        z-index: 1000;
        animation: fadeOut 3s forwards;
    `;
    document.body.appendChild(notification);
    
    // Add fade out animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeOut {
            0% { opacity: 1; }
            70% { opacity: 1; }
            100% { opacity: 0; display: none; }
        }
    `;
    document.head.appendChild(style);
    
    // Remove notification after animation
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 3000);
});

    // Modal elements
const modal = document.getElementById('question-modal');
const modalQuestionText = document.getElementById('modal-question-text');
const modalChart = document.getElementById('modal-chart');
const modalOptions = document.getElementById('modal-options');
const closeModalBtn = document.getElementById('close-modal-btn');

// Show modal with stored question data
function showQuestionAgain() {
    if (!currentQuestionData) {
        alert("Nenhuma pergunta disponível para mostrar novamente.");
        return;
    }

    // Fill modal content
    modalQuestionText.textContent = `(${currentQuestionData.question_index + 1}/${currentQuestionData.total_questions}) ${currentQuestionData.text}`;
    
    // Chart (add timestamp to avoid caching)
    if (currentQuestionData.chart_path && currentQuestionData.chart_path !== "") {
        modalChart.src = currentQuestionData.chart_path + '?t=' + new Date().getTime();
        modalChart.style.display = 'block';
    } else {
        modalChart.style.display = 'none';
    }

    // Options
    modalOptions.innerHTML = '';
    currentQuestionData.options.forEach((opt, i) => {
        const optDiv = document.createElement('div');
        optDiv.classList.add('option-btn');
        optDiv.textContent = `${String.fromCharCode(65 + i)}) ${opt}`;
        modalOptions.appendChild(optDiv);
    });

    // Show modal
    modal.style.display = 'flex';

    renderMath();   
}

// Close modal
closeModalBtn.addEventListener('click', () => {
    modal.style.display = 'none';
});

// Click outside modal to close (optional)
modal.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
});

// Attach button listener
document.getElementById('show-question-again-btn').addEventListener('click', showQuestionAgain);

    loadQuizList();
