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
  const [questionDeadline, setQuestionDeadline] = useState(null);
  const [timeLeftMs, setTimeLeftMs] = useState(null);

  const phaseMeta = {
    lobby: {
      label: 'Aguardando jogadores',
      title: `Sala do professor: aguardando início (${serverHost})`,
      copy: 'Selecione um quiz, aguarde a entrada dos jogadores e inicie a partida quando estiver pronto.'
    },
    question: {
      label: 'Pergunta em andamento',
      title: 'Pergunta atual',
      copy: 'Acompanhe a pergunta exibida e o progresso das respostas em tempo real.'
    },
    results: {
      label: 'Resultados da pergunta',
      title: 'Resultados',
      copy: 'Veja a alternativa correta, o gráfico de respostas e baixe o resultado da rodada.'
    },
    gameover: {
      label: 'Fim da partida',
      title: 'Placar final',
      copy: 'Revise a classificação final e exporte o resultado consolidado.'
    }
  };
  const activePhase = phaseMeta[phase] || phaseMeta.lobby;

  useEffect(() => {
    setSocket(getSocket());
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      setServerHost('');
    }
  }, []);

  useEffect(() => {
    if (!socket) {
      return;
    }

    const verifySession = async () => {
      const response = await fetch('/api/host/session');
      const payload = await response.json();
      if (payload.serverUrl) {
        setServerHost(payload.serverUrl);
      }
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

      if (data.state === 0) {
        setPhase('lobby');
        setQuestionDeadline(null);
      } else if (data.state === 1) {
        setPhase('question');
        setQuestionDeadline(typeof data.question_deadline === 'number' ? data.question_deadline : null);
      } else if (data.state === 2) {
        setPhase('results');
        setQuestionDeadline(null);
      }
    };
    const onShowQuestion = (data) => {
      setPhase('question');
      setQuestion(data);
      setResults(null);
      setQuestionDeadline(typeof data?.question_deadline === 'number' ? data.question_deadline : null);
    };
    const onUpdateAnswerCount = (data) => setAnswerCount(data || { answered: 0, total: 0 });
    const onShowResults = (data) => {
      setPhase('results');
      setResults(data);
      setQuestionDeadline(null);
    };
    const onGameOver = (data) => {
      setPhase('gameover');
      setLeaderboard(data || []);
      setQuestionDeadline(null);
    };
    const onQuestionTimeOver = () => {
      setQuestionDeadline(Date.now());
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
      setQuestionDeadline(null);
      alert('O jogo foi resetado!');
    };

    socket.on('update_player_list', onUpdatePlayers);
    socket.on('resume_host_state', onResumeHostState);
    socket.on('show_question', onShowQuestion);
    socket.on('update_answer_count', onUpdateAnswerCount);
    socket.on('show_results', onShowResults);
    socket.on('game_over', onGameOver);
    socket.on('question_time_over', onQuestionTimeOver);
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
      socket.off('question_time_over', onQuestionTimeOver);
      socket.off('player_left', onPlayerLeft);
      socket.off('host_disconnected', onHostDisconnected);
      socket.off('host_reconnected', onHostReconnected);
      socket.off('game_reset', onGameReset);
    };
  }, [router, socket]);

  useEffect(() => {
    if (!questionDeadline) {
      setTimeLeftMs(null);
      return;
    }

    const updateTime = () => {
      const msLeft = Math.max(0, questionDeadline - Date.now());
      setTimeLeftMs(msLeft);
    };

    updateTime();
    const intervalId = setInterval(updateTime, 250);
    return () => clearInterval(intervalId);
  }, [questionDeadline]);

  const formatTimeLeft = (ms) => {
    if (ms === null || ms === undefined) {
      return '--:--';
    }
    const totalSeconds = Math.ceil(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  };

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

  const downloadResultsAsCSV = (data) => {
    if (!data) {
      alert('Nenhum resultado para baixar.');
      return;
    }

    const leaderboard = data.leaderboard || [];
    if (leaderboard.length === 0) {
      alert('Nenhum jogador para exibir.');
      return;
    }

    const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..*/, '').replace('T', '_');
    const filename = `resultados_${timestamp}.csv`;
    const csvContent = [
      'Posição,Jogador,Pontuação',
      ...leaderboard.map((player, index) => `${index + 1},"${player.nickname.replace(/"/g, '""')}",${player.score}`)
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <section className="page-grid">
      <div className="card page-grid">
        <div>
          <span className="pill">Host</span>
          <h1 className="hero-title">{activePhase.title}</h1>
          <p className="hero-copy">{activePhase.copy}</p>
        </div>

        <div className="toolbar">
          <div className="pill">{activePhase.label}</div>
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

      {phase === 'lobby' ? (
        <div className="card page-grid">
          <h2 className="section-title">Aguardando jogadores</h2>
          <div className="result-banner">Servidor ativo: {serverHost || '...'}</div>
          <div className="result-banner">
            {players.length === 0
              ? 'Nenhum jogador conectado ainda.'
              : `${players.length} jogador${players.length === 1 ? '' : 'es'} conectado${players.length === 1 ? '' : 's'}.`}
          </div>
          <div className="list">
            {players.length === 0 ? (
              <div className="result-banner">A sala está pronta para receber participantes.</div>
            ) : (
              players.map((player) => (
                <div key={player} className="admin-list-item">{player}</div>
              ))
            )}
          </div>
        </div>
      ) : null}

      {phase === 'question' ? (
        <div className="card page-grid">
          <h2 className="section-title">Pergunta atual</h2>
          <div className="result-banner latex-block" dangerouslySetInnerHTML={{ __html: renderLatexToHtml(question?.text || 'Aguardando pergunta.') }} />
          {question?.chart_path ? <img src={question.chart_path} alt="Figura da pergunta" style={{ width: '100%', borderRadius: 20 }} /> : null}
          <div className="toolbar">
            <div className="pill">Respondidas: {answerCount.answered} / {answerCount.total}</div>
            <div className="pill">Tempo: {formatTimeLeft(timeLeftMs)}</div>
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
          {results?.leaderboard ? (
            <div className="toolbar">
              <button className="success" onClick={() => downloadResultsAsCSV(results)}>Baixar resultados (CSV)</button>
            </div>
          ) : null}
        </div>
      ) : null}

      {phase === 'gameover' ? (
        <div className="card page-grid">
          <h2 className="section-title">Placar final</h2>
          <div className="result-banner">A partida terminou. Você pode revisar o ranking e baixar o CSV final.</div>
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
          <div className="toolbar" style={{ marginTop: '1rem' }}>
            <button className="success" onClick={() => downloadResultsAsCSV({ leaderboard })}>Baixar resultados finais (CSV)</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}