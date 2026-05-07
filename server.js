const fs = require('fs');
const path = require('path');
const http = require('http');
const os = require('os');
const crypto = require('crypto');
const AdmZip = require('adm-zip');
const express = require('express');
const session = require('express-session');
const multer = require('multer');
const next = require('next');
const { Server } = require('socket.io');

const rootDir = __dirname;
let staticDir = path.join(rootDir, 'static');
let privateDir = path.join(rootDir, '.private');
let quizzesDir = path.join(staticDir, 'quizzes');
let figuresDir = path.join(staticDir, 'quiz-figures');
let graphsDir = path.join(staticDir, 'graphs');
let scoresDir = path.join(rootDir, 'scores');
let usersFile = path.join(privateDir, 'users.json');
let configFile = path.join(privateDir, 'config.json');
let gameSaveFile = path.join(privateDir, 'game_save.json');

const STATE_LOBBY = 0;
const STATE_QUESTION = 1;
const STATE_ANSWER = 2;
const STATE_GAMEOVER = 3;

const QUESTION_DURATION_MS = Number(process.env.QUESTION_DURATION_MS || 30000);

const playerSessions = new Map();
let registeredUsers = new Map();
let quizData = null;
let questionTimeoutId = null;
const gameState = {
  hostSid: null,
  players: {},
  currentQuestion: -1,
  answers: {},
  scores: {},
  state: STATE_LOBBY,
  questionDeadline: null
};

function configurePaths() {
  const dataRoot = process.env.QUIZ_DATA_DIR
    ? path.resolve(process.env.QUIZ_DATA_DIR)
    : rootDir;

  staticDir = process.env.QUIZ_STATIC_DIR
    ? path.resolve(process.env.QUIZ_STATIC_DIR)
    : path.join(dataRoot, 'static');

  privateDir = process.env.QUIZ_PRIVATE_DIR
    ? path.resolve(process.env.QUIZ_PRIVATE_DIR)
    : path.join(dataRoot, '.private');

  quizzesDir = process.env.QUIZ_QUIZZES_DIR
    ? path.resolve(process.env.QUIZ_QUIZZES_DIR)
    : path.join(staticDir, 'quizzes');

  figuresDir = process.env.QUIZ_FIGURES_DIR
    ? path.resolve(process.env.QUIZ_FIGURES_DIR)
    : path.join(staticDir, 'quiz-figures');

  graphsDir = process.env.QUIZ_GRAPHS_DIR
    ? path.resolve(process.env.QUIZ_GRAPHS_DIR)
    : path.join(staticDir, 'graphs');

  scoresDir = process.env.QUIZ_SCORES_DIR
    ? path.resolve(process.env.QUIZ_SCORES_DIR)
    : path.join(dataRoot, 'scores');

  usersFile = path.join(privateDir, 'users.json');
  configFile = path.join(privateDir, 'config.json');
  gameSaveFile = path.join(privateDir, 'game_save.json');
}

function createInitialGameState() {
  return {
    hostSid: null,
    players: {},
    currentQuestion: -1,
    answers: {},
    scores: {},
    state: STATE_LOBBY,
    questionDeadline: null
  };
}

function resetInMemoryState() {
  playerSessions.clear();
  registeredUsers = new Map();
  quizData = null;
  clearQuestionTimer();
  gameState.hostSid = null;
  gameState.players = {};
  gameState.currentQuestion = -1;
  gameState.answers = {};
  gameState.scores = {};
  gameState.state = STATE_LOBBY;
  gameState.questionDeadline = null;
}

function ensureDirectories() {
  for (const dir of [privateDir, quizzesDir, figuresDir, graphsDir, scoresDir]) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function sha256(text) {
  return crypto.createHash('sha256').update(text).digest('hex');
}

function readJsonFile(filePath, fallbackValue) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'));
  } catch {
    return fallbackValue;
  }
}

function writeJsonFile(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

function getLocalIPv4Address() {
  const interfaces = os.networkInterfaces();
  for (const entries of Object.values(interfaces)) {
    for (const entry of entries || []) {
      if (entry && entry.family === 'IPv4' && !entry.internal) {
        return entry.address;
      }
    }
  }

  return '127.0.0.1';
}

function getServerDisplayUrl(req) {
  const forwardedHost = String(req.headers['x-forwarded-host'] || req.headers.host || '');
  const portFromHeader = forwardedHost.includes(':') ? forwardedHost.split(':').pop() : '';
  const port = portFromHeader || String(process.env.PORT || 5000);
  const ipAddress = process.env.SERVER_IP || process.env.HOST_IP || getLocalIPv4Address();
  return `http://${ipAddress}:${port}`;
}

function loadConfig() {
  const defaultAdminPassword = process.env.ADMIN_PASSWORD || 'admin123';
  const existing = readJsonFile(configFile, null);
  const config = {
    sessionSecret: crypto.randomBytes(32).toString('hex'),
    adminPasswordHash: sha256(defaultAdminPassword),
    ...(existing && typeof existing === 'object' ? existing : {})
  };

  if (!config.sessionSecret) {
    config.sessionSecret = crypto.randomBytes(32).toString('hex');
  }

  if (!config.adminPasswordHash) {
    config.adminPasswordHash = sha256(defaultAdminPassword);
  }

  writeJsonFile(configFile, config);
  if (!existing) {
    console.log(`Admin password initialized to: ${defaultAdminPassword}`);
  }
  return config;
}

function loadUsers() {
  const data = readJsonFile(usersFile, []);
  if (!Array.isArray(data)) {
    writeJsonFile(usersFile, []);
    return new Map();
  }

  const users = new Map();
  for (const entry of data) {
    if (typeof entry === 'string' && entry.trim()) {
      users.set(entry.trim().toLowerCase(), entry.trim());
    }
  }
  return users;
}

function saveFullState() {
  const state = {
    gameState: {
      hostSid: gameState.hostSid,
      players: gameState.players,
      currentQuestion: gameState.currentQuestion,
      answers: gameState.answers,
      scores: gameState.scores,
      state: gameState.state,
      questionDeadline: gameState.questionDeadline
    },
    playerSessions: Object.fromEntries(playerSessions.entries()),
    quizData
  };

  try {
    writeJsonFile(gameSaveFile, state);
  } catch (error) {
    console.error('Failed to save game state:', error);
  }
}

function loadFullState() {
  if (!fs.existsSync(gameSaveFile)) {
    return null;
  }

  const state = readJsonFile(gameSaveFile, null);
  if (!state || typeof state !== 'object' || !state.gameState) {
    return null;
  }

  return state;
}

function restoreFullState() {
  const state = loadFullState();
  if (!state) {
    return false;
  }

  const restoredGameState = state.gameState;
  gameState.hostSid = null;
  gameState.players = restoredGameState.players || {};
  gameState.currentQuestion = typeof restoredGameState.currentQuestion === 'number' ? restoredGameState.currentQuestion : -1;
  gameState.answers = restoredGameState.answers || {};
  gameState.scores = restoredGameState.scores || {};
  gameState.state = typeof restoredGameState.state === 'number' ? restoredGameState.state : STATE_LOBBY;
  gameState.questionDeadline = typeof restoredGameState.questionDeadline === 'number'
    ? restoredGameState.questionDeadline
    : null;

  playerSessions.clear();
  for (const [token, sessionData] of Object.entries(state.playerSessions || {})) {
    playerSessions.set(token, sessionData);
  }

  quizData = state.quizData || null;
  return true;
}

function clearGameState() {
  gameState.hostSid = null;
  gameState.players = {};
  gameState.currentQuestion = -1;
  gameState.answers = {};
  gameState.scores = {};
  gameState.state = STATE_LOBBY;
  gameState.questionDeadline = null;
}

function clearQuestionTimer() {
  if (questionTimeoutId) {
    clearTimeout(questionTimeoutId);
    questionTimeoutId = null;
  }
}

function finalizeQuestionResults(io) {
  if (!quizData || gameState.state !== STATE_QUESTION) {
    return;
  }

  const questionData = quizData.questions[gameState.currentQuestion];
  if (!questionData) {
    return;
  }

  const correctOptionIndex = resolveCorrectOptionIndex(questionData);

  for (const [sid, answer] of Object.entries(gameState.answers)) {
    if (Number(answer) === correctOptionIndex) {
      gameState.scores[sid] = (gameState.scores[sid] || 0) + 10;
    }
  }

  const payload = buildResultsPayload(questionData, gameState.currentQuestion);
  io.emit('show_results', payload);

  clearQuestionTimer();
  gameState.questionDeadline = null;
  gameState.state = STATE_ANSWER;
  saveFullState();
}

function handleQuestionTimeout(io) {
  clearQuestionTimer();
  if (gameState.state !== STATE_QUESTION || gameState.currentQuestion < 0) {
    return;
  }

  gameState.questionDeadline = Date.now();
  io.emit('question_time_over', {
    question_index: gameState.currentQuestion
  });
  finalizeQuestionResults(io);
}

function scheduleQuestionTimer(io) {
  clearQuestionTimer();
  if (!gameState.questionDeadline || gameState.state !== STATE_QUESTION) {
    return;
  }

  const msLeft = gameState.questionDeadline - Date.now();
  if (msLeft <= 0) {
    handleQuestionTimeout(io);
    return;
  }

  questionTimeoutId = setTimeout(() => handleQuestionTimeout(io), msLeft);
}

function deleteSavedGameFile() {
  if (fs.existsSync(gameSaveFile)) {
    fs.unlinkSync(gameSaveFile);
  }
}

function saveUsers() {
  writeJsonFile(usersFile, Array.from(registeredUsers.values()));
}

function listQuizzes() {
  return fs
    .readdirSync(quizzesDir)
    .filter((file) => file.endsWith('.json'))
    .map((file) => file.slice(0, -5))
    .sort((left, right) => left.localeCompare(right));
}

function loadQuiz(quizName) {
  const filePath = path.join(quizzesDir, `${quizName}.json`);
  if (!fs.existsSync(filePath)) {
    return null;
  }

  const data = readJsonFile(filePath, null);
  if (!data || typeof data !== 'object' || typeof data.title !== 'string' || !Array.isArray(data.questions)) {
    return null;
  }

  return data;
}

function saveQuiz(quizName, data) {
  writeJsonFile(path.join(quizzesDir, `${quizName}.json`), data);
}

function nextAvailableQuizName(baseName) {
  const safeBaseName = sanitizeQuizName(baseName);
  let quizName = safeBaseName;
  let index = 1;

  while (fs.existsSync(path.join(quizzesDir, `${quizName}.json`))) {
    quizName = `${safeBaseName}_${index}`;
    index += 1;
  }

  return quizName;
}

function sanitizeQuizName(name) {
  return String(name || '')
    .trim()
    .replace(/[^a-zA-Z0-9_-]/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '') || `quiz_${Date.now()}`;
}

function exportScoresToCsv(scores, players) {
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\..+/, '').replace('T', '_');
  const filePath = path.join(scoresDir, `scores_${timestamp}.csv`);
  const lines = ['Jogador,Pontuação'];

  for (const [sid, score] of Object.entries(scores)) {
    const nickname = String(players[sid] || 'Desconhecido').replace(/"/g, '""');
    lines.push(`"${nickname}",${score}`);
  }

  fs.writeFileSync(filePath, `${lines.join('\n')}\n`, 'utf8');
  console.log(`Resultados exportados para ${path.relative(rootDir, filePath)}`);
}

function createLeaderboard() {
  return Object.entries(gameState.players)
    .map(([sid, nickname]) => ({ nickname, score: gameState.scores[sid] || 0 }))
    .sort((left, right) => right.score - left.score || left.nickname.localeCompare(right.nickname));
}

function resetGameForNewQuiz() {
  gameState.currentQuestion = -1;
  gameState.answers = {};
  gameState.scores = {};
  gameState.state = STATE_LOBBY;
  for (const sid of Object.keys(gameState.players)) {
    gameState.scores[sid] = 0;
  }
}

function getAnswerDistribution(questionData) {
  const answerDistribution = new Array(questionData.options.length).fill(0);
  for (const answer of Object.values(gameState.answers)) {
    const index = Number(answer);
    if (Number.isInteger(index) && index >= 0 && index < answerDistribution.length) {
      answerDistribution[index] += 1;
    }
  }
  return answerDistribution;
}

function buildQuestionPayload(questionData, questionIndex) {
  return {
    text: questionData.text,
    options: questionData.options,
    question_index: questionIndex,
    total_questions: quizData.questions.length,
    chart_path: loadQuestionFigure(questionData),
    state: gameState.state,
    question_deadline: gameState.questionDeadline,
    question_duration_ms: QUESTION_DURATION_MS
  };
}

function resolveCorrectOptionIndex(questionData) {
  const options = Array.isArray(questionData.options) ? questionData.options : [];
  const optionCount = options.length;
  if (optionCount === 0) {
    return 0;
  }

  const rawValue = questionData.correct_option;
  if (Number.isInteger(rawValue) && rawValue >= 0 && rawValue < optionCount) {
    return rawValue;
  }

  if (typeof rawValue === 'number' && Number.isFinite(rawValue)) {
    const rounded = Math.round(rawValue);
    if (rounded >= 0 && rounded < optionCount) {
      return rounded;
    }
    if (rounded >= 1 && rounded <= optionCount) {
      return rounded - 1;
    }
  }

  if (typeof rawValue === 'string') {
    const value = rawValue.trim();
    if (/^\d+$/.test(value)) {
      const numeric = Number(value);
      if (numeric >= 0 && numeric < optionCount) {
        return numeric;
      }
      if (numeric >= 1 && numeric <= optionCount) {
        return numeric - 1;
      }
    }

    const letterMatch = value.match(/^([A-Za-z])/);
    if (letterMatch) {
      const index = letterMatch[1].toUpperCase().charCodeAt(0) - 65;
      if (index >= 0 && index < optionCount) {
        return index;
      }
    }
  }

  return 0;
}

function buildResultsPayload(questionData, questionIndex) {
  const correctOptionIndex = resolveCorrectOptionIndex(questionData);
  const correctOptionText = questionData.options[correctOptionIndex];
  const answerDistribution = getAnswerDistribution(questionData);

  return {
    correct_option: correctOptionIndex,
    correct_option_text: `${String.fromCharCode(65 + correctOptionIndex)}) ${correctOptionText}`,
    scores: gameState.scores,
    players: gameState.players,
    answer_distribution: answerDistribution,
    chart_path: saveAnswerDistributionChart(answerDistribution, questionData, questionIndex)
  };
}

function broadcastCurrentGame(io, socket) {
  if (!quizData || !Array.isArray(quizData.questions) || gameState.currentQuestion < 0) {
    return;
  }

  const questionData = quizData.questions[gameState.currentQuestion];
  if (!questionData) {
    return;
  }

  if (gameState.state === STATE_QUESTION) {
    const payload = buildQuestionPayload(questionData, gameState.currentQuestion);
    io.emit('show_question', payload);
  } else if (gameState.state === STATE_ANSWER) {
    const payload = buildResultsPayload(questionData, gameState.currentQuestion);
    io.emit('show_results', payload);
  }

  if (socket && gameState.hostSid) {
    socket.emit('update_player_list', Object.values(gameState.players));
  }
}

function generateSvgChart(answerDistribution, questionIndex) {
  const width = 720;
  const height = 420;
  const padding = 52;
  const maxValue = Math.max(1, ...answerDistribution);
  const chartHeight = height - padding * 2;
  const chartWidth = width - padding * 2;
  const barGap = 18;
  const barWidth = (chartWidth - barGap * (answerDistribution.length - 1)) / Math.max(1, answerDistribution.length);
  const colors = ['#ef4444', '#3b82f6', '#f59e0b', '#22c55e'];

  const bars = answerDistribution
    .map((value, index) => {
      const barHeight = (value / maxValue) * chartHeight;
      const x = padding + index * (barWidth + barGap);
      const y = height - padding - barHeight;
      const labelX = x + barWidth / 2;
      return `
        <rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="18" fill="${colors[index % colors.length]}" />
        <text x="${labelX.toFixed(1)}" y="${(y - 12).toFixed(1)}" text-anchor="middle" fill="#0f172a" font-size="20" font-weight="700">${value}</text>
        <text x="${labelX.toFixed(1)}" y="${height - 18}" text-anchor="middle" fill="#475569" font-size="18" font-weight="700">${String.fromCharCode(65 + index)}</text>`;
    })
    .join('\n');

  const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
  <rect width="100%" height="100%" rx="28" fill="#f8fafc"/>
  <text x="50%" y="34" text-anchor="middle" fill="#0f172a" font-size="24" font-weight="800">Distribuição das respostas - Pergunta ${questionIndex + 1}</text>
  <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" stroke="#cbd5e1" stroke-width="2"/>
  <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" stroke="#cbd5e1" stroke-width="2"/>
  ${bars}
</svg>`;

  const fileName = `q${questionIndex + 1}_results.svg`;
  fs.writeFileSync(path.join(graphsDir, fileName), svg, 'utf8');
  return `/static/graphs/${fileName}`;
}

function saveAnswerDistributionChart(answerDistribution, questionData, questionIndex) {
  if (!Array.isArray(answerDistribution) || answerDistribution.length === 0) {
    return '';
  }

  try {
    return generateSvgChart(answerDistribution, questionIndex);
  } catch (error) {
    console.error('Falha ao salvar grafico de respostas:', error);
    return '';
  }
}

function loadQuestionFigure(questionData) {
  if (!questionData.figure || questionData.figure === 'none') {
    return '';
  }
  return `/static/quiz-figures/${questionData.figure}`;
}

function buildQuizArchiveBuffer(data) {
  const zip = new AdmZip();
  zip.addFile('quiz.json', Buffer.from(JSON.stringify(data, null, 2), 'utf8'));

  for (const question of data.questions || []) {
    const figure = question.figure;
    if (!figure || figure === 'none') {
      continue;
    }

    const figurePath = path.join(figuresDir, figure);
    if (fs.existsSync(figurePath)) {
      zip.addLocalFile(figurePath, 'figures', figure);
    }
  }

  return zip.toBuffer();
}

function readQuizDataFromBuffer(buffer) {
  try {
    const zip = new AdmZip(buffer);
    const quizEntry = zip.getEntry('quiz.json');

    if (quizEntry) {
      return {
        format: 'zip',
        quizData: JSON.parse(zip.readAsText(quizEntry, 'utf8')),
        zip
      };
    }
  } catch {
    // Fall back to legacy plain JSON .quiz files.
  }

  const text = buffer.toString('utf8').trim();
  if (!text) {
    throw new Error('Arquivo .quiz vazio');
  }

  return {
    format: 'json',
    quizData: JSON.parse(text)
  };
}

function importQuizArchiveBuffer(buffer) {
  const imported = readQuizDataFromBuffer(buffer);
  const quizDataFromArchive = imported.quizData;
  if (!quizDataFromArchive || typeof quizDataFromArchive !== 'object' || typeof quizDataFromArchive.title !== 'string' || !Array.isArray(quizDataFromArchive.questions)) {
    throw new Error('quiz.json mal formatado (faltando title ou questions)');
  }

  if (imported.format === 'zip') {
    const figureEntries = new Map();
    for (const entry of imported.zip.getEntries()) {
      if ((entry.entryName.startsWith('figures/') || entry.entryName.startsWith('quiz-figures/')) && !entry.isDirectory) {
        figureEntries.set(path.basename(entry.entryName), entry.getData());
      }
    }

    for (const question of quizDataFromArchive.questions) {
      const figure = question.figure;
      if (!figure || figure === 'none') {
        continue;
      }

      const figureData = figureEntries.get(path.basename(figure));
      if (!figureData) {
        question.figure = 'none';
        continue;
      }

      const extension = path.extname(figure).toLowerCase().replace('.', '') || 'png';
      const uniqueName = `${crypto.createHash('md5').update(`${Date.now()}${figure}`).digest('hex')}.${extension}`;
      fs.writeFileSync(path.join(figuresDir, uniqueName), figureData);
      question.figure = uniqueName;
    }
  }

  const baseName = sanitizeQuizName(quizDataFromArchive.title);
  const quizName = nextAvailableQuizName(baseName);
  saveQuiz(quizName, quizDataFromArchive);

  return { quizName, quizData: quizDataFromArchive };
}

function advanceQuestion(io) {
  if (!quizData || !Array.isArray(quizData.questions)) {
    return;
  }

  gameState.answers = {};
  gameState.currentQuestion += 1;
  gameState.state = STATE_QUESTION;
  gameState.questionDeadline = Date.now() + QUESTION_DURATION_MS;

  if (gameState.currentQuestion >= quizData.questions.length) {
    const leaderboard = createLeaderboard();
    exportScoresToCsv(gameState.scores, gameState.players);
    io.emit('game_over', leaderboard);
    clearGameState();
    quizData = null;
    deleteSavedGameFile();
    return;
  }

  const questionData = quizData.questions[gameState.currentQuestion];
  io.emit('show_question', buildQuestionPayload(questionData, gameState.currentQuestion));
  scheduleQuestionTimer(io);

  if (gameState.hostSid) {
    io.to(gameState.hostSid).emit('update_answer_count', {
      answered: 0,
      total: Object.keys(gameState.players).length
    });
  }

  saveFullState();
}

function finishQuiz(io) {
  const leaderboard = createLeaderboard();
  exportScoresToCsv(gameState.scores, gameState.players);
  io.emit('game_over', leaderboard);
  clearGameState();
  playerSessions.clear();
  quizData = null;
  deleteSavedGameFile();
}

async function createServer({ useNext = true } = {}) {
  configurePaths();
  resetInMemoryState();
  ensureDirectories();
  const config = loadConfig();
  registeredUsers = loadUsers();
  const restored = restoreFullState();
  console.log(`--- ${registeredUsers.size} usuários carregados de ${path.relative(rootDir, usersFile)} ---`);
  console.log(restored ? 'Server resumed with saved game state.' : 'No saved game state found. Starting fresh.');

  let handle = (req, res) => res.status(404).end();
  if (useNext) {
    const dev = process.env.NODE_ENV !== 'production';
    const nextApp = next({ dev, dir: rootDir });
    handle = nextApp.getRequestHandler();
    await nextApp.prepare();
  }

  const app = express();
  const server = http.createServer(app);
  const upload = multer({ storage: multer.memoryStorage() });
  const sessionMiddleware = session({
    secret: config.sessionSecret,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      sameSite: 'lax'
    }
  });

  const io = new Server(server, {
    maxHttpBufferSize: 10e6
  });

  app.use(express.json({ limit: '10mb' }));
  app.use(express.urlencoded({ extended: true }));
  app.use(sessionMiddleware);
  app.use('/static', express.static(staticDir));
  app.use('/scores', express.static(scoresDir));

  app.get('/api/quizzes', (req, res) => {
    res.json(listQuizzes());
  });

  app.get('/api/quiz/:quizName', (req, res) => {
    const quiz = loadQuiz(req.params.quizName);
    if (!quiz) {
      res.status(404).json({ error: 'Quiz not found' });
      return;
    }
    res.json(quiz);
  });

  app.post('/api/quiz/export', (req, res) => {
    const data = req.body;
    if (!data || typeof data.title !== 'string' || !Array.isArray(data.questions)) {
      res.status(400).json({ error: 'Dados do quiz inválidos' });
      return;
    }

    const safeTitle = sanitizeQuizName(data.title);
    const exportData = {
      title: data.title,
      questions: data.questions
    };
    const buffer = Buffer.from(JSON.stringify(exportData, null, 2), 'utf8');
    res.setHeader('Content-Type', 'application/json');
    res.setHeader('Content-Disposition', `attachment; filename="${safeTitle}.quiz"`);
    res.send(buffer);
  });

  app.post('/api/quiz/import', upload.single('file'), (req, res) => {
    if (!req.file) {
      res.status(400).json({ error: 'Nenhum arquivo enviado' });
      return;
    }

    if (!req.file.originalname.endsWith('.quiz')) {
      res.status(400).json({ error: 'O arquivo deve ter extensão .quiz' });
      return;
    }

    try {
      const result = importQuizArchiveBuffer(req.file.buffer);
      res.json({
        success: true,
        quiz_name: result.quizName,
        quiz_data: result.quizData
      });
    } catch (error) {
      res.status(400).json({ error: error.message || 'Erro ao processar o arquivo' });
    }
  });

  app.post('/api/quiz/:quizName', (req, res) => {
    const data = req.body;
    if (!data || typeof data.title !== 'string' || !Array.isArray(data.questions)) {
      res.status(400).json({ error: 'Invalid quiz data' });
      return;
    }

    const safeName = sanitizeQuizName(req.params.quizName);
    saveQuiz(safeName, data);
    res.json({ message: 'Quiz saved successfully', name: safeName });
  });

  app.delete('/api/quiz/:quizName', (req, res) => {
    const safeName = sanitizeQuizName(req.params.quizName);
    const filePath = path.join(quizzesDir, `${safeName}.json`);
    if (!fs.existsSync(filePath)) {
      res.status(404).json({ error: 'Quiz not found' });
      return;
    }

    fs.unlinkSync(filePath);
    res.json({ message: 'Quiz deleted' });
  });

  app.post(['/api/upload_image', '/api/upload-image'], upload.single('image'), (req, res) => {
    const file = req.file;
    if (!file) {
      res.status(400).json({ error: 'No image part' });
      return;
    }

    const extension = path.extname(file.originalname || '').toLowerCase().replace('.', '');
    if (!['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(extension)) {
      res.status(400).json({ error: 'File type not allowed' });
      return;
    }

    const uniqueName = `${crypto.createHash('md5').update(`${Date.now()}${file.originalname}`).digest('hex')}.${extension}`;
    fs.writeFileSync(path.join(figuresDir, uniqueName), file.buffer);
    res.json({ filename: uniqueName, url: `/static/quiz-figures/${uniqueName}` });
  });

  app.get(['/check_session', '/api/check-session'], (req, res) => {
    const token = String(req.query.token || '');
    if (!token || !playerSessions.has(token)) {
      res.json({ valid: false });
      return;
    }

    const sessionData = playerSessions.get(token);
    if (gameState.players[sessionData.sid]) {
      res.json({ valid: true, nickname: sessionData.nickname });
      return;
    }

    res.json({ valid: false });
  });

  app.post('/api/admin/login', (req, res) => {
    const password = String(req.body.password || '').trim();
    if (!password) {
      res.status(400).json({ error: 'Password is required' });
      return;
    }

    if (sha256(password) !== config.adminPasswordHash) {
      res.status(401).json({ error: 'Senha incorreta!' });
      return;
    }

    req.session.adminLoggedIn = true;
    req.session.save(() => {
      res.json({ success: true });
    });
  });

  app.post('/api/host/login', (req, res) => {
    const password = String(req.body.password || '').trim();
    if (!password) {
      res.status(400).json({ error: 'Password is required' });
      return;
    }

    if (sha256(password) !== config.adminPasswordHash) {
      res.status(401).json({ error: 'Senha incorreta!' });
      return;
    }

    req.session.hostLoggedIn = true;
    req.session.save(() => {
      res.json({ success: true });
    });
  });

  app.post('/api/host/logout', (req, res) => {
    req.session.destroy(() => {
      res.json({ success: true });
    });
  });

  app.get('/api/host/session', (req, res) => {
    res.json({
      loggedIn: Boolean(req.session.hostLoggedIn),
      serverUrl: getServerDisplayUrl(req)
    });
  });

  app.post('/api/admin/logout', (req, res) => {
    req.session.destroy(() => {
      res.json({ success: true });
    });
  });

  app.get('/api/admin/session', (req, res) => {
    res.json({ loggedIn: Boolean(req.session.adminLoggedIn) });
  });

  app.use((req, res, nextFn) => {
    if (req.method === 'GET') {
      if (req.path === '/host' || req.path.startsWith('/host/')) {
        if (req.path !== '/host/login' && !req.session.hostLoggedIn) {
          res.redirect('/host/login');
          return;
        }
        if (req.path === '/host/login' && req.session.hostLoggedIn) {
          res.redirect('/host');
          return;
        }
      }
      if (req.path === '/admin' || req.path.startsWith('/admin/')) {
        if (req.path !== '/admin/login' && !req.session.adminLoggedIn) {
          res.redirect('/admin/login');
          return;
        }
        if (req.path === '/admin/login' && req.session.adminLoggedIn) {
          res.redirect('/admin');
          return;
        }
      }
    }
    nextFn();
  });

  app.all('*', (req, res) => handle(req, res));

  io.use((socket, nextFn) => {
    sessionMiddleware(socket.request, {}, nextFn);
  });

  io.on('connect', (socket) => {
    console.log(`Cliente conectado: ${socket.id}`);

    socket.on('disconnect', () => {
      console.log(`Cliente desconectado: ${socket.id}`);

      if (socket.id === gameState.hostSid) {
        console.log('Host desconectou. Salvando estado e pausando o jogo.');
        gameState.hostSid = null;
        saveFullState();
        io.emit('host_disconnected', {
          message: 'O apresentador desconectou. Aguarde a reconexão para retomar o jogo.'
        });
        return;
      }

      if (gameState.players[socket.id]) {
        const nickname = gameState.players[socket.id];
        if (gameState.hostSid) {
          io.to(gameState.hostSid).emit('player_left', { nickname });
        }
      }
    });

    socket.on('host_join', () => {
      if (!socket.request.session.hostLoggedIn) {
        socket.emit('admin_error', { message: 'Você precisa estar logado como anfitrião para controlar o jogo.' });
        return;
      }

      if (gameState.hostSid && gameState.hostSid !== socket.id) {
        socket.emit('admin_error', { message: 'Já existe um anfitrião conectado.' });
        return;
      }

      if (gameState.players && Object.keys(gameState.players).length > 0) {
        gameState.hostSid = socket.id;
        socket.emit('update_player_list', Object.values(gameState.players));
        socket.emit('resume_host_state', {
          current_question: gameState.currentQuestion,
          state: gameState.state,
          total_players: Object.keys(gameState.players).length,
          answered_count: Object.keys(gameState.answers).length,
          question_deadline: gameState.questionDeadline,
          question_duration_ms: QUESTION_DURATION_MS
        });
        io.emit('host_reconnected', { message: 'O apresentador reconectou. O jogo vai continuar.' });

        if (gameState.state === STATE_QUESTION && gameState.currentQuestion >= 0 && quizData) {
          const questionData = quizData.questions[gameState.currentQuestion];
          if (questionData) {
            io.emit('show_question', buildQuestionPayload(questionData, gameState.currentQuestion));
            scheduleQuestionTimer(io);
          }
        } else if (gameState.state === STATE_ANSWER && gameState.currentQuestion >= 0 && quizData) {
          const questionData = quizData.questions[gameState.currentQuestion];
          if (questionData) {
            io.emit('show_results', buildResultsPayload(questionData, gameState.currentQuestion));
            clearQuestionTimer();
          }
        }
        return;
      }

      gameState.hostSid = socket.id;
      socket.emit('update_player_list', Object.values(gameState.players));

      if (gameState.currentQuestion >= 0 && quizData) {
        socket.emit('resume_host_state', {
          current_question: gameState.currentQuestion,
          state: gameState.state,
          total_players: Object.keys(gameState.players).length,
          answered_count: Object.keys(gameState.answers).length,
          question_deadline: gameState.questionDeadline,
          question_duration_ms: QUESTION_DURATION_MS
        });
        if (gameState.state === STATE_QUESTION) {
          io.emit('show_question', buildQuestionPayload(quizData.questions[gameState.currentQuestion], gameState.currentQuestion));
          scheduleQuestionTimer(io);
        } else if (gameState.state === STATE_ANSWER) {
          io.emit('show_results', buildResultsPayload(quizData.questions[gameState.currentQuestion], gameState.currentQuestion));
          clearQuestionTimer();
        }
      }
    });

    socket.on('admin_join', () => {
      if (!socket.request.session.adminLoggedIn) {
        socket.emit('admin_error', { message: 'Acesso negado.' });
        return;
      }

      socket.emit('update_user_list', Array.from(registeredUsers.values()).sort((a, b) => a.localeCompare(b)));
    });

    socket.on('add_user', (data) => {
      if (!socket.request.session.adminLoggedIn) {
        return;
      }

      const nickname = String(data && data.nickname ? data.nickname : '').trim();
      const key = nickname.toLowerCase();
      if (!nickname) {
        return;
      }

      if (registeredUsers.has(key)) {
        socket.emit('admin_error', { message: `O nome "${nickname}" (ou variação) já existe.` });
        return;
      }

      registeredUsers.set(key, nickname);
      saveUsers();
      io.emit('update_user_list', Array.from(registeredUsers.values()).sort((a, b) => a.localeCompare(b)));
    });

    socket.on('remove_user', (data) => {
      if (!socket.request.session.adminLoggedIn) {
        return;
      }

      const nickname = String(data && data.nickname ? data.nickname : '').trim();
      const key = nickname.toLowerCase();
      if (!registeredUsers.has(key)) {
        return;
      }

      registeredUsers.delete(key);
      saveUsers();
      io.emit('update_user_list', Array.from(registeredUsers.values()).sort((a, b) => a.localeCompare(b)));
    });

    socket.on('edit_user', (data) => {
      if (!socket.request.session.adminLoggedIn) {
        return;
      }

      const oldNickname = String(data && data.old_nickname ? data.old_nickname : '').trim();
      const newNickname = String(data && data.new_nickname ? data.new_nickname : '').trim();
      const oldKey = oldNickname.toLowerCase();
      const newKey = newNickname.toLowerCase();

      if (!oldNickname || !newNickname) {
        socket.emit('admin_error', { message: 'O novo nome não pode ser vazio.' });
        return;
      }

      if (!registeredUsers.has(oldKey)) {
        socket.emit('admin_error', { message: 'Usuário original não encontrado.' });
        return;
      }

      if (oldKey !== newKey && registeredUsers.has(newKey)) {
        socket.emit('admin_error', { message: `O nome "${newNickname}" (ou variação) já existe.` });
        return;
      }

      registeredUsers.delete(oldKey);
      registeredUsers.set(newKey, newNickname);
      saveUsers();
      io.emit('update_user_list', Array.from(registeredUsers.values()).sort((a, b) => a.localeCompare(b)));
    });

    socket.on('player_join', (data) => {
      const nickname = String(data && data.nickname ? data.nickname : '').trim();
      if (!nickname) {
        return;
      }

      const key = nickname.toLowerCase();
      if (!registeredUsers.has(key)) {
        socket.emit('join_failed', { reason: 'Usuário não cadastrado. Fale com o administrador.' });
        return;
      }

      const canonicalName = registeredUsers.get(key);
      if (Object.values(gameState.players).includes(canonicalName)) {
        socket.emit('join_failed', { reason: 'Este usuário já está no jogo.' });
        return;
      }

      gameState.players[socket.id] = canonicalName;
      gameState.scores[socket.id] = 0;

      const sessionToken = crypto.randomBytes(16).toString('hex');
      playerSessions.set(sessionToken, {
        sid: socket.id,
        nickname: canonicalName
      });

      if (gameState.hostSid) {
        io.to(gameState.hostSid).emit('update_player_list', Object.values(gameState.players));
      }

      socket.emit('join_success', {
        nickname: canonicalName,
        session_token: sessionToken
      });
      saveFullState();
    });

    socket.on('restore_session', (data) => {
      const token = data && data.token ? String(data.token) : '';
      const newSid = data && data.new_sid ? String(data.new_sid) : socket.id;
      const sessionData = playerSessions.get(token);

      if (!sessionData || !gameState.players[sessionData.sid]) {
        socket.emit('session_restore_failed', { reason: 'Sessão não encontrada ou expirada' });
        return;
      }

      const oldSid = sessionData.sid;
      const nickname = sessionData.nickname;
      gameState.players[newSid] = gameState.players[oldSid];
      delete gameState.players[oldSid];
      gameState.scores[newSid] = gameState.scores[oldSid] || 0;
      delete gameState.scores[oldSid];

      if (Object.prototype.hasOwnProperty.call(gameState.answers, oldSid)) {
        gameState.answers[newSid] = gameState.answers[oldSid];
        delete gameState.answers[oldSid];
      }

      playerSessions.set(token, {
        sid: newSid,
        nickname
      });

      socket.emit('session_restored', {
        nickname,
        current_question: gameState.currentQuestion,
        current_score: gameState.scores[newSid] || 0,
        options: quizData && quizData.questions && quizData.questions[gameState.currentQuestion]
          ? quizData.questions[gameState.currentQuestion].options
          : [0, 1, 2, 3],
        state: gameState.state,
        question_deadline: gameState.questionDeadline,
        question_duration_ms: QUESTION_DURATION_MS
      });

      if (gameState.hostSid) {
        io.to(gameState.hostSid).emit('update_player_list', Object.values(gameState.players));
      }
    });

    socket.on('start_game', (data) => {
      if (socket.id !== gameState.hostSid) {
        return;
      }

      const quizName = data && data['quiz-name'] ? String(data['quiz-name']) : '';
      const loadedQuiz = loadQuiz(quizName);
      if (!loadedQuiz) {
        socket.emit('admin_error', { message: 'Quiz não encontrado.' });
        return;
      }

      quizData = loadedQuiz;
      resetGameForNewQuiz();
      saveFullState();
      advanceQuestion(io);
    });

    socket.on('next_question', () => {
      if (socket.id !== gameState.hostSid) {
        return;
      }

      advanceQuestion(io);
    });

    socket.on('show_results', () => {
      if (socket.id !== gameState.hostSid || !quizData) {
        return;
      }
      finalizeQuestionResults(io);
    });

    socket.on('submit_answer', (data) => {
      if (!gameState.players[socket.id]) {
        return;
      }

      if (gameState.questionDeadline && Date.now() > gameState.questionDeadline) {
        socket.emit('answer_rejected', { reason: 'Tempo esgotado.' });
        return;
      }

      const optionIndex = Number(data && data.option_index);
      gameState.answers[socket.id] = optionIndex;
      socket.emit('answer_received');

      if (gameState.hostSid) {
        io.to(gameState.hostSid).emit('update_answer_count', {
          answered: Object.keys(gameState.answers).length,
          total: Object.keys(gameState.players).length
        });
      }
      saveFullState();

      if (Object.keys(gameState.answers).length >= Object.keys(gameState.players).length) {
        finalizeQuestionResults(io);
      }
    });

    socket.on('force_end_quiz', () => {
      if (socket.id !== gameState.hostSid) {
        return;
      }

      const leaderboard = createLeaderboard();
      exportScoresToCsv(gameState.scores, gameState.players);
      io.emit('game_over', leaderboard);
      clearGameState();
      playerSessions.clear();
      quizData = null;
      deleteSavedGameFile();
      io.emit('game_reset');
      clearQuestionTimer();
    });

    socket.on('clear_saved_game', () => {
      if (socket.id !== gameState.hostSid) {
        return;
      }

      deleteSavedGameFile();
      clearGameState();
      playerSessions.clear();
      quizData = null;
      io.emit('game_reset');
      io.to(socket.id).emit('admin_error', { message: 'Jogo foi resetado completamente.' });
      clearQuestionTimer();
    });
  });

  if (gameState.state === STATE_QUESTION) {
    scheduleQuestionTimer(io);
  }

  return { app, server, io, config, restored };
}

async function main() {
  const { server } = await createServer({ useNext: true });
  const port = Number(process.env.PORT || 5000);
  server.listen(port, '0.0.0.0', () => {
    console.log('Servidor Node/Next iniciado!');
    const serverUrl = `http://${getLocalIPv4Address()}:${port}`;
    console.log(`Host: ${serverUrl}/host`);
    console.log(`Admin: ${serverUrl}/admin/login`);
    console.log(`Alunos: ${serverUrl}`);
  });
}

if (require.main === module) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}

module.exports = {
  createServer,
  configurePaths,
  resetInMemoryState
};