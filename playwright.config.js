const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  expect: {
    timeout: 10000
  },
  use: {
    baseURL: 'http://127.0.0.1:5001',
    trace: 'on-first-retry'
  },
  webServer: {
    command: 'node scripts/e2e-seed.js && node server.js',
    port: 5001,
    reuseExistingServer: !process.env.CI,
    env: {
      PORT: '5001',
      NODE_ENV: 'test',
      ADMIN_PASSWORD: 'admin123',
      QUIZ_DATA_DIR: '.e2e-data'
    }
  }
});
