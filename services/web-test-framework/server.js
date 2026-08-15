/* Playwright test framework for the UAT platform.
 *
 * Runner API  :6000  POST /execute, GET /runs, GET /runs/:id, GET /tests
 * Report view :6001  static Playwright HTML reports
 */
'use strict';

const express = require('express');
const http = require('http');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const RUNNER_PORT = process.env.RUNNER_PORT || 6000;
const REPORTS_PORT = process.env.REPORTS_PORT || 6001;
const WEBAPP_URL = process.env.WEBAPP_URL || 'http://localhost:8000';
const PROJECT_ROOT = __dirname;
const RUNS_DIR = path.join(PROJECT_ROOT, 'reports', 'runs');
const REPORT_ROOT = path.join(PROJECT_ROOT, 'reports');

fs.mkdirSync(RUNS_DIR, { recursive: true });

const app = express();
app.use(express.json());

function now() {
  return new Date().toISOString();
}

function loadRun(runId) {
  const file = path.join(RUNS_DIR, `${runId}.json`);
  if (!fs.existsSync(file)) return null;
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}

function saveRun(run) {
  fs.writeFileSync(path.join(RUNS_DIR, `${run.runId}.json`), JSON.stringify(run, null, 2));
}

function collectSpecs(suites, out = []) {
  for (const suite of suites || []) {
    out.push(...(suite.specs || []));
    collectSpecs(suite.suites, out);
  }
  return out;
}

function parseJsonReport(text) {
  try {
    const data = JSON.parse(text);
    let passed = 0;
    const failed = [];
    let skipped = 0;
    for (const spec of collectSpecs(data.suites)) {
      for (const result of spec.tests || []) {
        const status = (result.results || []).slice(-1)[0]?.status || 'unknown';
        if (status === 'passed') passed += 1;
        else if (status === 'skipped') skipped += 1;
        else failed.push({ name: spec.title, status });
      }
    }
    return { total: data.stats.expected + data.stats.unexpected + data.stats.skipped, passed, failed: failed.length, skipped, failures: failed };
  } catch (err) {
    return { total: 0, passed: 0, failed: 0, skipped: 0, failures: [], error: String(err) };
  }
}

function runPlaywright(runId, branch, commitSha, environment) {
  const outDir = path.join(REPORT_ROOT, 'runs', runId);
  fs.mkdirSync(outDir, { recursive: true });
  const jsonOut = path.join(outDir, 'results.json');
  const args = [
    'playwright',
    'test',
    '--config=playwright.config.js',
  ];
  const child = spawn('npx', args, {
    cwd: PROJECT_ROOT,
    env: {
      ...process.env,
      WEBAPP_URL,
      JSON_REPORT: jsonOut,
      HTML_REPORT_DIR: path.join(outDir, 'html'),
      PW_OUTPUT: path.join(outDir, 'test-results'),
    },
  });

  let stderrTail = '';
  child.stdout.on('data', () => {});
  child.stderr.on('data', (d) => { stderrTail = (stderrTail + d).slice(-4000); });
  child.on('close', (code) => {
    let summary;
    try {
      summary = parseJsonReport(fs.readFileSync(jsonOut, 'utf8'));
    } catch (err) {
      summary = { total: 0, passed: 0, failed: 0, skipped: 0, failures: [], error: String(err), stderrTail };
    }
    saveRun({
      runId, status: 'COMPLETED', environment, branch, commitSha,
      startedAt: loadRun(runId).startedAt, finishedAt: now(), exitCode: code, summary,
    });
  });
}

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'web-test-framework' }));

app.post('/execute', (req, res) => {
  const { environment = 'qa', branch = 'develop', commit_sha = '' } = req.body || {};
  const runId = `web-run-${Date.now()}`;
  saveRun({ runId, status: 'RUNNING', environment, branch, commitSha: commit_sha, startedAt: now() });
  runPlaywright(runId, branch, commit_sha, environment);
  res.json({ run_id: runId, status: 'RUNNING' });
});

app.get('/runs', (_req, res) => {
  const runs = fs.readdirSync(RUNS_DIR)
    .filter((f) => f.endsWith('.json'))
    .map((f) => loadRun(f.slice(0, -5)))
    .sort((a, b) => (a.startedAt < b.startedAt ? 1 : -1));
  res.json({
    runs: runs.map((r) => ({
      run_id: r.runId, status: r.status, environment: r.environment, branch: r.branch,
      started_at: r.startedAt, finished_at: r.finishedAt,
      total: r.summary ? r.summary.total : 0, passed: r.summary ? r.summary.passed : 0,
      failed: r.summary ? r.summary.failed : 0, skipped: r.summary ? r.summary.skipped : 0,
    })),
  });
});

app.get('/runs/:runId', (req, res) => {
  const run = loadRun(req.params.runId);
  if (!run) return res.status(404).json({ error: 'run not found' });
  res.json(run);
});

app.get('/runs/:runId/html', (req, res) => {
  const html = path.join(REPORT_ROOT, 'runs', req.params.runId, 'html', 'index.html');
  if (!fs.existsSync(html)) return res.status(404).json({ error: 'no html report yet' });
  res.sendFile(html);
});

// Report viewer on :6001 (static files + API on :6000).
const reportsApp = express();
reportsApp.use('/', express.static(REPORT_ROOT));

const runnerServer = http.createServer(app);
runnerServer.listen(RUNNER_PORT, () => console.log(`web-test-framework runner on :${RUNNER_PORT}`));
const reportsServer = http.createServer(reportsApp);
reportsServer.listen(REPORTS_PORT, () => console.log(`web-test-framework reports on :${REPORTS_PORT}`));
