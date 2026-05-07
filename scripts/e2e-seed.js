const fs = require('fs');
const path = require('path');

const baseDir = path.resolve(process.env.QUIZ_DATA_DIR || '.e2e-data');
const staticDir = path.join(baseDir, 'static');
const quizzesDir = path.join(staticDir, 'quizzes');
const figuresDir = path.join(staticDir, 'quiz-figures');
const graphsDir = path.join(staticDir, 'graphs');
const privateDir = path.join(baseDir, '.private');
const scoresDir = path.join(baseDir, 'scores');

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true });
}

function writeJson(filePath, data) {
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf8');
}

if (fs.existsSync(baseDir)) {
  fs.rmSync(baseDir, { recursive: true, force: true });
}

ensureDir(quizzesDir);
ensureDir(figuresDir);
ensureDir(graphsDir);
ensureDir(privateDir);
ensureDir(scoresDir);

writeJson(path.join(privateDir, 'users.json'), ['Alice']);

const quizData = {
  title: 'E2E Quiz',
  questions: [
    {
      text: 'Quanto e 2 + 2?',
      options: ['3', '4', '5', '6'],
      correct_option: 1,
      figure: 'none'
    }
  ]
};

writeJson(path.join(quizzesDir, 'e2e_quiz.json'), quizData);
