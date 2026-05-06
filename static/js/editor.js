let currentQuizName = "";   // empty string means new quiz
let quizData = { title: "", questions: [] };

const quizSelect = document.getElementById('quiz-select');
const quizTitleInput = document.getElementById('quiz-title');
const questionsContainer = document.getElementById('questions-container');
const newQuizBtn = document.getElementById('new-quiz-btn');
const deleteQuizBtn = document.getElementById('delete-quiz-btn');
const addQuestionBtn = document.getElementById('add-question-btn');
const saveQuizBtn = document.getElementById('save-quiz-btn');

// -------------------- Helper: fetch quizzes list --------------------
async function loadQuizList() {
    const res = await fetch('/api/quizzes');
    const quizzes = await res.json();
    quizSelect.innerHTML = '<option value="">-- Novo Quiz --</option>';
    quizzes.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        quizSelect.appendChild(opt);
    });
}

// -------------------- Load a specific quiz --------------------
async function loadQuiz(quizName) {
    if (!quizName) {
        // new quiz
        currentQuizName = "";
        quizData = { title: "", questions: [] };
        quizTitleInput.value = "";
        renderQuestions();
        return;
    }
    const res = await fetch(`/api/quiz/${encodeURIComponent(quizName)}`);
    if (res.ok) {
        quizData = await res.json();
        currentQuizName = quizName;
        quizTitleInput.value = quizData.title;
        renderQuestions();
    } else {
        alert("Erro ao carregar quiz");
    }
}

// -------------------- Render all questions from quizData --------------------
function renderQuestions() {
    questionsContainer.innerHTML = '';
    quizData.questions.forEach((q, idx) => {
        const qDiv = document.createElement('div');
        qDiv.className = 'question-card';
        qDiv.dataset.index = idx;

        // Header with remove button
        qDiv.innerHTML = `
        <div class="question-header">
            <strong>Pergunta ${idx+1}</strong>
            <button class="remove-question-btn" data-idx="${idx}" style="background:#dc3545;color:white;">Remover</button>
        </div>
        <label>Texto da pergunta:</label>
        <textarea class="question-text" style="width:100%; margin-bottom:10px;" rows="3">${escapeHtml(q.text)}</textarea>
        
        <label>Opções (selecione a correta):</label>
        <ul class="options-list" id="options-list-${idx}"></ul>
        
        <label>Figura (opcional):</label>
        <div>
            <input type="file" class="figure-upload" accept="image/*" data-qidx="${idx}">
            <button class="clear-figure-btn" data-qidx="${idx}" style="background:#6c757d;color:white;">Remover figura</button>
        </div>
        <div class="figure-preview-container" id="fig-preview-${idx}"></div>`;
        questionsContainer.appendChild(qDiv);

        // Render options list
        const optionsList = qDiv.querySelector(`#options-list-${idx}`);
        q.options.forEach((opt, optIdx) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <input type="radio" name="correct_option_${idx}" value="${optIdx}" ${q.correct_option === optIdx ? 'checked' : ''}>
                <textarea class="option-text" style="flex:1; resize:vertical;" rows="1">${escapeHtml(opt)}</textarea>
                <button class="remove-option-btn" data-optidx="${optIdx}" style="background:#dc3545;color:white;">X</button>
            `;
            optionsList.appendChild(li);

            const radio = li.querySelector('input[type="radio"]');
            radio.addEventListener('change', () => {
                if (radio.checked) {
                    quizData.questions[qIdx].correct_option = parseInt(radio.value);
                }
            });
        });
        // Add new option button
        const addOptBtn = document.createElement('button');
        addOptBtn.textContent = '+ Adicionar opção';
        addOptBtn.className = 'add-option-btn';
        addOptBtn.dataset.qidx = idx;
        addOptBtn.style.marginTop = '5px';
        optionsList.parentElement.appendChild(addOptBtn);

        // Preview existing figure
        const previewDiv = qDiv.querySelector(`#fig-preview-${idx}`);
        if (q.figure && q.figure !== "none") {
            previewDiv.innerHTML = `<img src="/static/quiz-figures/${q.figure}" class="figure-preview"><br><small>${q.figure}</small>`;
        } else {
            previewDiv.innerHTML = '<small>Nenhuma figura</small>';
        }

        // Bind events for this question
        bindQuestionEvents(qDiv, idx);
    });
}

function bindQuestionEvents(qDiv, qIdx) {
    // Remove question button
    qDiv.querySelector('.remove-question-btn').addEventListener('click', () => {
        quizData.questions.splice(qIdx, 1);
        renderQuestions();
    });

    // Update question text on change
    const textInput = qDiv.querySelector('.question-text');
    textInput.addEventListener('input', (e) => {
        quizData.questions[qIdx].text = e.target.value;
    });

    // Handle option changes (delegation)
    const optionsList = qDiv.querySelector('.options-list');
    optionsList.addEventListener('input', (e) => {
        if (e.target.classList.contains('option-text')) {
            const li = e.target.closest('li');
            const optIdx = Array.from(optionsList.children).indexOf(li);
            quizData.questions[qIdx].options[optIdx] = e.target.value;
        }
    });
    optionsList.addEventListener('click', (e) => {
        if (e.target.classList.contains('remove-option-btn')) {
            const li = e.target.closest('li');
            const optIdx = Array.from(optionsList.children).indexOf(li);
            quizData.questions[qIdx].options.splice(optIdx, 1);
            // Update correct_option if needed
            if (quizData.questions[qIdx].correct_option >= quizData.questions[qIdx].options.length) {
                quizData.questions[qIdx].correct_option = quizData.questions[qIdx].options.length - 1;
            }
            renderQuestions();  // re-render to refresh indices
        }
    });
    // Add option button
    const addOptBtn = qDiv.querySelector('.add-option-btn');
    addOptBtn.addEventListener('click', () => {
        quizData.questions[qIdx].options.push("");
        renderQuestions();
    });

    // Figure upload
    const fileInput = qDiv.querySelector('.figure-upload');
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const formData = new FormData();
        formData.append('image', file);
        try {
            const res = await fetch('/api/upload_image', { method: 'POST', body: formData });
            const data = await res.json();
            if (res.ok) {
                quizData.questions[qIdx].figure = data.filename;
                renderQuestions(); // refresh to show preview
            } else {
                alert(data.error);
            }
        } catch(err) {
            alert('Upload failed');
        }
    });
    // Clear figure button
    const clearBtn = qDiv.querySelector('.clear-figure-btn');
    clearBtn.addEventListener('click', () => {
        quizData.questions[qIdx].figure = "none";
        renderQuestions();
    });
}

// Helper to escape HTML (prevent injection)
function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/[&<>]/g, function(m) {
        if (m === '&') return '&amp;';
        if (m === '<') return '&lt;';
        if (m === '>') return '&gt;';
        return m;
    }).replace(/[\uD800-\uDBFF][\uDC00-\uDFFF]/g, function(c) {
        return c;
    });
}

// -------------------- Save current quiz --------------------
async function saveQuiz() {
    const newTitle = quizTitleInput.value.trim();
    if (!newTitle) {
        alert("O título do quiz não pode estar vazio.");
        return;
    }
    // Update quizData title
    quizData.title = newTitle;
    // Determine filename: if currentQuizName is empty, use title (sanitized)
    let targetName = currentQuizName;
    if (!targetName) {
        // Sanitize title to be filename-friendly
        targetName = newTitle.replace(/[^a-zA-Z0-9_\-]/g, '_');
        if (targetName.length === 0) targetName = "quiz_" + Date.now();
    }
    const res = await fetch(`/api/quiz/${encodeURIComponent(targetName)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(quizData)
    });
    if (res.ok) {
        alert("Quiz salvo com sucesso!");
        await loadQuizList();
        // Select the saved quiz in dropdown
        quizSelect.value = targetName;
        currentQuizName = targetName;
    } else {
        const err = await res.json();
        alert("Erro ao salvar: " + (err.error || "desconhecido"));
    }
}

// -------------------- Delete quiz --------------------
async function deleteQuiz() {
    if (!currentQuizName) {
        alert("Nenhum quiz selecionado para excluir.");
        return;
    }
    if (!confirm(`Tem certeza que deseja excluir o quiz "${currentQuizName}"?`)) return;
    const res = await fetch(`/api/quiz/${encodeURIComponent(currentQuizName)}`, { method: 'DELETE' });
    if (res.ok) {
        alert("Quiz excluído.");
        currentQuizName = "";
        quizData = { title: "", questions: [] };
        quizTitleInput.value = "";
        renderQuestions();
        await loadQuizList();
        quizSelect.value = "";
    } else {
        alert("Erro ao excluir");
    }
}

// -------------------- New quiz (reset form) --------------------
function newQuiz() {
    currentQuizName = "";
    quizData = { title: "", questions: [] };
    quizTitleInput.value = "";
    renderQuestions();
    quizSelect.value = "";
}

// -------------------- Add empty question --------------------
function addQuestion() {
    quizData.questions.push({
        text: "Nova pergunta",
        options: ["Opção 1", "Opção 2"],
        correct_option: 0,
        figure: "none"
    });
    renderQuestions();
}

// -------------------- Event listeners --------------------
quizSelect.addEventListener('change', (e) => {
    const selected = e.target.value;
    if (selected === "") {
        newQuiz();
    } else {
        loadQuiz(selected);
    }
});

// -------------------- Exportar Quiz --------------------
async function exportQuiz() {
    // Sincroniza o título com o campo de input
    quizData.title = quizTitleInput.value.trim();
    if (!quizData.title) {
        alert("O quiz precisa ter um título antes de ser exportado.");
        return;
    }

    try {
        const response = await fetch('/api/quiz/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(quizData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Erro na exportação');
        }

        // Obtém o blob e dispara o download
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        // Nome do arquivo: título do quiz (sanitizado) + .quiz
        let safeTitle = quizData.title.replace(/[^a-zA-Z0-9_\-]/g, '_');
        a.download = `${safeTitle}.quiz`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (err) {
        alert(`Falha ao exportar: ${err.message}`);
    }
}

// -------------------- Importar Quiz --------------------
function importQuiz() {
    const fileInput = document.getElementById('import-file-input');
    fileInput.value = ''; // permite reimportar o mesmo arquivo
    fileInput.click();
}

document.getElementById('import-file-input').addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/quiz/import', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Erro na importação');
        }

        // Substitui o quiz atual pelos dados importados
        currentQuizName = data.quiz_name;
        quizData = data.quiz_data;
        quizTitleInput.value = quizData.title;
        renderQuestions();

        // Atualiza a lista de quizzes no dropdown
        await loadQuizList();
        // Seleciona o quiz recém-importado
        quizSelect.value = currentQuizName;

        alert(`Quiz "${quizData.title}" importado com sucesso!`);
    } catch (err) {
        alert(`Erro ao importar: ${err.message}`);
    }
});

// Adiciona os event listeners dos novos botões
document.getElementById('export-quiz-btn').addEventListener('click', exportQuiz);
document.getElementById('import-quiz-btn').addEventListener('click', importQuiz);
newQuizBtn.addEventListener('click', newQuiz);
deleteQuizBtn.addEventListener('click', deleteQuiz);
addQuestionBtn.addEventListener('click', addQuestion);
saveQuizBtn.addEventListener('click', saveQuiz);

// Initial load
loadQuizList();
newQuiz();  // start empty