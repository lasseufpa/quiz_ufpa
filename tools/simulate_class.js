#!/usr/bin/env node
/**
 * Simulador de turma para o quiz_ufpa.
 *
 * Cria "alunos virtuais" que entram na sala e se comportam como gente:
 *  - cada um tem uma probabilidade própria de acertar;
 *  - tempos de resposta variados (alguns quase instantâneos, outros lentos);
 *  - de vez em quando nem respondem (deixam o tempo acabar);
 *  - de vez em quando caem e voltam no meio da partida (reconexão).
 *
 * Modo 1 — só os alunos (você conduz pelo navegador em /host):
 *
 *   node tools/simulate_class.js --students "Ana,Bruno,Carla"
 *
 * Modo 2 — o script também faz o papel de apresentador (partida completa,
 * sem abrir navegador). Precisa da senha do professor:
 *
 *   node tools/simulate_class.js --password SENHA --class simulacao-10 \
 *        --quiz 1C-RelatingAnalogDiscreteFrequencies
 *
 * Opções:
 *   --url          Base do servidor (padrão: http://localhost:5000)
 *   --class        Slug da turma (padrão: simulacao-10)
 *   --students     Nomes separados por vírgula (padrão: os 9 "bots")
 *   --quiz         Nome do quiz (obrigatório no modo 2)
 *   --password     Senha do professor; ativa o modo apresentador
 *   --accuracy     Acerto médio 0..1 (padrão: sorteado entre 0.30 e 0.90)
 *   --skip         Chance de não responder (padrão: 0.04)
 *   --disconnect   Chance de cair após responder (padrão: 0.06)
 *   --wait         Segundos de espera pelos alunos antes de iniciar (padrão: 8)
 *   --seed         Semente do sorteio (repetível)
 */

'use strict';

const http = require('http');
const { io } = require('socket.io-client');

// -------------------- utilidades --------------------
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function parseArgs(argv) {
  const out = {};
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a.indexOf('--') !== 0) continue;
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.indexOf('--') === 0) out[key] = true;
    else { out[key] = next; i++; }
  }
  return out;
}

// Gerador determinístico (mesma semente => mesmo sorteio)
function makeRandom(seed) {
  let s = seed >>> 0;
  return function () {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function httpRequest(urlString, method, formBody, cookie) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlString);
    const payload = formBody ? Buffer.from(formBody) : null;
    const headers = {};
    if (payload) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded';
      headers['Content-Length'] = payload.length;
    }
    if (cookie) headers['Cookie'] = cookie;

    const req = http.request({
      hostname: u.hostname,
      port: u.port || 80,
      path: u.pathname + u.search,
      method: method,
      headers: headers,
    }, (res) => {
      let body = '';
      res.setEncoding('utf8');
      res.on('data', (c) => { body += c; });
      res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: body }));
    });
    req.on('error', reject);
    if (payload) req.write(payload);
    req.end();
  });
}

function pad(s, n) {
  s = String(s);
  return s + ' '.repeat(Math.max(0, n - s.length));
}

// -------------------- configuração --------------------
const args = parseArgs(process.argv);

if (args.help || args.h) {
  console.log([
    '',
    'Uso: node tools/simulate_class.js [opções]',
    '',
    '  --url         base do servidor (padrão http://localhost:5000)',
    '  --class       slug da turma (padrão simulacao-10)',
    '  --students    nomes separados por vírgula (padrão: 9 alunos de exemplo)',
    '  --quiz        nome do quiz (obrigatório no modo --password)',
    '  --password    senha do professor (ativa o modo apresentador automático)',
    '  --accuracy    acerto médio 0..1 (padrão: sorteado entre 0.30 e 0.90)',
    '  --skip        chance de não responder (padrão 0.04)',
    '  --disconnect  chance de cair após responder (padrão 0.06)',
    '  --wait        segundos de espera pelos alunos antes de iniciar (padrão 8)',
    '  --teams       times do modo time; "alternar" (padrão, A/B) ou "A" / "B"',
    '  --seed        semente do sorteio (repetível)',
    '',
  ].join('\n'));
  process.exit(0);
}

const cfg = {
  url: (args.url || 'http://localhost:5000').replace(/\/$/, ''),
  className: args.class || 'simulacao-10',
  password: args.password || null,
  quiz: args.quiz || null,
  wait: Number(args.wait || 8),
  accuracy: args.accuracy != null ? Number(args.accuracy) : null,
  skip: args.skip != null ? Number(args.skip) : 0.04,
  disconnect: args.disconnect != null ? Number(args.disconnect) : 0.06,
  teams: (args.teams || 'alternar'),
  seed: Number(args.seed || 20261104),
};

const DEFAULT_BOTS = ['Ana', 'Bruno', 'Carla', 'Diego', 'Elisa', 'Felipe', 'Gabriela', 'Hugo', 'Isabela'];
const botNames = (args.students ? String(args.students).split(',') : DEFAULT_BOTS)
  .map((s) => s.trim()).filter(Boolean);

const rnd = makeRandom(cfg.seed);
const sockets = [];
let quiz = null;
const answerMap = {};   // texto da pergunta -> índice da alternativa correta
let finished = false;

// -------------------- perfis --------------------
// No modo time, os alunos virtuais se dividem: "alternar" (A, B, A, B…),
// um time fixo ("A" ou "B") ou "nenhum" para salas sem modo time.
function teamForIndex(index) {
  const escolha = String(cfg.teams || 'alternar').toLowerCase();
  if (escolha === 'nenhum' || escolha === 'none' || escolha === 'off') return null;
  if (escolha === 'a' || escolha === 'b') return escolha.toUpperCase();
  return index % 2 === 0 ? 'A' : 'B';
}

const profiles = botNames.map((nickname, index) => {
  const profile = {
    nickname: nickname,
    team: teamForIndex(index),        // 'A'/'B' (modo time) ou null
    accuracy: cfg.accuracy != null ? cfg.accuracy : 0.30 + rnd() * 0.60,
    speed: 0.6 + rnd() * 1.6,          // > 1 = mais lento
    pSkip: cfg.skip,
    pDisconnect: cfg.disconnect,
    pSlow: 0.15,                        // 15% das perguntas "travam"
    // estatísticas
    answered: 0,
    correct: 0,
    skipped: 0,
    disconnects: 0,
    totalDelay: 0,
  };
  return profile;
});

function describeProfiles() {
  console.log('\nPerfis dos alunos virtuais:');
  profiles.forEach((p) => {
    console.log('  ' + pad(p.nickname, 12) +
      'acerto ' + pad(Math.round(p.accuracy * 100) + '%', 5) +
      ' velocidade x' + p.speed.toFixed(2) +
      (p.team ? '  time ' + p.team : '') +
      '  (pular ' + Math.round(p.pSkip * 100) + '%, cair ' + Math.round(p.pDisconnect * 100) + '%)');
  });
  console.log('');
}

// -------------------- dados do quiz --------------------
async function loadQuizInfo() {
  const listUrl = cfg.url + '/api/classes/' + encodeURIComponent(cfg.className) + '/quizzes';
  const res = await httpRequest(listUrl, 'GET');
  if (res.status !== 200) {
    throw new Error('Não consegui listar os quizzes da turma "' + cfg.className + '" (HTTP ' + res.status + ').');
  }
  const names = JSON.parse(res.body);
  if (!Array.isArray(names) || names.length === 0) {
    throw new Error('A turma "' + cfg.className + '" não tem quizzes. Crie/copiei um quiz no editor.');
  }
  const quizName = cfg.quiz || names[0];

  const quizUrl = cfg.url + '/api/classes/' + encodeURIComponent(cfg.className) +
    '/quiz/' + encodeURIComponent(quizName);
  const quizRes = await httpRequest(quizUrl, 'GET');
  if (quizRes.status !== 200) {
    throw new Error('Quiz "' + quizName + '" não encontrado (HTTP ' + quizRes.status + '). ' +
      'Disponíveis: ' + names.join(', '));
  }
  return { name: quizName, data: JSON.parse(quizRes.body), available: names };
}

// O apresentador pode escolher qualquer quiz da turma no navegador. Para não
// errar o gabarito, montamos um índice "texto da pergunta -> alternativa certa"
// com todos os quizzes da turma.
async function loadAnswerMap(names) {
  for (let i = 0; i < names.length; i++) {
    try {
      const url = cfg.url + '/api/classes/' + encodeURIComponent(cfg.className) +
        '/quiz/' + encodeURIComponent(names[i]);
      const res = await httpRequest(url, 'GET');
      if (res.status !== 200) continue;
      const data = JSON.parse(res.body);
      (data.questions || []).forEach((q) => {
        if (q && typeof q.text === 'string') answerMap[q.text] = Number(q.correct_option);
      });
    } catch (e) { /* ignora quiz ilegível */ }
  }
  return Object.keys(answerMap).length;
}

function correctOptionFor(state) {
  if (state.text != null && answerMap[state.text] != null) return answerMap[state.text];
  const q = quiz && quiz.questions ? quiz.questions[state.questionIndex] : null;
  return q ? Number(q.correct_option) : 0;
}

// -------------------- aluno virtual --------------------
function createBot(profile) {
  let sock = null;
  let warnedClosed = false;
  const state = { questionIndex: -1, options: 0, answered: false, choice: null, forced: false, text: null };

  function connect(delayMs) {
    setTimeout(() => {
      sock = io(cfg.url, { transports: ['websocket', 'polling'], reconnection: false, timeout: 8000 });
      sockets.push(sock);

      sock.on('connect', () => {
        sock.emit('player_join', { nickname: profile.nickname, team: profile.team });
      });

      sock.on('join_success', (data) => {
        warnedClosed = false;
        const time = data && data.team_name ? ' [' + data.team_name + ']' : '';
        console.log('  \u2713 ' + profile.nickname + ' entrou na sala' + time);
      });

      sock.on('join_failed', (d) => {
        // Sala ainda fechada ou nome momentaneamente preso: tenta de novo
        if (finished) return;
        if (!warnedClosed) {
          warnedClosed = true;
          console.log('  \u2026 ' + pad(profile.nickname, 12) +
            'aguardando a sala abrir (' + (d && d.reason ? d.reason : 'sem motivo') + ')');
        }
        setTimeout(() => {
          if (sock && sock.connected) sock.emit('player_join', { nickname: profile.nickname, team: profile.team });
        }, 2500);
      });

      sock.on('show_question', (data) => {
        state.questionIndex = data.question_index;
        state.options = (data.options || []).length;
        state.text = data.text;
        state.answered = false;
        state.choice = null;
      });

      sock.on('answer_allowed', () => { maybeAnswer(); });

      // (a conferência do acerto é feita na hora do envio: assim uma queda de
      // conexão logo depois não esconde o resultado da pergunta)

      sock.on('game_over', () => {
        // No modo apresentador o script encerra e mostra o resumo. No modo
        // "só alunos", ele fica vivo e entra de novo quando outra sala abrir.
        try { sock.close(); } catch (e) { /* ignore */ }
        if (!cfg.password && !finished) {
          console.log('  \u21bb ' + pad(profile.nickname, 10) + 'fim da partida \u2014 aguardando a próxima sala');
          connect(3000);
        }
      });

      // O professor reiniciou a partida: entra de novo, como um aluno faria
      sock.on('game_reset', () => {
        if (finished) return;
        console.log('  \u21bb ' + pad(profile.nickname, 10) + 'a partida foi reiniciada \u2014 entrando de novo');
        try { sock.close(); } catch (e) { /* ignore */ }
        warnedClosed = false;
        connect(1500);
      });

      // O professor fechou a sala (troca de turma/quiz): o aluno precisa
      // entrar de novo quando ela reabrir.
      sock.on('room_closed', () => {
        if (finished) return;
        warnedClosed = false;
        state.answered = true;
        state.questionIndex = -1;
        console.log('  \u{1F6AA} ' + pad(profile.nickname, 10) + 'sala fechada \u2014 aguardando reabrir');
        setTimeout(() => {
          if (sock && sock.connected) sock.emit('player_join', { nickname: profile.nickname, team: profile.team });
        }, 1500);
      });

      sock.on('connect_error', (err) => {
        console.log('  ! ' + profile.nickname + ' erro de conexão: ' + err.message);
      });
    }, delayMs || 0);
  }

  function maybeAnswer() {
    if (state.answered || state.questionIndex < 0 || finished) return;

    if (rnd() < profile.pSkip) {
      state.answered = true;
      state.choice = null;
      state.questionIndex = -1;
      profile.skipped++;
      console.log('  – ' + pad(profile.nickname, 12) + 'não respondeu (deixou o tempo acabar)');
      return;
    }

    let delay = (1.2 + rnd() * 8) * profile.speed;
    if (rnd() < profile.pSlow) delay *= 2.5;
    delay = Math.min(Math.max(delay, 0.6), 26);

    setTimeout(() => {
      if (state.answered || finished) return;

      const total = state.options || 4;
      const correct = correctOptionFor(state);
      let choice;
      if (rnd() < profile.accuracy) {
        choice = correct;
      } else {
        const pool = [];
        for (let i = 0; i < total; i++) if (i !== correct) pool.push(i);
        choice = pool.length ? pool[Math.floor(rnd() * pool.length)] : correct;
      }

      state.answered = true;
      state.choice = choice;
      profile.answered++;
      profile.totalDelay += delay;
      if (choice === correct) profile.correct++;

      sock.emit('submit_answer', { option_index: choice });
      const letter = String.fromCharCode(65 + choice);
      const mark = choice === correct ? '✓' : '✗';
      console.log('  → ' + pad(profile.nickname, 12) + 'respondeu ' + letter +
        ' em ' + delay.toFixed(1) + 's ' + mark);

      // Simula queda de conexão depois de responder (pontos são preservados)
      if (rnd() < profile.pDisconnect) {
        profile.disconnects++;
        setTimeout(() => {
          if (finished) return;
          console.log('  ⚡ ' + pad(profile.nickname, 12) + 'perdeu a conexão… reconectando');
          try { sock.close(); } catch (e) { /* ignore */ }
          connect(2000 + Math.floor(rnd() * 4000));
        }, 400);
      }
    }, delay * 1000);
  }

  return { profile: profile, connect: connect };
}

// -------------------- apresentador --------------------
async function hostLogin() {
  const res = await httpRequest(cfg.url + '/host/login', 'POST',
    'password=' + encodeURIComponent(cfg.password));
  const cookies = res.headers['set-cookie'] || [];
  if (cookies.length === 0) {
    throw new Error('Login falhou: o servidor não devolveu sessão. Senha errada?');
  }
  return cookies.map((c) => c.split(';')[0]).join('; ');
}

function runHost(cookie, quizName, expectedPlayers) {
  return new Promise((resolve, reject) => {
    const host = io(cfg.url, {
      transports: ['websocket', 'polling'],
      extraHeaders: { Cookie: cookie },
      reconnection: false,
    });
    sockets.push(host);

    let playersSeen = 0;
    let started = false;
    let pendingResults = false;
    let resultsTimer = null;

    host.on('connect', () => {
      host.emit('host_join');
      setTimeout(() => host.emit('open_room', { class: cfg.className }), 400);
    });

    host.on('update_player_list', (players) => {
      playersSeen = players.length;
      if (started || playersSeen < expectedPlayers) return;
      started = true;
      console.log('\n👥 ' + playersSeen + ' jogadores na sala — iniciando a partida…\n');
      host.emit('start_game', { class: cfg.className, 'quiz-name': quizName });
    });

    host.on('answer_allowed', () => {
      // Rede de segurança: se ninguém responder, revela os resultados sozinho
      clearTimeout(resultsTimer);
      resultsTimer = setTimeout(() => {
        if (!pendingResults) host.emit('show_results');
        pendingResults = true;
      }, 33000);
    });

    host.on('update_answer_count', (d) => {
      if (!started || pendingResults) return;
      if (d.total > 0 && d.answered >= d.total) {
        pendingResults = true;
        clearTimeout(resultsTimer);
        host.emit('show_results');
      }
    });

    host.on('show_results', () => {
      setTimeout(() => {
        if (finished) return;
        pendingResults = false;
        host.emit('next_question');
      }, 2500);
    });

    host.on('game_over', (leaderboard) => {
      resolve(leaderboard || []);
    });

    host.on('admin_error', (d) => {
      console.log('  ! servidor: ' + (d && d.message ? d.message : d));
    });

    setTimeout(() => {
      if (!started) reject(new Error('Ninguém entrou na sala em ' + cfg.wait + 's.'));
    }, (cfg.wait + 12) * 1000);
  });
}

// -------------------- resumo --------------------
function printSummary(leaderboard) {
  console.log('\n================ RESULTADO DA SIMULAÇÃO ================');
  console.log(pad('aluno', 12) + pad('respostas', 11) + pad('acertos', 9) +
    pad('acerto', 8) + pad('tempo méd.', 12) + 'quedas');
  profiles.forEach((p) => {
    const avg = p.answered ? (p.totalDelay / p.answered) : 0;
    const rate = p.answered ? Math.round((p.correct / p.answered) * 100) : 0;
    console.log(pad(p.nickname, 12) + pad(p.answered, 11) + pad(p.correct, 9) +
      pad(rate + '%', 8) + pad(avg.toFixed(1) + 's', 12) + p.disconnects);
  });
  const skipped = profiles.reduce((a, p) => a + p.skipped, 0);
  const drops = profiles.reduce((a, p) => a + p.disconnects, 0);
  console.log('\n  pulos (tempo esgotado): ' + skipped + ' | reconexões simuladas: ' + drops);

  if (leaderboard && leaderboard.length) {
    console.log('\n  Placar final do servidor:');
    leaderboard.forEach((p, i) => {
      console.log('   ' + (i + 1) + '. ' + pad(p.nickname, 12) + p.score + ' pts');
    });
  }
  console.log('========================================================\n');
}

// -------------------- execução --------------------
async function main() {
  console.log('\n🤖 Simulador de turma — ' + cfg.url);
  console.log('   turma: ' + cfg.className + ' | alunos: ' + botNames.join(', '));

  const info = await loadQuizInfo();
  quiz = info.data;
  const mapped = await loadAnswerMap(info.available);
  console.log('   quiz de referência: ' + info.name + ' (' + (quiz.questions || []).length +
    ' perguntas) | gabaritos indexados: ' + mapped + ' perguntas de ' + info.available.length + ' quizzes');

  describeProfiles();

  let hostPromise = null;
  if (cfg.password) {
    const cookie = await hostLogin();
    hostPromise = runHost(cookie, info.name, profiles.length);
  }

  profiles.forEach((p, i) => createBot(p).connect(500 + i * 250));

  if (hostPromise) {
    const leaderboard = await hostPromise;
    finished = true;
    await sleep(1200);
    printSummary(leaderboard);
    setTimeout(() => { sockets.forEach((s) => { try { s.close(); } catch (e) {} }); process.exit(0); }, 500);
  } else {
    console.log('\nAlunos conectados. Agora abra /host no navegador, escolha a turma e o quiz, ' +
      'clique em "Aguardar jogadores" e em "Iniciar Jogo". Ctrl+C para parar.\n');
    process.on('SIGINT', () => {
      finished = true;
      console.log('\nEncerrando…');
      printSummary([]);
      sockets.forEach((s) => { try { s.close(); } catch (e) {} });
      process.exit(0);
    });
  }
}

main().catch((err) => {
  console.error('\n❌ ' + err.message + '\n');
  sockets.forEach((s) => { try { s.close(); } catch (e) {} });
  process.exit(1);
});
