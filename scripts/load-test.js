const { performance } = require('perf_hooks');

function parseArgs(argv) {
  const args = {};
  for (let index = 2; index < argv.length; index += 1) {
    const entry = argv[index];
    if (!entry.startsWith('--')) {
      continue;
    }
    const [key, rawValue] = entry.slice(2).split('=');
    args[key] = rawValue === undefined ? true : rawValue;
  }
  return args;
}

async function run() {
  if (typeof fetch !== 'function') {
    throw new Error('This script requires Node.js 18+ for the built-in fetch API.');
  }

  const args = parseArgs(process.argv);
  const total = Number(args.total || 100);
  const concurrency = Number(args.concurrency || 10);
  const url = args.url || 'http://127.0.0.1:5000/api/quizzes';

  let inFlight = 0;
  let cursor = 0;
  const timings = [];
  let failures = 0;

  async function worker() {
    while (cursor < total) {
      const current = cursor;
      cursor += 1;
      inFlight += 1;
      const start = performance.now();
      try {
        const response = await fetch(url);
        await response.text();
        if (!response.ok) {
          failures += 1;
        }
      } catch {
        failures += 1;
      } finally {
        timings[current] = performance.now() - start;
        inFlight -= 1;
      }
    }
  }

  const workers = [];
  const workerCount = Math.min(concurrency, total);
  for (let index = 0; index < workerCount; index += 1) {
    workers.push(worker());
  }

  await Promise.all(workers);

  const totalTime = timings.reduce((sum, value) => sum + value, 0);
  const avg = totalTime / timings.length;
  const sorted = timings.slice().sort((a, b) => a - b);
  const p95Index = Math.floor(sorted.length * 0.95) - 1;
  const p95 = sorted[Math.max(0, p95Index)];

  console.log('Load test summary');
  console.log(`Target URL: ${url}`);
  console.log(`Requests: ${timings.length}`);
  console.log(`Concurrency: ${concurrency}`);
  console.log(`Failures: ${failures}`);
  console.log(`Average ms: ${avg.toFixed(1)}`);
  console.log(`P95 ms: ${p95.toFixed(1)}`);
}

run().catch((error) => {
  console.error(error);
  process.exit(1);
});
