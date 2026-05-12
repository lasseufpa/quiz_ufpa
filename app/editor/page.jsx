"use client";

import { useRef, useEffect, useState } from 'react';

function emptyQuestion() {
  return {
    text: 'Nova pergunta',
    options: ['Opção 1', 'Opção 2'],
    correct_option: 0,
    figure: 'none'
  };
}

export default function EditorPage() {
  const [quizName, setQuizName] = useState('');
  const [quizList, setQuizList] = useState([]);
  const [currentQuiz, setCurrentQuiz] = useState({ title: '', questions: [] });
  const [currentName, setCurrentName] = useState('');
  const importInputRef = useRef(null);

  useEffect(() => {
    loadQuizList();
    loadQuiz('');
  }, []);

  async function loadQuizList() {
    const response = await fetch('/api/quizzes');
    const data = await response.json();
    setQuizList(data);
  }

  async function loadQuiz(name) {
    if (!name) {
      setCurrentName('');
      setCurrentQuiz({ title: '', questions: [] });
      setQuizName('');
      return;
    }

    const response = await fetch(`/api/quiz/${encodeURIComponent(name)}`);
    if (!response.ok) {
      alert('Erro ao carregar quiz');
      return;
    }

    const data = await response.json();
    setCurrentName(name);
    setCurrentQuiz(data);
    setQuizName(data.title || '');
  }

  function updateQuestion(index, updater) {
    setCurrentQuiz((previous) => {
      const questions = previous.questions.map((question, questionIndex) => (
        questionIndex === index ? updater({ ...question }) : question
      ));
      return { ...previous, questions };
    });
  }

  function addQuestion() {
    setCurrentQuiz((previous) => ({
      ...previous,
      questions: [...previous.questions, emptyQuestion()]
    }));
  }

  function removeQuestion(index) {
    setCurrentQuiz((previous) => ({
      ...previous,
      questions: previous.questions.filter((_, questionIndex) => questionIndex !== index)
    }));
  }

  async function uploadFigure(file, questionIndex) {
    const formData = new FormData();
    formData.append('image', file);

    const response = await fetch('/api/upload_image', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || 'Falha no upload');
      return;
    }

    updateQuestion(questionIndex, (question) => {
      question.figure = data.filename;
      return question;
    });
  }

  async function saveQuiz() {
    const title = quizName.trim();
    if (!title) {
      alert('O título do quiz não pode estar vazio.');
      return;
    }

    const payload = {
      title,
      questions: currentQuiz.questions
    };

    const targetName = currentName || title.replace(/[^a-zA-Z0-9_-]/g, '_') || `quiz_${Date.now()}`;
    const response = await fetch(`/api/quiz/${encodeURIComponent(targetName)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || 'Erro ao salvar quiz');
      return;
    }

    await loadQuizList();
    setCurrentName(data.name || targetName);
    alert('Quiz salvo com sucesso!');
  }

  async function deleteQuiz() {
    if (!currentName) {
      alert('Nenhum quiz selecionado para excluir.');
      return;
    }

    if (!window.confirm(`Tem certeza que deseja excluir o quiz "${currentName}"?`)) {
      return;
    }

    const response = await fetch(`/api/quiz/${encodeURIComponent(currentName)}`, { method: 'DELETE' });
    if (!response.ok) {
      alert('Erro ao excluir quiz');
      return;
    }

    await loadQuizList();
    loadQuiz('');
  }

  async function exportQuiz() {
    const title = quizName.trim() || currentQuiz.title?.trim() || '';
    if (!title || currentQuiz.questions.length === 0) {
      alert('Abra ou crie um quiz antes de exportar.');
      return;
    }

    const response = await fetch('/api/quiz/export', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        ...currentQuiz,
        title
      })
    });

    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      alert(data.error || 'Erro ao exportar quiz');
      return;
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${title.replace(/[^a-zA-Z0-9_-]/g, '_') || 'quiz'}.quiz`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => {
      window.URL.revokeObjectURL(url);
    }, 1000);
  }

  async function importQuiz(file) {
    if (!file) {
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch('/api/quiz/import', {
      method: 'POST',
      body: formData
    });

    const data = await response.json();
    if (!response.ok) {
      alert(data.error || 'Erro ao importar quiz');
      return;
    }

    await loadQuizList();
    setCurrentName(data.quiz_name);
    setCurrentQuiz(data.quiz_data);
    setQuizName(data.quiz_data.title || '');
  }

  return (
    <section className="page-grid">
      <div className="card page-grid">
        <div>
          <span className="pill">Editor</span>
          <h1 className="hero-title">Gerenciador de quizzes</h1>
          <p className="hero-copy">Crie, edite e publique quizzes diretamente pelo navegador.</p>
        </div>

        <div className="toolbar">
          <select value={currentName} onChange={(event) => loadQuiz(event.target.value)} style={{ minWidth: 260, flex: '1 1 260px' }}>
            <option value="">-- Novo quiz --</option>
            {quizList.map((quiz) => (
              <option key={quiz} value={quiz}>{quiz}</option>
            ))}
          </select>
          <button className="ghost" onClick={() => loadQuiz('')}>Novo</button>
          <button className="ghost" onClick={exportQuiz}>Exportar</button>
          <button className="ghost" onClick={() => importInputRef.current?.click()}>Importar</button>
          <button className="danger" onClick={deleteQuiz}>Excluir</button>
          <input
            ref={importInputRef}
            type="file"
            accept=".quiz,.json"
            style={{ display: 'none' }}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                importQuiz(file);
              }
              event.target.value = '';
            }}
          />
        </div>
      </div>

      <div className="card editor-grid">
        <input value={quizName} onChange={(event) => setQuizName(event.target.value)} placeholder="Título do quiz" />

        {currentQuiz.questions.map((question, questionIndex) => (
          <div className="question-card" key={`question-${questionIndex}`}>
            <div className="question-header">
              <strong>Pergunta {questionIndex + 1}</strong>
              <button className="danger" onClick={() => removeQuestion(questionIndex)}>Remover</button>
            </div>

            <input
              value={question.text}
              onChange={(event) => updateQuestion(questionIndex, (item) => {
                item.text = event.target.value;
                return item;
              })}
              placeholder="Texto da pergunta"
            />

            <div className="stack">
              {question.options.map((option, optionIndex) => (
                <div className="toolbar" key={`option-${questionIndex}-${optionIndex}`}>
                  <input
                    value={option}
                    onChange={(event) => updateQuestion(questionIndex, (item) => {
                      item.options[optionIndex] = event.target.value;
                      return item;
                    })}
                    placeholder={`Opção ${optionIndex + 1}`}
                  />
                  <button
                    className="ghost"
                    onClick={() => updateQuestion(questionIndex, (item) => {
                      item.options.splice(optionIndex, 1);
                      if (item.correct_option >= item.options.length) {
                        item.correct_option = Math.max(0, item.options.length - 1);
                      }
                      return item;
                    })}
                  >
                    Remover
                  </button>
                </div>
              ))}
            </div>

            <div className="toolbar">
              <button
                className="ghost"
                onClick={() => updateQuestion(questionIndex, (item) => {
                  item.options.push('');
                  return item;
                })}
              >
                + Adicionar opção
              </button>
              <span className="muted" style={{ whiteSpace: 'nowrap' }}>
                Índice da resposta correta (0 = primeira opção)
              </span>
              <input
                type="number"
                min="0"
                max={Math.max(0, question.options.length - 1)}
                value={question.correct_option}
                onChange={(event) => updateQuestion(questionIndex, (item) => {
                  const nextValue = Number(event.target.value);
                  item.correct_option = Number.isFinite(nextValue) ? Math.max(0, Math.min(nextValue, Math.max(0, item.options.length - 1))) : 0;
                  return item;
                })}
                style={{ maxWidth: 180 }}
              />
            </div>

            <div className="toolbar">
              <input
                type="file"
                accept="image/*"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) {
                    uploadFigure(file, questionIndex);
                  }
                }}
              />
              <button
                className="ghost"
                onClick={() => updateQuestion(questionIndex, (item) => {
                  item.figure = 'none';
                  return item;
                })}
              >
                Remover figura
              </button>
            </div>

            {question.figure && question.figure !== 'none' ? (
              <div className="result-banner">
                <img src={`/static/quiz-figures/${question.figure}`} alt="Figura da pergunta" style={{ width: '100%', borderRadius: 16 }} />
              </div>
            ) : (
              <div className="result-banner muted">Nenhuma figura associada.</div>
            )}
          </div>
        ))}

        <div className="toolbar">
          <button className="ghost" onClick={addQuestion}>+ Adicionar pergunta</button>
          <button onClick={saveQuiz}>Salvar quiz</button>
        </div>
      </div>
    </section>
  );
}