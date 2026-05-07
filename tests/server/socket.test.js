const request = require('supertest');
const { io } = require('socket.io-client');
const {
  createTestDataDir,
  seedUsers,
  seedQuiz,
  startTestServer,
  stopTestServer,
  cleanupTestDataDir,
  resetTestEnv
} = require('./helpers');

function waitForEvent(socket, event, timeoutMs = 3000) {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error(`Timeout waiting for ${event}`));
    }, timeoutMs);

    socket.once(event, (payload) => {
      clearTimeout(timeout);
      resolve(payload);
    });
  });
}

describe('Socket flow', () => {
  let dataDir;
  let app;
  let server;
  let ioServer;
  let baseUrl;

  beforeEach(async () => {
    const data = createTestDataDir();
    dataDir = data.baseDir;

    seedUsers(data.privateDir, ['Alice']);
    seedQuiz(data.quizzesDir, 'sample', {
      title: 'Sample Quiz',
      questions: [
        {
          text: '2 + 2 = ? ',
          options: ['3', '4', '5', '6'],
          correct_option: 1,
          figure: 'none'
        }
      ]
    });

    ({ app, server, io: ioServer, baseUrl } = await startTestServer({ dataDir }));
  });

  afterEach(async () => {
    await stopTestServer(server, ioServer);
    cleanupTestDataDir(dataDir);
    resetTestEnv();
  });

  it('allows host to run a round and player to answer', async () => {
    const loginResponse = await request(app)
      .post('/api/host/login')
      .send({ password: 'admin123' });

    const cookies = loginResponse.headers['set-cookie'] || [];
    const cookieHeader = cookies.map((cookie) => cookie.split(';')[0]).join('; ');

    const hostSocket = io(baseUrl, {
      transports: ['websocket'],
      extraHeaders: {
        Cookie: cookieHeader
      }
    });

    const playerSocket = io(baseUrl, {
      transports: ['websocket']
    });

    await waitForEvent(hostSocket, 'connect');
    await waitForEvent(playerSocket, 'connect');

    hostSocket.emit('host_join');

    const joinSuccessPromise = waitForEvent(playerSocket, 'join_success');
    playerSocket.emit('player_join', { nickname: 'Alice' });
    await joinSuccessPromise;

    const questionPromise = waitForEvent(playerSocket, 'show_question');
    hostSocket.emit('start_game', { 'quiz-name': 'sample' });
    await questionPromise;

    const resultsPromise = waitForEvent(playerSocket, 'show_results');
    playerSocket.emit('submit_answer', { option_index: 1 });
    const results = await resultsPromise;

    expect(results.correct_option).toBe(1);

    const gameOverPromise = waitForEvent(playerSocket, 'game_over');
    hostSocket.emit('next_question');
    const leaderboard = await gameOverPromise;
    expect(Array.isArray(leaderboard)).toBe(true);

    hostSocket.close();
    playerSocket.close();
  });
});
