let currentClass = "";    // slug da turma aberta no editor
let currentQuizName = "";   // empty string means new quiz
let quizData = { title: "", questions: [] };

const classSelect = document.getElementById('class-select');
const quizSelect = document.getElementById('quiz-select');
const quizTitleInput = document.getElementById('quiz-title');
const questionsContainer = document.getElementById('questions-container');
const newQuizBtn = document.getElementById('new-quiz-btn');
const deleteQuizBtn = document.getElementById('delete-quiz-btn');
const addQuestionBtn = document.getElementById('add-question-btn');
const saveQuizBtn = document.getElementById('save-quiz-btn');

// -------------------- Helpers de API (por turma) --------------------
function classQuizUrl(quizName) {
    return `/api/classes/${encodeURIComponent(currentClass)}/quiz/${encodeURIComponent(quizName)}`;
}

// -------------------- Carrega as turmas e a lista de quizzes --------------------
async function loadClasses() {
    const res = await fetch('/api/classes');
    const data = await res.json();
    const turmas = data.classes || [];

    classSelect.innerHTML = '';
    turmas.forEach(c => {
        const opt = document.createElement('option');
        opt.value = c.slug;
        opt.textContent = `${c.name} (${c.students} aluno${c.students === 1 ? '' : 's'})`;
        classSelect.appendChild(opt);
    });

    const previous = currentClass;
    const existente = turmas.some(c => c.slug === previous);
    currentClass = existente ? previous : (turmas[0] ? turmas[0].slug : '');
    classSelect.value = currentClass;

    newQuiz();
    await loadQuizList();
}

// -------------------- Helper: fetch quizzes list --------------------
async function loadQuizList() {
    quizSelect.innerHTML = '<option value="">-- Novo Quiz --</option>';
    if (!currentClass) return;

    const res = await fetch(`/api/classes/${encodeURIComponent(currentClass)}/quizzes`);
    const quizzes = await res.json();
    if (!Array.isArray(quizzes)) return;

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
    const res = await fetch(classQuizUrl(quizName));
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

        // Header with preview/remove buttons
        qDiv.innerHTML = `
        <div class="question-header">
            <strong>Pergunta ${idx+1}</strong>
            <div class="question-header-actions">
                <button class="preview-question-btn" data-idx="${idx}" style="background:#6f42c1;color:white;">👁 Pré-visualizar</button>
                <button class="remove-question-btn" data-idx="${idx}" style="background:#dc3545;color:white;">Remover</button>
            </div>
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
                    quizData.questions[idx].correct_option = parseInt(radio.value);
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
    // Pré-visualização apenas desta questão
    qDiv.querySelector('.preview-question-btn').addEventListener('click', () => {
        previewQuestion(qIdx);
    });

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
    const res = await fetch(classQuizUrl(targetName), {
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
    const res = await fetch(classQuizUrl(currentQuizName), { method: 'DELETE' });
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

classSelect.addEventListener('change', async () => {
    currentClass = classSelect.value;
    newQuiz();
    await loadQuizList();
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
    formData.append('class', currentClass);

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

// -------------------- Pré-visualização --------------------
// mode: 'single' (só a questão clicada) ou 'quiz' (percorre o quiz inteiro)
let previewIndex = 0;
let previewSingle = false;

const previewModal = document.getElementById('preview-modal');
const previewCounter = document.getElementById('preview-counter');
const previewQuestionText = document.getElementById('preview-question-text');
const previewFigure = document.getElementById('preview-figure');
const previewOptions = document.getElementById('preview-options');
const previewPrevBtn = document.getElementById('preview-prev-btn');
const previewNextBtn = document.getElementById('preview-next-btn');
const previewNav = document.querySelector('.preview-nav');

function openPreview(startIndex, mode) {
    const total = quizData.questions ? quizData.questions.length : 0;
    if (total === 0) {
        alert("O quiz não tem perguntas para pré-visualizar.");
        return;
    }

    previewSingle = (mode === 'single');
    previewIndex = Math.max(0, Math.min(startIndex, total - 1));

    // No modo "single" não há navegação entre perguntas
    previewNav.style.display = previewSingle ? 'none' : 'flex';

    renderPreview();
    previewModal.classList.add('open');
    typesetPreview();   // o modal precisa estar visível para o MathJax medir
}

// Pré-visualização do quiz inteiro (a partir da primeira questão)
function previewQuiz() {
    openPreview(0, 'quiz');
}

// Pré-visualização de uma única questão
function previewQuestion(idx) {
    openPreview(idx, 'single');
}

function renderPreview() {
    const total = quizData.questions.length;
    const q = quizData.questions[previewIndex];
    if (!q) return;

    previewCounter.textContent = previewSingle
        ? `Pré-visualização – Pergunta ${previewIndex + 1} de ${total}`
        : `Quiz completo – Pergunta ${previewIndex + 1} de ${total}`;

    previewQuestionText.textContent = q.text || '(sem texto)';

    if (q.figure && q.figure !== 'none') {
        previewFigure.src = `/static/quiz-figures/${q.figure}`;
        previewFigure.style.display = 'block';
    } else {
        previewFigure.removeAttribute('src');
        previewFigure.style.display = 'none';
    }

    previewOptions.innerHTML = '';
    (q.options || []).forEach((opt, i) => {
        const div = document.createElement('div');
        div.className = 'preview-option' + (q.correct_option === i ? ' correct' : '');

        const letter = document.createElement('span');
        letter.className = 'preview-letter';
        letter.textContent = `${String.fromCharCode(65 + i)})`;

        div.appendChild(letter);
        div.appendChild(document.createTextNode(opt || ''));
        previewOptions.appendChild(div);
    });

    previewPrevBtn.disabled = previewIndex === 0;
    previewNextBtn.disabled = previewIndex === total - 1;
}

// O MathJax processa o documento uma única vez, quando a página carrega.
// Como o conteúdo do preview é criado depois (e trocado a cada pergunta),
// é preciso pedir para reprocessá-lo manualmente.
function typesetPreview() {
    if (!window.MathJax) return;

    const ready = (MathJax.startup && MathJax.startup.promise)
        ? MathJax.startup.promise
        : Promise.resolve();

    ready.then(() => {
        if (typeof MathJax.typesetPromise !== 'function') return;
        if (typeof MathJax.typesetClear === 'function') {
            MathJax.typesetClear([previewModal]);
        }
        return MathJax.typesetPromise([previewModal]);
    }).catch(err => console.warn('MathJax error:', err));
}

function closePreview() {
    previewModal.classList.remove('open');
}

previewPrevBtn.addEventListener('click', () => {
    if (previewIndex > 0) { previewIndex--; renderPreview(); typesetPreview(); }
});
previewNextBtn.addEventListener('click', () => {
    if (previewIndex < quizData.questions.length - 1) { previewIndex++; renderPreview(); typesetPreview(); }
});
document.getElementById('preview-close-btn').addEventListener('click', closePreview);
document.getElementById('preview-quiz-btn').addEventListener('click', previewQuiz);

// Fecha ao clicar no fundo; Esc fecha sempre, setas só no modo "quiz"
previewModal.addEventListener('click', (e) => {
    if (e.target === previewModal) closePreview();
});
document.addEventListener('keydown', (e) => {
    if (!previewModal.classList.contains('open')) return;
    if (e.key === 'Escape') { closePreview(); return; }
    if (previewSingle) return;
    if (e.key === 'ArrowLeft') previewPrevBtn.click();
    else if (e.key === 'ArrowRight') previewNextBtn.click();
});

// -------------------- Turmas --------------------
const classModal = document.getElementById('class-modal');
const classModalTitle = document.getElementById('class-modal-title');
const classNameInput = document.getElementById('class-name-input');
let classModalAction = 'create';

function currentClassName() {
    const opt = classSelect.options[classSelect.selectedIndex];
    return opt ? opt.textContent.replace(/ \(\d+ alunos?\)$/, '') : '';
}

function openClassModal(action) {
    if (action === 'rename' && !currentClass) {
        alert('Selecione uma turma para renomear.');
        return;
    }

    classModalAction = action;
    classModalTitle.textContent = action === 'create' ? 'Nova turma' : 'Renomear turma';
    classNameInput.value = action === 'create' ? '' : currentClassName();
    classModal.classList.add('open');
    classNameInput.focus();
    classNameInput.select();
}

function closeClassModal() {
    classModal.classList.remove('open');
}

async function submitClassModal() {
    const name = classNameInput.value.trim();
    if (!name) {
        alert('Informe o nome da turma.');
        return;
    }

    const criar = classModalAction === 'create';
    const url = criar
        ? '/api/classes'
        : `/api/classes/${encodeURIComponent(currentClass)}`;

    const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    });
    const data = await res.json();
    if (!res.ok) {
        alert(`Erro ao ${criar ? 'criar' : 'renomear'} a turma: ` + (data.error || 'desconhecido'));
        return;
    }

    if (criar) currentClass = data.slug;
    closeClassModal();
    await loadClasses();
}

async function deleteClass() {
    if (!currentClass) return;

    const nome = currentClassName();
    if (!confirm(`Excluir a turma "${nome}" e TODOS os quizzes dela?`)) return;

    const res = await fetch(`/api/classes/${encodeURIComponent(currentClass)}`, {
        method: 'DELETE'
    });
    const data = await res.json();
    if (!res.ok) {
        alert('Erro ao excluir turma: ' + (data.error || 'desconhecido'));
        return;
    }

    currentClass = '';
    await loadClasses();
}

document.getElementById('new-class-btn').addEventListener('click', () => openClassModal('create'));
document.getElementById('rename-class-btn').addEventListener('click', () => openClassModal('rename'));
document.getElementById('delete-class-btn').addEventListener('click', deleteClass);
document.getElementById('class-save-btn').addEventListener('click', submitClassModal);
document.getElementById('class-cancel-btn').addEventListener('click', closeClassModal);
document.getElementById('class-close-btn').addEventListener('click', closeClassModal);
classNameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') submitClassModal();
});
classModal.addEventListener('click', (e) => {
    if (e.target === classModal) closeClassModal();
});

// -------------------- Copiar quiz de outra turma --------------------
const copyModal = document.getElementById('copy-modal');
const copySrcClass = document.getElementById('copy-src-class');
const copySrcQuiz = document.getElementById('copy-src-quiz');
const copyNewName = document.getElementById('copy-new-name');
const copyConfirmBtn = document.getElementById('copy-confirm-btn');

let quizzesByClass = {};

function refreshCopyQuizzes() {
    const quizzes = quizzesByClass[copySrcClass.value] || [];
    copySrcQuiz.innerHTML = '';

    quizzes.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        copySrcQuiz.appendChild(opt);
    });

    copyNewName.value = quizzes.length ? quizzes[0] : '';
    copyConfirmBtn.disabled = quizzes.length === 0;
}

async function openCopyModal() {
    if (!currentClass) {
        alert('Selecione a turma de destino.');
        return;
    }

    const [resAll, resClasses] = await Promise.all([
        fetch('/api/quizzes-by-class'),
        fetch('/api/classes')
    ]);
    quizzesByClass = await resAll.json();
    const dataClasses = await resClasses.json();

    copySrcClass.innerHTML = '';
    (dataClasses.classes || []).forEach(c => {
        if (c.slug === currentClass) return;   // não faz sentido copiar para a mesma turma
        const opt = document.createElement('option');
        opt.value = c.slug;
        opt.textContent = c.name;
        copySrcClass.appendChild(opt);
    });

    if (!copySrcClass.options.length) {
        alert('Não há outra turma cadastrada para copiar quizzes.');
        return;
    }

    refreshCopyQuizzes();
    copyModal.classList.add('open');
}

async function confirmCopy() {
    const quizOrigem = copySrcQuiz.value;
    if (!quizOrigem) return;

    const res = await fetch(`/api/classes/${encodeURIComponent(currentClass)}/copy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            from_class: copySrcClass.value,
            quiz_name: quizOrigem,
            new_name: copyNewName.value.trim() || quizOrigem
        })
    });
    const data = await res.json();
    if (!res.ok) {
        alert('Erro ao copiar: ' + (data.error || 'desconhecido'));
        return;
    }

    copyModal.classList.remove('open');
    await loadQuizList();
    quizSelect.value = data.quiz_name;
    await loadQuiz(data.quiz_name);
    alert(`Quiz copiado como "${data.quiz_name}".`);
}

document.getElementById('copy-quiz-btn').addEventListener('click', openCopyModal);
document.getElementById('copy-close-btn').addEventListener('click', () => copyModal.classList.remove('open'));
copySrcClass.addEventListener('change', refreshCopyQuizzes);
copySrcQuiz.addEventListener('change', () => { copyNewName.value = copySrcQuiz.value; });
copyConfirmBtn.addEventListener('click', confirmCopy);
copyModal.addEventListener('click', (e) => { if (e.target === copyModal) copyModal.classList.remove('open'); });

// Initial load
loadClasses();