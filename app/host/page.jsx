"use client";

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getSocket } from '@/lib/socket';
import { renderLatexToHtml } from '@/lib/renderLatex';

export default function HostPage() {
  const router = useRouter();
  const [socket, setSocket] = useState(null);
  const [serverHost, setServerHost] = useState('');
  const [players, setPlayers] = useState([]);
  const [quizzes, setQuizzes] = useState([]);
  const [selectedQuiz, setSelectedQuiz] = useState('');
  const [phase, setPhase] = useState('lobby');
  const [question, setQuestion] = useState(null);
  const [results, setResults] = useState(null);
  const [answerCount, setAnswerCount] = useState({ answered: 0, total: 0 });
  const [leaderboard, setLeaderboard] = useState([]);

  useEffect(() => {
    setSocket(getSocket());
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setServerHost(window.location.hostname);
    }
  }, []);

  useEffect(() => {
    if (!socket) {
      return;
    }

    const verifySession = async () => {
      const response = await fetch('/api/host/session');
      const payload = await response.json();
      if (!payload.loggedIn) {
        router.push('/host/login');
        return;
      }

      socket.emit('host_join');
    };

    const loadQuizzes = async () => {
      const response = await fetch('/api/quizzes');
      const data = await response.json();
      setQuizzes(data);
    };

    const onUpdatePlayers = (list) => setPlayers(list || []);
    const onResumeHostState = (data) => {
      if (!data) {
        return;
      }

      if (data.state === 1) {
        setPhase('question');
      } else if (data.state === 2) {
        setPhase('results');
      }
    };
    const onShowQuestion = (data) => {
      setPhase('question');
      setQuestion(data);
      setResults(null);
    };
    const onUpdateAnswerCount = (data) => setAnswerCount(data || { answered: 0, total: 0 });
    const onShowResults = (data) => {
      setPhase('results');
      setResults(data);
    };
    const onGameOver = (data) => {
      setPhase('gameover');
      setLeaderboard(data || []);
    };
    const onPlayerLeft = () => socket.emit('host_join');
    const onHostDisconnected = (data) => {
      if (data?.message) {
        alert(data.message);
      }
    };
    const onHostReconnected = (data) => {
      if (data?.message) {
        alert(data.message);
      }
    };
    const onGameReset = () => {
      setPlayers([]);
      setPhase('lobby');
      setQuestion(null);
      setResults(null);
      setLeaderboard([]);
      setAnswerCount({ answered: 0, total: 0 });
      alert('O jogo foi resetado!');
    };

    socket.on('update_player_list', onUpdatePlayers);
    socket.on('resume_host_state', onResumeHostState);
    socket.on('show_question', onShowQuestion);
    socket.on('update_answer_count', onUpdateAnswerCount);
    socket.on('show_results', onShowResults);
    socket.on('game_over', onGameOver);
    socket.on('player_left', onPlayerLeft);
    socket.on('host_disconnected', onHostDisconnected);
    socket.on('host_reconnected', onHostReconnected);
    socket.on('game_reset', onGameReset);

    loadQuizzes();
    verifySession();

    return () => {
      socket.off('update_player_list', onUpdatePlayers);
      socket.off('resume_host_state', onResumeHostState);
      socket.off('show_question', onShowQuestion);
      socket.off('update_answer_count', onUpdateAnswerCount);
      socket.off('show_results', onShowResults);
      socket.off('game_over', onGameOver);
      socket.off('player_left', onPlayerLeft);
      socket.off('host_disconnected', onHostDisconnected);
      socket.off('host_reconnected', onHostReconnected);
      socket.off('game_reset', onGameReset);
    };
  }, [router, socket]);

  const startGame = () => {
    if (!selectedQuiz) {
      alert('Selecione um quiz válido.');
      return;
    }

    if (socket) {
      socket.emit('start_game', { 'quiz-name': selectedQuiz });
    }
  };

  const forceEndQuiz = () => {
    if (window.confirm('Tem certeza que deseja finalizar o quiz agora?')) {
      socket?.emit('force_end_quiz');
    }
  };

  const nextQuestion = () => socket?.emit('next_question');
  const showResults = () => socket?.emit('show_results');

  return (
    <section className="page-grid">
      <div className="card page-grid">
        <div>
          <span className="pill">Host</span>
          <h1 className="hero-title">Sala do professor: {serverHost || '...'}</h1>
          <p className="hero-copy">Controle a fila de jogadores, o quiz atual e a navegação entre perguntas.</p>
        </div>

        <div className="toolbar">
          <select value={selectedQuiz} onChange={(event) => setSelectedQuiz(event.target.value)} style={{ minWidth: 280, flex: '1 1 280px' }}>
            <option value="">-- Selecionar quiz --</option>
            {quizzes.map((quiz) => (
              <option key={quiz} value={quiz}>{quiz}</option>
            ))}
          </select>
          <button onClick={startGame} disabled={players.length === 0}>Iniciar jogo ({players.length})</button>
          <button className="danger" onClick={forceEndQuiz} disabled={players.length === 0}>Finalizar quiz</button>
          <button
            className="ghost"
            onClick={async () => {
              await fetch('/api/host/logout', { method: 'POST' });
              router.push('/host/login');
            }}
          >
            Sair
          </button>
        </div>
      </div>

      <div className="card page-grid">
        <h2 className="section-title">Jogadores</h2>
        <div className="list">
          {players.length === 0 ? (
            <div className="result-banner">Nenhum jogador conectado.</div>
          ) : (
            players.map((player) => (
              <div key={player} className="admin-list-item">{player}</div>
            ))
          )}
        </div>
      </div>

      {phase !== 'lobby' ? (
        <div className="card page-grid">
          <h2 className="section-title">Pergunta atual</h2>
          <div className="result-banner latex-block" dangerouslySetInnerHTML={{ __html: renderLatexToHtml(question?.text || 'Aguardando pergunta.') }} />
          {question?.chart_path ? <img src={question.chart_path} alt="Figura da pergunta" style={{ width: '100%', borderRadius: 20 }} /> : null}
          <div className="toolbar">
            <div className="pill">Respondidas: {answerCount.answered} / {answerCount.total}</div>
            <button onClick={showResults}>Mostrar resultados</button>
            <button className="warning" onClick={nextQuestion}>Próxima pergunta</button>
          </div>
        </div>
      ) : null}

      {phase === 'results' ? (
        <div className="card page-grid">
          <h2 className="section-title">Resultados</h2>
          {results?.correct_option_text ? <div className="result-banner">Resposta correta: <span className="latex-inline" dangerouslySetInnerHTML={{ __html: renderLatexToHtml(results.correct_option_text) }} /></div> : null}
          {results?.chart_path ? <img src={results.chart_path} alt="Gráfico das respostas" style={{ width: '100%', borderRadius: 20 }} /> : null}
        </div>
      ) : null}

      {phase === 'gameover' ? (
        <div className="card page-grid">
          <h2 className="section-title">Placar final</h2>
          <div className="scoreboard">
            {leaderboard.length === 0 ? (
              <div className="result-banner">Nenhum jogador participou.</div>
            ) : (
              leaderboard.map((player, index) => (
                <div key={`${player.nickname}-${index}`} className="result-banner">
                  {index + 1}. {player.nickname} - {player.score} pontos
                </div>
              ))
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}