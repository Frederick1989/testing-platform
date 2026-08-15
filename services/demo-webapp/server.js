/* Demo weather web application under test (port 8000).
 *
 * Proxies weather requests to the weather mock API and renders a search UI.
 * Deliberate defects (matching the seeded demo defects) are marked below so the
 * UAT platform has real UI bugs to surface via the Playwright framework.
 */
'use strict';

const express = require('express');
const http = require('http');
const path = require('path');

const PORT = process.env.PORT || 8000;
const WEATHER_URL = process.env.WEATHER_URL || 'http://localhost:5000';

const app = express();

// Proxy the weather API (client-side JS talks same-origin; avoids CORS).
app.use('/api/weather', (req, res) => {
  const target = `${WEATHER_URL}${req.originalUrl}`;
  const upstream = http.request(
    target,
    { method: req.method, headers: { ...req.headers, host: new URL(target).host } },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode, upstreamRes.headers);
      upstreamRes.pipe(res);
      upstreamRes.on('error', () => res.status(502).json({ error: 'upstream unavailable' }));
    }
  );
  upstream.on('error', () => res.status(502).json({ error: 'upstream unavailable' }));
  req.on('error', () => res.status(400).json({ error: 'bad request' }));
  req.pipe(upstream);
});

app.get('/', (_req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});
app.use(express.static(path.join(__dirname, 'public')));

app.get('/health', (_req, res) => res.json({ status: 'ok', service: 'weather-demo-webapp' }));

app.listen(PORT, () => {
  console.log(`weather-demo-webapp listening on :${PORT} (weather proxy -> ${WEATHER_URL})`);
});
