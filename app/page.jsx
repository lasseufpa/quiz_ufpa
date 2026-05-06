"use client";

import { useEffect, useState } from 'react';
import { getSocket } from '@/lib/socket';
import { renderLatexToHtml } from '@/lib/renderLatex';

const STATE_QUESTION = 1;
const STATE_ANSWER = 2;

const optionLetters = ['A', 'B', 'C', 'D'];

export default function PlayerPage() {
  const [socket, setSocket] = useState(null);
  const [view, setView] = useState('join');
  const [nickname, setNickname] = useState('');
  const [question, setQuestion] = useState(null);
  const [results, setResults] = useState(null);
  const [leaderboard, setLeaderboard] = useState([]);
  const [score, setScore] = useState(0);
  const [sessionToken, setSessionToken] = useState(() => (typeof window !== 'undefined' ? localStorage.getItem('quizSessionToken') : null));
  const [answerIndex, setAnswerIndex] = useState(() => (typeof window !== 'undefined' ? localStorage.getItem('answerSubmitted') : null));
  const [questionDeadline, setQuestionDeadline] = useState(null);
  const [timeLeftMs, setTimeLeftMs] = useState(null);

  useEffect(() => {
    setSocket(getSocket());
  }, []);

  useEffect(() => {
    if (!socket) {
      return;
    }

    const onConnect = () => {
      if (sessionToken) {
        socket.emit('restore_session', { token: sessionToken, new_sid: socket.id });
      }
    };

    const onJoinSuccess = (data) => {
      setView('wait');
      setNickname(data.nickname);
      if (data.session_token) {
        setSessionToken(data.session_token);
        localStorage.setItem('quizSessionToken', data.session_token);
      }
    };

    const onJoinFailed = (data) => {
      alert(data.reason || 'Falha ao entrar');
    };

    const onSessionRestored = (data) => {
      setNickname(data.nickname);
      setScore(data.current_score || 0);
      setView('wait');

      if (data.current_question >= 0) {
        if (data.state === STATE_QUESTION) {
          if (localStorage.getItem('answerSubmitted') === null) {
            setView('question');
            setQuestionDeadline(typeof data.question_deadline === 'number' ? data.question_deadline : null);
          } else {
            setView('results');
            setQuestionDeadline(null);
          }
        }

        if (data.state === STATE_ANSWER) {
          setView('results');
          setQuestionDeadline(null);
        }
      }
    };

    const onSessionRestoreFailed = () => {
      localStorage.removeItem('quizSessionToken');
      localStorage.removeItem('answerSubmitted');
      setSessionToken(null);
      setView('join');
    };

    const onShowQuestion = (data) => {
      setQuestion(data);
      setResults(null);
      setAnswerIndex(null);
      localStorage.removeItem('answerSubmitted');
      setView('question');
      setQuestionDeadline(typeof data?.question_deadline === 'number' ? data.question_deadline : null);
    };

    const onAnswerReceived = () => {
      setView('results');
      setResults((previous) => previous || { message: 'Resposta recebida! Aguardando resultados...' });
      setQuestionDeadline(null);
    };

    const onShowResults = (data) => {
      setResults(data);
      setScore(data.scores?.[socket.id] || 0);
      setView('results');
      setQuestionDeadline(null);
    };

    const onGameOver = (data) => {
      setLeaderboard(data || []);
      setView('gameover');
      setQuestionDeadline(null);
    };

    const onQuestionTimeOver = () => {
      setQuestionDeadline(Date.now());
      setResults((previous) => previous || { message: 'Tempo esgotado. Aguarde o professor mostrar os resultados.' });
      setView('results');
    };

    const onAnswerRejected = (data) => {
      alert(data?.reason || 'Resposta rejeitada.');
    };

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
      localStorage.removeItem('quizSessionToken');
      localStorage.removeItem('answerSubmitted');
      setSessionToken(null);
      setAnswerIndex(null);
      setView('join');
      setQuestion(null);
      setResults(null);
      setLeaderboard([]);
      setScore(0);
      setQuestionDeadline(null);
      alert('O jogo foi resetado.');
    };

    socket.on('connect', onConnect);
    socket.on('join_success', onJoinSuccess);
    socket.on('join_failed', onJoinFailed);
    socket.on('session_restored', onSessionRestored);
    socket.on('session_restore_failed', onSessionRestoreFailed);
    socket.on('show_question', onShowQuestion);
    socket.on('answer_received', onAnswerReceived);
    socket.on('show_results', onShowResults);
    socket.on('game_over', onGameOver);
    socket.on('question_time_over', onQuestionTimeOver);
    socket.on('answer_rejected', onAnswerRejected);
    socket.on('host_disconnected', onHostDisconnected);
    socket.on('host_reconnected', onHostReconnected);
    socket.on('game_reset', onGameReset);

    return () => {
      socket.off('connect', onConnect);
      socket.off('join_success', onJoinSuccess);
      socket.off('join_failed', onJoinFailed);
      socket.off('session_restored', onSessionRestored);
      socket.off('session_restore_failed', onSessionRestoreFailed);
      socket.off('show_question', onShowQuestion);
      socket.off('answer_received', onAnswerReceived);
      socket.off('show_results', onShowResults);
      socket.off('game_over', onGameOver);
      socket.off('question_time_over', onQuestionTimeOver);
      socket.off('answer_rejected', onAnswerRejected);
      socket.off('host_disconnected', onHostDisconnected);
      socket.off('host_reconnected', onHostReconnected);
      socket.off('game_reset', onGameReset);
    };
  }, [sessionToken, socket]);

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

  const joinGame = () => {
    const trimmedNickname = nickname.trim();
    if (!socket) {
      return;
    }

    if (!trimmedNickname) {
      alert('Adicione um nome.');
      return;
    }

    socket.emit('player_join', { nickname: trimmedNickname });
  };

  const submitAnswer = (index) => {
    if (!socket) {
      return;
    }

    socket.emit('submit_answer', { option_index: index });
    setAnswerIndex(String(index));
    localStorage.setItem('answerSubmitted', String(index));
    setView('results');
  };

  const renderJoinView = () => (
    <section className="card page-grid" style={{ maxWidth: 620, margin: '0 auto' }}>
      <div>
        <span className="pill">Participante</span>
        <h1 className="hero-title">Entrar no quiz</h1>
        <p className="hero-copy">Entre com um nome cadastrado para participar da sessão em andamento.</p>
      </div>

      <div className="stack">
        <input value={nickname} onChange={(event) => setNickname(event.target.value)} placeholder="Seu nome" />
        <button onClick={joinGame}>Entrar</button>
      </div>
    </section>
  );

  const renderWaitView = () => (
    <section className="card page-grid" style={{ maxWidth: 720, margin: '0 auto' }}>
      <div>
        <span className="pill">Sala de espera</span>
        <h1 className="hero-title">Olá, {nickname}!</h1>
        <p className="hero-copy">Aguarde o professor iniciar o jogo.</p>
      </div>
      <div className="result-banner"><strong>Placar atual:</strong> {score}</div>
    </section>
  );

  const renderQuestionView = () => {
    const isTimeUp = timeLeftMs !== null && timeLeftMs <= 0;
    const isDisabled = answerIndex !== null || isTimeUp;

    return (
      <section className="card page-grid" style={{ maxWidth: 980, margin: '0 auto' }}>
        <div>
          <span className="pill">Pergunta em andamento</span>
          <div className="pill" style={{ marginTop: '0.75rem' }}>Tempo: {formatTimeLeft(timeLeftMs)}</div>
          <h1 className="hero-title latex-block" style={{ fontSize: 'clamp(1.5rem, 3vw, 2.8rem)' }} dangerouslySetInnerHTML={{ __html: renderLatexToHtml(question?.text || 'Pergunta') }} />
        </div>

        <div className="option-grid">
          {(question?.options || []).map((option, index) => (
            <button
              key={`${question?.question_index || 0}-${index}`}
              className={`option-btn ${['is-a', 'is-b', 'is-c', 'is-d'][index] || ''}`}
              onClick={() => submitAnswer(index)}
              disabled={isDisabled}
            >
              <span className="latex-inline" dangerouslySetInnerHTML={{ __html: `${optionLetters[index]}) ${renderLatexToHtml(option)}` }} />
            </button>
          ))}
        </div>
      </section>
    );
  };

  const renderResultsView = () => {
    const currentAnswer = answerIndex;
    const hasFinalResult = results && results.correct_option !== undefined && results.correct_option !== null;
    const correctIndex = hasFinalResult ? String(results.correct_option) : null;
    const message = !hasFinalResult
      ? (currentAnswer === null ? 'Resposta enviada! Aguardando resultados...' : (results?.message || 'Resposta enviada! Aguardando resultados...'))
      : currentAnswer === null
        ? 'Você não respondeu a tempo!'
        : currentAnswer === correctIndex
          ? 'Você acertou!'
          : 'Você errou!';

    return (
      <section className="card page-grid" style={{ maxWidth: 920, margin: '0 auto' }}>
        <div>
          <span className="pill">Resultado</span>
          <h1 className="hero-title">{message}</h1>
        </div>

        {!hasFinalResult ? <div className="result-banner">Sua resposta foi enviada. Aguarde o professor mostrar o resultado final.</div> : null}
        {results?.message ? <div className="result-banner">{results.message}</div> : null}

        {results?.correct_option_text ? (
          <div className="result-banner"><strong>Resposta correta:</strong> <span className="latex-inline" dangerouslySetInnerHTML={{ __html: renderLatexToHtml(results.correct_option_text) }} /></div>
        ) : null}

        <div className="result-banner"><strong>Placar:</strong> {score}</div>

        {results?.chart_path ? <img src={results.chart_path} alt="Distribuição das respostas" style={{ width: '100%', borderRadius: 20 }} /> : null}
      </section>
    );
  };

  const renderGameOverView = () => (
    <section className="card page-grid" style={{ maxWidth: 760, margin: '0 auto' }}>
      <div>
        <span className="pill">Fim do jogo</span>
        <h1 className="hero-title">Placar final</h1>
      </div>

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
    </section>
  );

  if (view === 'wait') return renderWaitView();
  if (view === 'question') return renderQuestionView();
  if (view === 'results') return renderResultsView();
  if (view === 'gameover') return renderGameOverView();
  return renderJoinView();
}