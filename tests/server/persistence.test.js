const fs = require('fs');
const path = require('path');
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
    const timeout = setTimeout(() => reject(new Error(`Timeout waiting for ${event}`)), timeoutMs);
    socket.once(event, (payload) => {
      clearTimeout(timeout);
      resolve(payload);
    });
  });
}

describe('Persistence and recovery', () => {
  let dataDir;

  afterEach(() => {
    cleanupTestDataDir(dataDir);
    resetTestEnv();
  });

  it('restores the game state after restart', async () => {
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

    const firstServer = await startTestServer({ dataDir });

    const loginResponse = await request(firstServer.app)
      .post('/api/host/login')
      .send({ password: 'admin123' });

    const cookies = loginResponse.headers['set-cookie'] || [];
    const cookieHeader = cookies.map((cookie) => cookie.split(';')[0]).join('; ');

    const hostSocket = io(firstServer.baseUrl, {
      transports: ['websocket'],
      extraHeaders: { Cookie: cookieHeader }
    });

    const playerSocket = io(firstServer.baseUrl, { transports: ['websocket'] });

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
    await resultsPromise;

    hostSocket.close();
    playerSocket.close();

    await stopTestServer(firstServer.server, firstServer.io);

    const saveFile = path.join(dataDir, '.private', 'game_save.json');
    expect(fs.existsSync(saveFile)).toBe(true);

    const secondServer = await startTestServer({ dataDir });

    const secondLogin = await request(secondServer.app)
      .post('/api/host/login')
      .send({ password: 'admin123' });

    const secondCookies = secondLogin.headers['set-cookie'] || [];
    const secondCookieHeader = secondCookies.map((cookie) => cookie.split(';')[0]).join('; ');

    const resumedHost = io(secondServer.baseUrl, {
      transports: ['websocket'],
      extraHeaders: { Cookie: secondCookieHeader }
    });

    await waitForEvent(resumedHost, 'connect');

    const resumePromise = waitForEvent(resumedHost, 'resume_host_state');
    resumedHost.emit('host_join');
    const resumeState = await resumePromise;

    expect(resumeState.current_question).toBe(0);
    expect(resumeState.state).toBe(2);

    resumedHost.close();
    await stopTestServer(secondServer.server, secondServer.io);
  });
});
