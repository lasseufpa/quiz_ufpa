const request = require('supertest');
const {
  createTestDataDir,
  seedUsers,
  seedQuiz,
  startTestServer,
  stopTestServer,
  cleanupTestDataDir,
  resetTestEnv
} = require('./helpers');

describe('API integration', () => {
  let dataDir;
  let app;
  let server;
  let io;

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

    ({ app, server, io } = await startTestServer({ dataDir }));
  });

  afterEach(async () => {
    await stopTestServer(server, io);
    cleanupTestDataDir(dataDir);
    resetTestEnv();
  });

  it('lists available quizzes', async () => {
    const response = await request(app).get('/api/quizzes');
    expect(response.status).toBe(200);
    expect(response.body).toContain('sample');
  });

  it('creates and retrieves a quiz', async () => {
    const payload = {
      title: 'New Quiz',
      questions: [
        {
          text: 'Pergunta',
          options: ['A', 'B', 'C', 'D'],
          correct_option: 2,
          figure: 'none'
        }
      ]
    };

    const saveResponse = await request(app)
      .post('/api/quiz/new_quiz')
      .send(payload);

    expect(saveResponse.status).toBe(200);
    expect(saveResponse.body.name).toBe('new_quiz');

    const loadResponse = await request(app).get('/api/quiz/new_quiz');
    expect(loadResponse.status).toBe(200);
    expect(loadResponse.body.title).toBe('New Quiz');
  });

  it('persists admin session after login', async () => {
    const agent = request.agent(app);
    const loginResponse = await agent
      .post('/api/admin/login')
      .send({ password: 'admin123' });

    expect(loginResponse.status).toBe(200);

    const sessionResponse = await agent.get('/api/admin/session');
    expect(sessionResponse.status).toBe(200);
    expect(sessionResponse.body.loggedIn).toBe(true);
  });
});
