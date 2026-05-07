const fs = require('fs');
const os = require('os');
const path = require('path');

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

function createTestDataDir() {
  const baseDir = fs.mkdtempSync(path.join(os.tmpdir(), 'quiz-ufpa-'));
  const staticDir = path.join(baseDir, 'static');
  const quizzesDir = path.join(staticDir, 'quizzes');
  const figuresDir = path.join(staticDir, 'quiz-figures');
  const graphsDir = path.join(staticDir, 'graphs');
  const privateDir = path.join(baseDir, '.private');
  const scoresDir = path.join(baseDir, 'scores');

  fs.mkdirSync(quizzesDir, { recursive: true });
  fs.mkdirSync(figuresDir, { recursive: true });
  fs.mkdirSync(graphsDir, { recursive: true });
  fs.mkdirSync(privateDir, { recursive: true });
  fs.mkdirSync(scoresDir, { recursive: true });

  return {
    baseDir,
    staticDir,
    quizzesDir,
    figuresDir,
    graphsDir,
    privateDir,
    scoresDir
  };
}

function seedUsers(privateDir, users) {
  writeJson(path.join(privateDir, 'users.json'), users);
}

function seedQuiz(quizzesDir, quizName, quizData) {
  writeJson(path.join(quizzesDir, `${quizName}.json`), quizData);
}

async function startTestServer({ dataDir, useNext = false } = {}) {
  process.env.NODE_ENV = 'test';
  process.env.ADMIN_PASSWORD = process.env.ADMIN_PASSWORD || 'admin123';
  process.env.QUIZ_DATA_DIR = dataDir;

  const { createServer } = require('../../server');
  const { app, server, io } = await createServer({ useNext });

  await new Promise((resolve) => {
    server.listen(0, '127.0.0.1', resolve);
  });

  const address = server.address();
  const baseUrl = `http://127.0.0.1:${address.port}`;

  return { app, server, io, baseUrl };
}

async function stopTestServer(server, io) {
  if (io) {
    io.close();
  }

  if (server && server.listening) {
    await new Promise((resolve) => server.close(resolve));
  }
}

function cleanupTestDataDir(baseDir) {
  if (baseDir && fs.existsSync(baseDir)) {
    fs.rmSync(baseDir, { recursive: true, force: true });
  }
}

function resetTestEnv() {
  delete process.env.QUIZ_DATA_DIR;
}

module.exports = {
  createTestDataDir,
  seedUsers,
  seedQuiz,
  startTestServer,
  stopTestServer,
  cleanupTestDataDir,
  resetTestEnv
};
